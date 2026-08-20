"""Bridge to the phontrast R package (formerly phonJSD).

`phontrast <https://github.com/berrygrant/phontrast>`_ (Berry, 2026) quantifies
contrast/separation between phonological categories with information-theoretic
measures — Jensen-Shannon Divergence via KDE (the ``ks`` package), plus Pillai,
Bhattacharyya, and percent-overlap — in arbitrary n-dimensional acoustic
spaces.  The package was renamed from *phonJSD* to *phontrast*; this bridge
prefers ``phontrast`` and falls back to a legacy ``phonJSD`` install.

When R and phontrast are installed, vowelchemy calls the package directly so
the numbers match the lab's canonical method::

    compare_overlap_metrics(
        data         = <tokens>,
        features     = c("F1_norm", "F2_norm"),
        category_col = "vowel_canon",
        group_col    = "Age Group",     # or NULL for the whole dataset
        output       = "wide"
    )

When R is unavailable, :mod:`vowelchemy.metrics` provides a methodologically
aligned native Python implementation (KDE-based JSD, Pillai, Bhattacharyya) so
the app still works everywhere — see :func:`vowelchemy.metrics.pairwise_separation`.
"""

from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional, Sequence

import pandas as pd

from .runners import CommandResult, run_streaming, which

PHONTRAST_INSTALL_HINT = (
    "phontrast is an R (>= 4.1) package. Install R, then in R run:\n"
    '  install.packages("remotes")\n'
    '  remotes::install_github("berrygrant/phontrast")\n'
    "Ensure `Rscript` is on your PATH so vowelchemy can call it."
)

# Package names to try, in order: current name first, then the pre-rename one.
_R_PACKAGES = ("phontrast", "phonJSD")


@dataclass
class PhontrastStatus:
    rscript_path: Optional[str]
    package: Optional[str] = None  # which R package name resolved
    version: Optional[str] = None
    install_hint: str = PHONTRAST_INSTALL_HINT

    @property
    def package_installed(self) -> bool:
        return self.package is not None

    @property
    def available(self) -> bool:
        return bool(self.rscript_path) and self.package_installed


def phontrast_status(rscript: str = "Rscript") -> PhontrastStatus:
    """Detect Rscript and whether phontrast (or legacy phonJSD) is installed."""
    path = which(rscript)
    if not path:
        return PhontrastStatus(rscript_path=None)
    for pkg in _R_PACKAGES:
        try:
            check = subprocess.run(
                [rscript, "-e",
                 f'cat(as.character(requireNamespace("{pkg}", quietly=TRUE)))'],
                capture_output=True, text=True, timeout=60,
            )
        except (subprocess.SubprocessError, OSError):
            return PhontrastStatus(rscript_path=path)
        if not check.stdout.strip().endswith("TRUE"):
            continue
        version = None
        try:
            v = subprocess.run(
                [rscript, "-e", f'cat(as.character(packageVersion("{pkg}")))'],
                capture_output=True, text=True, timeout=60,
            )
            version = v.stdout.strip() or None
        except (subprocess.SubprocessError, OSError):
            pass
        return PhontrastStatus(rscript_path=path, package=pkg, version=version)
    return PhontrastStatus(rscript_path=path)


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


def build_r_script(
    features: Sequence[str],
    category_col: str,
    group_col: Optional[str],
    output: str = "wide",
    package: str = "phontrast",
) -> str:
    """Generate the R driver script (reads in_csv arg, writes out_csv arg)."""
    group_expr = f'"{group_col}"' if group_col else "NULL"
    return f"""#!/usr/bin/env Rscript
args <- commandArgs(trailingOnly = TRUE)
in_csv  <- args[1]
out_csv <- args[2]
suppressMessages(library({package}))
d <- read.csv(in_csv, check.names = FALSE, stringsAsFactors = FALSE)
res <- compare_overlap_metrics(
  data         = d,
  features     = {_r_string_vector(features)},
  category_col = "{category_col}",
  group_col    = {group_expr},
  output       = "{output}"
)
write.csv(res, out_csv, row.names = FALSE)
"""


def compare_overlap_metrics(
    df: pd.DataFrame,
    features: Sequence[str],
    category_col: str = "vowel_canon",
    group_col: Optional[str] = None,
    output: str = "wide",
    work_dir: Optional[str | Path] = None,
    rscript: str = "Rscript",
    on_output: Optional[Callable[[str], None]] = None,
    timeout: Optional[float] = 1800,
) -> PhontrastResult:
    """Run phontrast's ``compare_overlap_metrics`` on ``df`` and return its table.

    Only the needed columns are exported to R; rows with missing feature values
    are dropped first.
    """
    keep = [c for c in [*features, category_col, group_col] if c and c in df.columns]
    subset = df[keep].dropna(subset=[c for c in features if c in df.columns]).copy()

    work = Path(work_dir) if work_dir else Path(tempfile.mkdtemp(prefix="vowelchemy_phontrast_"))
    work.mkdir(parents=True, exist_ok=True)
    in_csv = work / "phontrast_input.csv"
    out_csv = work / "phontrast_output.csv"
    script_path = work / "run_phontrast.R"
    subset.to_csv(in_csv, index=False)

    status = phontrast_status(rscript)
    package = status.package or _R_PACKAGES[0]
    script_path.write_text(build_r_script(features, category_col, group_col, output, package))

    notes: list[str] = []
    if not status.rscript_path:
        notes.append("Rscript not found; cannot run phontrast (use the built-in engine).")
        return PhontrastResult(
            result=CommandResult([rscript], 127, "", "Rscript not found"),
            script_path=script_path, input_csv=in_csv, notes=notes,
        )
    if status.package == "phonJSD":
        notes.append(
            "Using the legacy phonJSD install; the package is now published as "
            "phontrast (remotes::install_github('berrygrant/phontrast'))."
        )

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
