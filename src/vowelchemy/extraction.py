"""Vowel-formant extraction via new-fave.

`new-fave <https://github.com/Forced-Alignment-and-Vowel-Extraction/new-fave>`_
(Fruehwald, 2024) is the modern successor to FAVE-extract (Rosenfelder et al.,
2022): it reads force-aligned TextGrids plus audio and measures vowel formants
with fasttrackpy's optimal-track selection.  Full citations in
``docs/REFERENCES.md``.

Vowelchemy shells out to new-fave's ``fave-extract`` CLI and then loads the
resulting CSV.  We deliberately extract **raw Hz** formants and apply
normalization ourselves (see :mod:`vowelchemy.normalization`) so students can
switch methods instantly without re-measuring.

.. note::
   new-fave's exact CLI surface evolves between releases.  The command builder
   below targets the documented directory subcommands ``fave-extract corpus``
   (a flat folder of wav/TextGrid pairs) and ``fave-extract subcorpora``
   (per-speaker sub-folders), and every call accepts ``extra_args`` plus a fully
   overridable ``subcommand``.  Verify against ``fave-extract --help`` for your
   installed version; adjusting the defaults here is a one-line change.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import pandas as pd

from .analysis import read_table
from .corpus import CorpusInventory, discover_corpus
from .runners import CommandResult, ToolStatus, probe_version, run_streaming, which
from .schema import ColumnSchema

NEWFAVE_INSTALL_HINT = (
    "new-fave installs with pip into any Python 3.10+ environment:\n"
    "  pip install new-fave\n"
    "It provides the `fave-extract` command used for measurement. The app can\n"
    "do this for you — 'Set up tools' ▸ Install new-fave — or you can point it\n"
    "at an environment that already has it."
)


def newfave_status(executable: str = "fave-extract", wait: bool = False) -> ToolStatus:
    """Detect new-fave; see :func:`vowelchemy.alignment.mfa_status` on ``wait``."""
    path = which(executable)
    version = probe_version(executable, version_args=("--version",), wait=wait) if path else None
    return ToolStatus(name="new-fave (fave-extract)", path=path,
                      version=version, install_hint=NEWFAVE_INSTALL_HINT)


# --------------------------------------------------------------------------- #
# Extraction
# --------------------------------------------------------------------------- #
@dataclass
class ExtractionResult:
    result: CommandResult
    output_dir: Path
    csv_path: Optional[Path] = None
    data: Optional[pd.DataFrame] = None
    schema: Optional[ColumnSchema] = None
    notes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.result.ok and self.data is not None and not self.data.empty


def _build_command(
    staged_dir: Path,
    executable: str,
    subcommand: str,
    speakers_file: Optional[Path],
    destination: Optional[Path],
    exclude_overlaps: bool,
    extra_args: Optional[list[str]],
) -> list[str]:
    """Assemble the fave-extract invocation.

    new-fave's directory subcommands (``corpus`` for a flat directory of
    wav/TextGrid pairs, ``subcorpora`` for per-speaker sub-folders) take the
    corpus directory as their positional argument; the output goes next to the
    inputs unless a destination is given.  Flags vary by release, so anything
    beyond the essentials is passed through ``extra_args``.
    """
    args: list[str] = [executable, subcommand, str(staged_dir)]
    if destination:
        args += ["--destination", str(destination)]
    if speakers_file:
        args += ["--speakers", str(speakers_file)]
    if exclude_overlaps:
        args += ["--exclude-overlaps"]
    if extra_args:
        args += list(extra_args)
    return args


def _load_output(*search_dirs: Path) -> tuple[Optional[Path], Optional[pd.DataFrame]]:
    """Find and load the most likely new-fave output CSV under ``search_dirs``.

    new-fave writes several files per corpus; the one-row-per-vowel measurements
    live in the ``*_points.csv`` file, which we prefer over ``tracks``/``param``.
    """
    candidates: list[Path] = []
    seen: set[Path] = set()
    for d in search_dirs:
        for p in sorted(d.rglob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True):
            if p not in seen:
                seen.add(p)
                candidates.append(p)

    def rank(p: Path) -> int:
        name = p.name.lower()
        if "points" in name:
            return 0
        if any(h in name for h in ("vowel", "formant", "fave", "measurement", "_data")):
            return 1
        if any(h in name for h in ("tracks", "param", "logparam")):
            return 3  # not the per-token summary
        return 2

    for path in sorted(candidates, key=rank):
        try:
            df = pd.read_csv(path)
        except (OSError, pd.errors.ParserError):
            continue
        if not df.empty:
            return path, df
    return None, None


def extract_vowels(
    audio_dir: str | os.PathLike,
    aligned_dir: str | os.PathLike,
    output_dir: str | os.PathLike,
    speakers_file: Optional[str | os.PathLike] = None,
    subcommand: str = "corpus",
    destination: Optional[str | os.PathLike] = None,
    exclude_overlaps: bool = True,
    extra_args: Optional[list[str]] = None,
    on_output: Optional[Callable[[str], None]] = None,
    executable: str = "fave-extract",
    link: bool = True,
    timeout: Optional[float] = None,
) -> ExtractionResult:
    """Extract vowel formants from aligned TextGrids + audio.

    Pairs each recording's audio with its force-aligned TextGrid (staging them
    together when they live in separate folders), runs new-fave, then loads and
    schema-detects the resulting ``*_points.csv``.  ``subcommand`` selects
    new-fave's directory mode: ``corpus`` (flat) or ``subcorpora`` (per-speaker
    sub-folders).
    """
    output_dir = Path(output_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    inventory = discover_corpus(audio_dir, transcript_dir=aligned_dir, aligned_dir=aligned_dir)
    aligned_items = [i for i in inventory.items if i.audio and i.textgrid and i.aligned]
    notes: list[str] = []
    if not aligned_items:
        notes.append(
            "No audio paired with an aligned TextGrid was found. "
            "Run alignment first, or check that TextGrids contain a phone tier."
        )

    # Stage wav + aligned TextGrid together for new-fave's directory mode
    # (flat for `corpus`, per-speaker sub-folders for `subcorpora`).
    staging = output_dir / "_newfave_input"
    staged = _stage_aligned(inventory, staging, link=link,
                            per_speaker=(subcommand == "subcorpora"))
    if on_output:
        on_output(f"Staged {staged} aligned pair(s) into {staging}")

    cmd = _build_command(
        staging, executable, subcommand,
        Path(speakers_file).expanduser() if speakers_file else None,
        Path(destination).expanduser() if destination else None,
        exclude_overlaps, extra_args,
    )
    if on_output:
        on_output("Running: " + " ".join(cmd))
    # Run from output_dir so any relative outputs land where we look for them.
    result = run_streaming(cmd, on_output=on_output, cwd=str(output_dir), timeout=timeout)

    # new-fave writes next to inputs (staging, which is under output_dir) or to
    # the destination; scanning output_dir recursively covers both.
    csv_path, df = _load_output(output_dir, *( [Path(destination)] if destination else []))
    schema = ColumnSchema.detect(df) if df is not None else None
    if df is not None and schema is not None and not schema.is_valid:
        notes.append(
            "Extraction produced a CSV but required columns "
            f"{schema.missing_required()} were not auto-detected; set them manually."
        )
    return ExtractionResult(
        result=result, output_dir=output_dir, csv_path=csv_path,
        data=df, schema=schema, notes=notes,
    )


def _stage_aligned(
    inventory: CorpusInventory, dest: Path, link: bool = True, per_speaker: bool = False
) -> int:
    """Place each aligned recording's wav + TextGrid together for new-fave.

    Flat by default (new-fave ``corpus`` mode); set ``per_speaker`` for the
    ``subcorpora`` layout.
    """
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    from .alignment import _place  # reuse the symlink/copy helper

    n = 0
    for item in inventory.items:
        if not (item.audio and item.textgrid and item.aligned):
            continue
        target = dest / item.speaker if per_speaker else dest
        target.mkdir(parents=True, exist_ok=True)
        _place(item.audio, target / f"{item.stem}{item.audio.suffix}", link)
        _place(item.textgrid, target / f"{item.stem}.TextGrid", link)
        n += 1
    return n


def load_existing_vowel_data(csv_path: str | os.PathLike) -> ExtractionResult:
    """Wrap an already-extracted CSV/TSV table as an :class:`ExtractionResult`."""
    csv_path = Path(csv_path).expanduser()
    df = read_table(csv_path)
    schema = ColumnSchema.detect(df)
    dummy = CommandResult(args=["<preexisting>"], returncode=0, stdout="", stderr="")
    notes: list[str] = []
    if not schema.is_valid:
        notes.append(f"Required columns {schema.missing_required()} not auto-detected.")
    return ExtractionResult(
        result=dummy, output_dir=csv_path.parent, csv_path=csv_path,
        data=df, schema=schema, notes=notes,
    )
