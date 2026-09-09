"""Bridge to the phontrast R package.

`phontrast <https://github.com/berrygrant/phontrast>`_ (Berry, 2026; on CRAN
since 2.3.1) quantifies contrast/separation between phonological categories:
Jensen-Shannon divergence and distance via KDE (the ``ks`` package), the
Pillai trace, Bhattacharyya distance/affinity, Mahalanobis distance and
proportional overlap, in arbitrary n-dimensional acoustic spaces.  The package
was renamed from *phonJSD* in 2.0.0, when ``compare_overlap_metrics()`` became
``phontrast()``.

When R and phontrast >= 2.3.1 are installed, vowelchemy drives the package
directly so the numbers are the lab's canonical ones.  For every pair of vowel
categories (phontrast compares exactly two) the generated script runs::

    phontrast(data, features, category_col, group_col, min_tokens, bw,
              density, mc_n, do_boot, n_boot, conf_level, output = "wide")
    pillai_overlap(data, features, category_col, proportion_standardized = TRUE)

and binds the proportion-standardized Pillai fields (``pillai_eq`` …) onto
phontrast's wide table, which ``phontrast()`` itself does not return.  One
naming asymmetry to know about: in this table ``group`` holds the group
*level* (phontrast's convention), whereas the built-in engine's table has
``group`` = the grouping column's name and ``group_value`` = the level.

**Finding R.** ``Rscript`` is rarely on the ``PATH`` of a double-clicked app:
the Windows installer never adds it, macOS launches apps with a bare
``/usr/bin:/bin`` path, and conda's R is only visible when its environment is
activated.  So :func:`candidate_rscripts` also looks in the standard install
locations (the Windows registry and ``Program Files``, the macOS
``R.framework`` and Homebrew, ``/usr/lib/R`` and ``rig``'s ``/opt/R`` on
Linux, every conda environment) and the user can point Vowelchemy at an R
explicitly (Set up tools, or ``VOWELCHEMY_RSCRIPT``).  Each R found is
probed once — version, library, whether phontrast is installed — and the
first with a usable phontrast wins; :func:`install_plan` can install the
package into that R.

When R is unavailable, :mod:`vowelchemy.metrics` is a native port of the same
estimators (same column names), so the app works everywhere — see
:func:`vowelchemy.metrics.pairwise_separation`.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional, Sequence

import pandas as pd

from . import toolenv
from .runners import CommandResult, run_streaming

PHONTRAST_MIN_VERSION = (2, 3, 1)  # phontrast() + proportion-standardized Pillai
PHONTRAST_INSTALL_HINT = (
    "R (>= 4.1) was not found. Install it from https://cloud.r-project.org — or, if it "
    "is installed, point Vowelchemy at it (Set up tools ▸ phontrast). Then install the "
    'package: in R run install.packages("phontrast").'
)
# Bandwidth selectors phontrast accepts (its default is the Hpi plug-in).
R_BANDWIDTHS = ("Hpi", "Hscv", "Hpi.diag", "scott.diag")
R_DENSITIES = ("kde", "mvnorm")

# Package names to probe, in order: current name first, then the pre-rename one
# (reported so the hint can say "update", not "install").
_R_PACKAGES = ("phontrast", "phonJSD")

# Where a chosen R is remembered (``VOWELCHEMY_RSCRIPT`` wins over the setting).
R_SETTINGS_KEY = "rscript"
R_ENV_VAR = "VOWELCHEMY_RSCRIPT"
# Relative locations of Rscript inside a folder someone might pick: an R home,
# its bin directory, the macOS framework, or a conda environment.
_RSCRIPT_IN_FOLDER = (
    "Rscript", "Rscript.exe",
    "bin/Rscript", "bin/Rscript.exe", "bin/x64/Rscript.exe",
    "Resources/bin/Rscript",                 # R.framework
    "Scripts/Rscript.exe", "Lib/R/bin/Rscript.exe",  # conda r-base on Windows
    "lib/R/bin/Rscript",                     # conda r-base (posix)
)
_MAX_PROBES = 8  # R installations to start when looking for phontrast


def _version_tuple(version: Optional[str]) -> tuple[int, ...]:
    if not version:
        return ()
    return tuple(int(p) for p in re.findall(r"\d+", version)[:3])


# --------------------------------------------------------------------------- #
# Finding R
# --------------------------------------------------------------------------- #
def selected_rscript() -> Optional[str]:
    """The Rscript the user chose, if any (env var wins over settings)."""
    override = os.environ.get(R_ENV_VAR)
    if override:
        return str(Path(override).expanduser())
    stored = toolenv.read_settings().get(R_SETTINGS_KEY)
    return str(Path(stored).expanduser()) if stored else None


def rscript_in(path: str | os.PathLike) -> Optional[str]:
    """``Rscript`` at ``path`` — the program itself, or a folder that contains it.

    Accepts an R home (``…/R-4.4.1``), its ``bin`` directory, the macOS
    ``R.framework`` (or one of its ``Versions``), or a conda environment.
    """
    p = Path(path).expanduser()
    if p.is_file():
        return str(p) if p.name.lower().startswith("rscript") else None
    if p.is_dir():
        for rel in _RSCRIPT_IN_FOLDER:
            candidate = p / rel
            if candidate.is_file():
                return str(candidate)
    return None


def set_selected_rscript(path: Optional[str]) -> Optional[str]:
    """Remember (or clear, with ``None``) the R to run phontrast with.

    Validates that the path holds an Rscript that actually runs, so the UI can
    explain a bad pick instead of silently storing it.  Returns the Rscript.
    """
    settings = toolenv.read_settings()
    if not path:
        settings.pop(R_SETTINGS_KEY, None)
        toolenv.write_settings(settings)
        toolenv.invalidate_caches("phontrast::")
        return None
    rscript = rscript_in(path)
    if rscript is None:
        raise ValueError(
            f"No Rscript found at {path}. Pick the Rscript program itself, or the folder "
            "R is installed in (the one with bin/ inside it)."
        )
    if probe_rscript(rscript) is None:
        raise ValueError(f"{rscript} did not run as R (it could not report its version).")
    settings[R_SETTINGS_KEY] = rscript
    toolenv.write_settings(settings)
    toolenv.invalidate_caches("phontrast::")  # probe the chosen R fresh
    return rscript


def _version_key(p: Path) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", p.name)) or (0,)


def _versioned(parent: Path, pattern: str) -> list[Path]:
    """Sub-directories of ``parent`` matching ``pattern``, newest version first."""
    try:
        kids = [d for d in parent.glob(pattern) if d.is_dir()]
    except OSError:
        return []
    return sorted(kids, key=_version_key, reverse=True)


def _windows_registry_r_homes() -> list[Path]:
    """R installations recorded by the Windows installer (``HKLM/HKCU\\SOFTWARE\\R-core``)."""
    try:
        import winreg  # type: ignore[import-not-found]
    except ImportError:
        return []
    homes: list[Path] = []
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for sub in (r"SOFTWARE\R-core\R", r"SOFTWARE\R-core\R64", r"SOFTWARE\WOW6432Node\R-core\R"):
            try:
                with winreg.OpenKey(hive, sub) as key:
                    try:
                        homes.append(Path(winreg.QueryValueEx(key, "InstallPath")[0]))
                    except OSError:
                        pass
                    i = 0
                    while True:
                        try:
                            name = winreg.EnumKey(key, i)
                        except OSError:
                            break
                        i += 1
                        try:
                            with winreg.OpenKey(key, name) as vk:
                                homes.append(Path(winreg.QueryValueEx(vk, "InstallPath")[0]))
                        except OSError:
                            continue
            except OSError:
                continue
    return homes


def _platform_rscripts() -> list[Path]:
    """Where installers put R on this platform, most likely / newest first."""
    out: list[Path] = []
    if sys.platform == "win32":
        homes = _windows_registry_r_homes()
        for root in (os.environ.get("ProgramFiles"), os.environ.get("ProgramW6432"),
                     os.environ.get("ProgramFiles(x86)"),
                     os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs"), "C:\\"):
            if root:
                homes += _versioned(Path(root) / "R", "R-*")
        for home in homes:
            out += [home / "bin" / "Rscript.exe", home / "bin" / "x64" / "Rscript.exe"]
    elif sys.platform == "darwin":
        framework = Path("/Library/Frameworks/R.framework")
        out.append(framework / "Resources" / "bin" / "Rscript")
        out += [v / "Resources" / "bin" / "Rscript" for v in _versioned(framework / "Versions", "*")]
        out += [Path(p) for p in ("/usr/local/bin/Rscript", "/opt/homebrew/bin/Rscript",
                                  "/opt/local/bin/Rscript")]
        out += [d / "bin" / "Rscript" for d in _versioned(Path("/opt/R"), "*")]  # rig
    else:
        out += [Path(p) for p in ("/usr/bin/Rscript", "/usr/local/bin/Rscript",
                                  "/usr/lib/R/bin/Rscript", "/usr/lib64/R/bin/Rscript")]
        out += [d / "bin" / "Rscript" for d in _versioned(Path("/opt/R"), "*")]
    return out


def _conda_rscripts() -> list[Path]:
    """Rscript inside conda/mamba environments (``r-base``), activated or not."""
    prefixes = toolenv._candidate_prefixes()
    for extra in toolenv._conda_cli_prefixes():
        if extra not in prefixes:
            prefixes.append(extra)
    out: list[Path] = []
    for prefix in prefixes:
        out += [prefix / "bin" / "Rscript", prefix / "Scripts" / "Rscript.exe",
                prefix / "Lib" / "R" / "bin" / "Rscript.exe", prefix / "lib" / "R" / "bin" / "Rscript"]
    return out


def candidate_rscripts() -> list[str]:
    """Every Rscript we can find, most likely first, de-duplicated by real path.

    Order: the R the user chose; the chosen tool environment, the app's own
    environment and ``PATH``; the platform's standard install locations; conda
    environments.
    """
    seen: set[Path] = set()
    out: list[str] = []

    def add(p: Optional[str | os.PathLike]) -> None:
        if not p:
            return
        path = Path(p)
        if not path.is_file():
            return
        try:
            real = path.resolve()
        except OSError:
            return
        if real in seen:
            return
        seen.add(real)
        out.append(str(path))

    add(selected_rscript())
    add(toolenv.resolve("Rscript"))
    for p in _platform_rscripts():
        add(p)
    for p in _conda_rscripts():
        add(p)
    return out


# One R start per installation: version, home, first library, installed package.
_PROBE_R = (
    'cat("R", paste(R.version$major, R.version$minor, sep = "."), "\\n");'
    'cat("HOME", R.home(), "\\n");'
    'cat("LIB", .libPaths()[1], "\\n");'
    'for (p in c("phontrast", "phonJSD")) if (requireNamespace(p, quietly = TRUE)) {'
    ' cat("PKG", p, as.character(utils::packageVersion(p)), "\\n"); break }'
)


def probe_rscript(rscript: str, timeout: float = 30) -> Optional[dict]:
    """Run ``rscript`` once; ``None`` if it does not behave like R.

    Returns ``{"path", "r_version", "home", "library", "package", "version"}``
    where ``package``/``version`` describe the installed phontrast (or legacy
    phonJSD) and ``home`` is ``R.home()`` — two launchers of one installation
    (``/usr/bin/Rscript`` and ``/usr/lib/R/bin/Rscript``) share it.
    """
    try:
        res = subprocess.run([rscript, "-e", _PROBE_R], capture_output=True, text=True,
                             timeout=timeout, env=toolenv.subprocess_env())
    except (subprocess.SubprocessError, OSError):
        return None
    info: dict = {"path": rscript, "r_version": None, "home": None, "library": None,
                  "package": None, "version": None}
    for line in res.stdout.splitlines():
        parts = line.split()
        if not parts:
            continue
        if parts[0] == "R" and len(parts) > 1 and info["r_version"] is None:
            info["r_version"] = parts[1]
        elif parts[0] == "HOME":
            info["home"] = line[len("HOME"):].strip() or None
        elif parts[0] == "LIB":
            info["library"] = line[len("LIB"):].strip() or None
        elif parts[0] == "PKG" and len(parts) > 2:
            info["package"], info["version"] = parts[1], parts[2]
    return info if info["r_version"] else None


def _supported(info: dict) -> bool:
    return info.get("package") == "phontrast" and _version_tuple(info.get("version")) >= PHONTRAST_MIN_VERSION


def _probe_all(explicit: Optional[str]) -> str:
    """Probe the candidate R installations; JSON so the cache can hold it."""
    paths = [explicit] if explicit else candidate_rscripts()[:_MAX_PROBES]
    infos: list[dict] = []
    homes: set[str] = set()
    for info in (probe_rscript(p) for p in paths):
        if not info:
            continue
        if info.get("home") in homes:
            continue  # another launcher of an installation already listed
        if info.get("home"):
            homes.add(info["home"])
        infos.append(info)
    best = next((i for i, info in enumerate(infos) if _supported(info)), None)
    if best is None:
        best = next((i for i, info in enumerate(infos) if info.get("package")), None)
    if best is None and infos:
        best = 0
    return json.dumps({"best": best, "candidates": infos})


@dataclass
class PhontrastStatus:
    rscript_path: Optional[str]
    package: Optional[str] = None  # which R package name resolved
    version: Optional[str] = None
    r_version: Optional[str] = None
    library: Optional[str] = None  # first library the probed R searches
    candidates: list[dict] = field(default_factory=list)  # every R found, probed
    selected: Optional[str] = None  # the R the user chose, if any
    probing: bool = False  # first look-up still running in the background

    @property
    def package_installed(self) -> bool:
        return self.package is not None

    @property
    def supported(self) -> bool:
        """phontrast new enough to have ``phontrast()`` and ``pillai_eq``."""
        return self.package == "phontrast" and _version_tuple(self.version) >= PHONTRAST_MIN_VERSION

    @property
    def available(self) -> bool:
        return bool(self.rscript_path) and self.supported

    @property
    def path(self) -> Optional[str]:
        return self.rscript_path

    @property
    def install_hint(self) -> str:
        need = ".".join(map(str, PHONTRAST_MIN_VERSION))
        if self.probing:
            return "Looking for R…"
        where = f" (R {self.r_version} at {self.rscript_path})" if self.rscript_path else ""
        if self.package_installed and not self.supported:
            found = f"{self.package} {self.version or ''}".strip()
            return (f"{found} is installed{where} but Vowelchemy needs phontrast >= {need} "
                    "(phontrast(), Jensen-Shannon distance, proportion-standardized Pillai). "
                    'Set up tools ▸ Install phontrast updates it, or in that R run '
                    'install.packages("phontrast").')
        if self.rscript_path and not self.package_installed:
            return (f"R {self.r_version} was found at {self.rscript_path}, but phontrast is not "
                    "installed in it. Set up tools ▸ Install phontrast does it for you, or in "
                    'that R run install.packages("phontrast").')
        return PHONTRAST_INSTALL_HINT


def phontrast_status(rscript: str = "Rscript", wait: bool = False) -> PhontrastStatus:
    """Find R and phontrast; cached like the other tool probes.

    With the default ``rscript="Rscript"`` every candidate R is considered
    (see :func:`candidate_rscripts`); an explicit path probes only that R.
    Starting R takes a moment, so ``wait=False`` probes in the background and
    reports ``probing=True`` until the answer is in.
    """
    explicit = rscript if rscript != "Rscript" else None
    key = f"phontrast::{explicit or 'auto'}"
    probe = lambda: _probe_all(explicit)  # noqa: E731
    cached = (toolenv.cached_version(key, probe) if wait
              else toolenv.cached_version_async(key, probe))
    selected = None if explicit else selected_rscript()
    if cached is None:
        return PhontrastStatus(rscript_path=None, selected=selected, probing=not wait)
    try:
        data = json.loads(cached)
    except ValueError:
        return PhontrastStatus(rscript_path=None, selected=selected)
    candidates = data.get("candidates") or []
    best = data.get("best")
    if best is None or best >= len(candidates):
        return PhontrastStatus(rscript_path=None, candidates=candidates, selected=selected)
    info = candidates[best]
    return PhontrastStatus(
        rscript_path=info.get("path"), package=info.get("package"), version=info.get("version"),
        r_version=info.get("r_version"), library=info.get("library"),
        candidates=candidates, selected=selected,
    )


# Installs into the user library (creating it if needed) so no admin rights are
# required; CRAN ships binaries for Windows/macOS, Linux builds from source.
_INSTALL_R = (
    'lib <- Sys.getenv("R_LIBS_USER"); if (!nzchar(lib)) lib <- .libPaths()[1];'
    ' lib <- path.expand(lib); dir.create(lib, recursive = TRUE, showWarnings = FALSE);'
    ' .libPaths(c(lib, .libPaths()));'
    ' options(repos = c(CRAN = "https://cloud.r-project.org"));'
    ' install.packages("phontrast", lib = lib);'
    ' if (!requireNamespace("phontrast", quietly = TRUE)) stop("phontrast did not install");'
    ' cat("phontrast", as.character(utils::packageVersion("phontrast")), "installed in", lib, "\\n")'
)


def install_plan(rscript: Optional[str]) -> tuple[Optional[list[str]], str]:
    """Command that installs phontrast into ``rscript``'s R, or ``None`` plus why not."""
    if not rscript:
        return None, ("R was not found, so phontrast cannot be installed. Install R from "
                      "https://cloud.r-project.org (or point Vowelchemy at your R), then "
                      "press Scan again.")
    return [rscript, "-e", _INSTALL_R], ""


# --------------------------------------------------------------------------- #
# Running phontrast
# --------------------------------------------------------------------------- #
@dataclass
class PhontrastResult:
    result: CommandResult
    data: Optional[pd.DataFrame] = None
    script_path: Optional[Path] = None
    input_csv: Optional[Path] = None
    output_csv: Optional[Path] = None
    notes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.result.ok and self.data is not None and not self.data.empty


def _r_string_vector(names: Sequence[str]) -> str:
    inner = ", ".join('"' + str(n).replace('"', '\\"') + '"' for n in names)
    return f"c({inner})"


def _r_string(value: Optional[str]) -> str:
    return "NULL" if value is None else '"' + str(value).replace('"', '\\"') + '"'


_R_TEMPLATE = r"""#!/usr/bin/env Rscript
# Generated by Vowelchemy: phontrast() + pillai_overlap(proportion_standardized = TRUE)
# for every pair of vowel categories, optionally within each level of a group.
args <- commandArgs(trailingOnly = TRUE)
in_csv  <- args[1]
out_csv <- args[2]
suppressMessages(library(phontrast))
if (utils::packageVersion("phontrast") < "@MIN_VERSION@") {
  stop("Vowelchemy needs phontrast >= @MIN_VERSION@ (found ",
       utils::packageVersion("phontrast"), "); run install.packages('phontrast').")
}

features     <- @FEATURES@
category_col <- @CATEGORY@
group_col    <- @GROUP@
opts <- list(
  min_tokens = @MIN_TOKENS@, bw = @BW@, density = @DENSITY@, mc_n = @MC_N@, eps = @EPS@,
  do_boot = @DO_BOOT@, n_boot = @N_BOOT@, conf_level = @CONF_LEVEL@
)

d <- read.csv(in_csv, check.names = FALSE, stringsAsFactors = FALSE)
d <- d[stats::complete.cases(d[, c(features, category_col), drop = FALSE]), , drop = FALSE]
d[[category_col]] <- as.character(d[[category_col]])
vowels <- sort(unique(d[[category_col]]))
if (length(vowels) < 2) stop("Need at least two vowel categories after removing missing values.")
pairs <- utils::combn(vowels, 2, simplify = FALSE)

# Proportion-standardized Pillai (Berry 2026; Becker 1986; Lachenbruch & Mickey 1968)
# plus Stanley & Sneller's (2023) e/m null reference, for one pair in one (sub)frame.
standardized <- function(sub_i, pr) {
  po <- tryCatch(
    suppressWarnings(pillai_overlap(sub_i, features, category_col, proportion_standardized = TRUE)),
    error = function(e) NULL
  )
  counts <- table(factor(sub_i[[category_col]], levels = pr))
  pick <- function(name, default = NA_real_) {
    if (is.null(po) || is.null(po[[name]])) default else po[[name]]
  }
  data.frame(
    n_a = as.integer(counts[[1]]), n_b = as.integer(counts[[2]]),
    pillai_eq = pick("pillai_eq"), pillai_eq_fallback = pick("pillai_eq_fallback", NA),
    d2_plugin = pick("d2_plugin"), d2_unbiased = pick("d2_unbiased"),
    d2_fallback = pick("d2_fallback"), bias_2p_over_H = pick("bias_2p_over_H"),
    H = pick("H"), fragile_minority = pick("fragile_minority", NA),
    pillai_null_p95 = min(1, exp(1) / (nrow(sub_i) / 2)),
    stringsAsFactors = FALSE
  )
}

rows <- list()
for (pr in pairs) {
  sub <- d[d[[category_col]] %in% pr, , drop = FALSE]
  res <- tryCatch(
    suppressWarnings(phontrast(
      data = sub, features = features, category_col = category_col, group_col = group_col,
      min_tokens = opts$min_tokens, bw = opts$bw, eps = opts$eps, output = "wide",
      do_boot = opts$do_boot, n_boot = opts$n_boot, conf_level = opts$conf_level,
      progress = FALSE, density = opts$density, mc_n = opts$mc_n
    )),
    error = function(e) {
      message("phontrast(", pr[1], "~", pr[2], "): ", conditionMessage(e))
      NULL
    }
  )
  if (is.null(res) || !nrow(res)) next
  res <- as.data.frame(res, stringsAsFactors = FALSE)
  extra <- do.call(rbind, lapply(seq_len(nrow(res)), function(i) {
    sub_i <- if (is.null(group_col)) sub else
      sub[as.character(sub[[group_col]]) == as.character(res$group[i]), , drop = FALSE]
    standardized(sub_i, pr)
  }))
  rows[[length(rows) + 1]] <- cbind(
    data.frame(vowel_a = pr[1], vowel_b = pr[2], stringsAsFactors = FALSE), res, extra
  )
}
if (!length(rows)) stop("phontrast returned no rows for any vowel pair (check min_tokens and token counts).")
out <- do.call(rbind, rows)
write.csv(out, out_csv, row.names = FALSE)
"""


def build_r_script(
    features: Sequence[str],
    category_col: str,
    group_col: Optional[str],
    bw: str = "Hpi",
    density: str = "kde",
    mc_n: int = 10_000,
    min_tokens: int = 20,
    n_boot: int = 0,
    conf_level: float = 0.95,
    eps: float = 1e-6,
) -> str:
    """Generate the R driver script (reads in_csv arg, writes out_csv arg).

    ``n_boot`` > 0 turns on phontrast's bootstrap (``do_boot = TRUE``), which
    adds ``<metric>_mean/_sd/_ci_lower/_ci_upper`` columns.
    """
    if bw not in R_BANDWIDTHS:
        raise ValueError(f"bw must be one of {R_BANDWIDTHS}, got {bw!r}")
    if density not in R_DENSITIES:
        raise ValueError(f"density must be one of {R_DENSITIES}, got {density!r}")
    subs = {
        "@MIN_VERSION@": ".".join(map(str, PHONTRAST_MIN_VERSION)),
        "@FEATURES@": _r_string_vector(features),
        "@CATEGORY@": _r_string(category_col),
        "@GROUP@": _r_string(group_col),
        "@MIN_TOKENS@": str(int(min_tokens)),
        "@BW@": _r_string(bw),
        "@DENSITY@": _r_string(density),
        "@MC_N@": f"{int(mc_n)}L",
        "@EPS@": repr(float(eps)),
        "@DO_BOOT@": "TRUE" if n_boot > 0 else "FALSE",
        "@N_BOOT@": str(int(n_boot) if n_boot > 0 else 1000),
        "@CONF_LEVEL@": repr(float(conf_level)),
    }
    script = _R_TEMPLATE
    for key, value in subs.items():
        script = script.replace(key, value)
    return script


def run_phontrast(
    df: pd.DataFrame,
    features: Sequence[str],
    category_col: str = "vowel_canon",
    group_col: Optional[str] = None,
    bw: str = "Hpi",
    density: str = "kde",
    mc_n: int = 10_000,
    min_tokens: int = 20,
    n_boot: int = 0,
    conf_level: float = 0.95,
    work_dir: Optional[str | Path] = None,
    rscript: str = "Rscript",
    on_output: Optional[Callable[[str], None]] = None,
    timeout: Optional[float] = 1800,
) -> PhontrastResult:
    """Run phontrast on every vowel pair in ``df`` and return the combined table.

    Only the needed columns are exported to R; rows with missing feature values
    are dropped first.  The table has one row per (vowel pair × group level)
    with phontrast's wide columns (``jsd``, ``js_distance``, ``pillai``,
    ``pillai_p_value``, ``bhatt_dist``, ``bhatt_affinity``,
    ``mahalanobis_dist``, ``percent_overlap`` …) plus ``vowel_a``/``vowel_b``,
    ``n_a``/``n_b``, the proportion-standardized Pillai fields and
    ``pillai_null_p95``.  With the default ``rscript`` the R that
    :func:`phontrast_status` found is used.
    """
    keep = [c for c in [*features, category_col, group_col] if c and c in df.columns]
    subset = df[keep].dropna(subset=[c for c in features if c in df.columns]).copy()

    work = Path(work_dir) if work_dir else Path(tempfile.mkdtemp(prefix="vowelchemy_phontrast_"))
    work.mkdir(parents=True, exist_ok=True)
    in_csv = work / "phontrast_input.csv"
    out_csv = work / "phontrast_output.csv"
    script_path = work / "run_phontrast.R"
    subset.to_csv(in_csv, index=False)
    script_path.write_text(build_r_script(
        features, category_col, group_col, bw=bw, density=density, mc_n=mc_n,
        min_tokens=min_tokens, n_boot=n_boot, conf_level=conf_level,
    ))

    status = phontrast_status(rscript, wait=True)
    notes: list[str] = []
    if not status.rscript_path:
        notes.append("Rscript not found; cannot run phontrast (use the built-in engine).")
        return PhontrastResult(
            result=CommandResult([rscript], 127, "", "Rscript not found"),
            script_path=script_path, input_csv=in_csv, notes=notes,
        )
    if status.package_installed and not status.supported:
        notes.append(status.install_hint)

    result = run_streaming(
        [status.rscript_path, str(script_path), str(in_csv), str(out_csv)],
        on_output=on_output, timeout=timeout,
    )
    data = None
    if out_csv.exists():
        try:
            data = pd.read_csv(out_csv)
        except (OSError, pd.errors.ParserError) as exc:
            notes.append(f"Could not read phontrast output: {exc}")
    else:
        notes.append("phontrast did not produce an output file; see the log.")
    return PhontrastResult(
        result=result, data=data, script_path=script_path,
        input_csv=in_csv, output_csv=out_csv, notes=notes,
    )


# Name used before the phontrast 2.4.1 port (mirrors phontrast's own deprecated alias).
compare_overlap_metrics = run_phontrast
