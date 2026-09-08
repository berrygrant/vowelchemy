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

When R is unavailable, :mod:`vowelchemy.metrics` is a native port of the same
estimators (same column names), so the app works everywhere — see
:func:`vowelchemy.metrics.pairwise_separation`.
"""

from __future__ import annotations

import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional, Sequence

import pandas as pd

from . import toolenv
from .runners import CommandResult, run_streaming, which

PHONTRAST_MIN_VERSION = (2, 3, 1)  # phontrast() + proportion-standardized Pillai
PHONTRAST_INSTALL_HINT = (
    "phontrast is an R (>= 4.1) package on CRAN. Install R, then in R run:\n"
    '  install.packages("phontrast")\n'
    "Ensure `Rscript` is on your PATH so vowelchemy can call it."
)
# Bandwidth selectors phontrast accepts (its default is the Hpi plug-in).
R_BANDWIDTHS = ("Hpi", "Hscv", "Hpi.diag", "scott.diag")
R_DENSITIES = ("kde", "mvnorm")

# Package names to probe, in order: current name first, then the pre-rename one
# (reported so the hint can say "update", not "install").
_R_PACKAGES = ("phontrast", "phonJSD")


def _version_tuple(version: Optional[str]) -> tuple[int, ...]:
    if not version:
        return ()
    return tuple(int(p) for p in re.findall(r"\d+", version)[:3])


@dataclass
class PhontrastStatus:
    rscript_path: Optional[str]
    package: Optional[str] = None  # which R package name resolved
    version: Optional[str] = None

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
    def install_hint(self) -> str:
        if self.package_installed and not self.supported:
            found = f"{self.package} {self.version or ''}".strip()
            need = ".".join(map(str, PHONTRAST_MIN_VERSION))
            return (f"{found} is installed but Vowelchemy needs phontrast >= {need} "
                    "(phontrast(), Jensen-Shannon distance, proportion-standardized Pillai). "
                    'In R run: install.packages("phontrast")')
        return PHONTRAST_INSTALL_HINT


def phontrast_status(rscript: str = "Rscript", wait: bool = False) -> PhontrastStatus:
    """Detect Rscript and whether phontrast (or legacy phonJSD) is installed.

    Cached like the other tool probes: starting R twice per status poll is slow
    enough to make the sidebar feel stuck. ``wait=False`` probes in the
    background, so a request never waits for R to boot.
    """
    path = which(rscript)
    if not path:
        return PhontrastStatus(rscript_path=None)
    key = f"phontrast::{path}"
    probe = lambda: _probe_r_packages(rscript, path)  # noqa: E731
    cached = (toolenv.cached_version(key, probe) if wait
              else toolenv.cached_version_async(key, probe))
    if cached is None:
        return PhontrastStatus(rscript_path=path)
    package, _, version = cached.partition(" ")
    return PhontrastStatus(rscript_path=path, package=package, version=version or None)


def _probe_r_packages(rscript: str, path: str) -> Optional[str]:
    """``"<package> <version>"`` for the first installed R package, else ``None``."""
    for pkg in _R_PACKAGES:
        try:
            check = subprocess.run(
                [rscript, "-e",
                 f'cat(as.character(requireNamespace("{pkg}", quietly=TRUE)))'],
                capture_output=True, text=True, timeout=60,
            )
        except (subprocess.SubprocessError, OSError):
            return None
        if not check.stdout.strip().endswith("TRUE"):
            continue
        version = ""
        try:
            v = subprocess.run(
                [rscript, "-e", f'cat(as.character(packageVersion("{pkg}")))'],
                capture_output=True, text=True, timeout=60,
            )
            version = v.stdout.strip()
        except (subprocess.SubprocessError, OSError):
            pass
        return f"{pkg} {version}".strip()
    return None


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
    ``pillai_null_p95``.
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
        [rscript, str(script_path), str(in_csv), str(out_csv)],
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
