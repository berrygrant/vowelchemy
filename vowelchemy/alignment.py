"""Force-alignment via the Montreal Forced Aligner (MFA 3.x).

Vowelchemy does not bundle MFA — it is a large Kaldi-based tool best installed
in its own conda environment (see the README).  This module *detects* an MFA
install and drives it:

* stage a corpus directory when audio and transcripts live in separate folders;
* download the acoustic model + pronunciation dictionary if needed;
* optionally validate the corpus;
* run ``mfa align`` and report where the TextGrids landed.

The canonical MFA 3.x commands used here are::

    mfa model download acoustic  english_us_arpa
    mfa model download dictionary english_us_arpa
    mfa validate <corpus_dir> <dictionary> <acoustic_model>
    mfa align    <corpus_dir> <dictionary> <acoustic_model> <output_dir>

MFA expects each ``<basename>.wav`` to sit next to a ``<basename>.lab`` (or
``.txt``) transcript, optionally grouped into per-speaker sub-folders.

Reference: McAuliffe, Socolof, Mihuc, Wagner & Sonderegger (2017), *Montreal
Forced Aligner: Trainable text-speech alignment using Kaldi*, Interspeech —
full citation in ``docs/REFERENCES.md``.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from .constants import DEFAULT_ACOUSTIC_MODEL, DEFAULT_DICTIONARY
from .corpus import CorpusInventory
from .runners import CommandResult, ToolStatus, probe_version, run_streaming, which

MFA_INSTALL_HINT = (
    "Install MFA in its own environment, e.g.\n"
    "  conda create -n aligner -c conda-forge montreal-forced-aligner\n"
    "  conda activate aligner\n"
    "then launch vowelchemy from that environment so `mfa` is on PATH."
)


def mfa_status(executable: str = "mfa") -> ToolStatus:
    """Detect whether MFA is available and grab its version."""
    path = which(executable)
    version = probe_version(executable, version_args=("version",)) if path else None
    return ToolStatus(name="Montreal Forced Aligner", path=path,
                      version=version, install_hint=MFA_INSTALL_HINT)


# --------------------------------------------------------------------------- #
# Corpus staging (handles audio + transcripts in separate folders)
# --------------------------------------------------------------------------- #
@dataclass
class StagingResult:
    corpus_dir: Path
    n_staged: int
    skipped: list[str] = field(default_factory=list)
    linked: bool = True


def stage_corpus(
    inventory: CorpusInventory,
    dest_dir: str | os.PathLike,
    link: bool = True,
    per_speaker: bool = True,
) -> StagingResult:
    """Build an MFA-ready corpus directory from a discovered inventory.

    Each pairable recording is placed as ``<dest>/<speaker>/<stem>.wav`` next to
    a ``<stem>.lab`` transcript.  Symlinks are used by default (fast, no copy);
    set ``link=False`` to copy instead (needed for some network filesystems).
    """
    dest = Path(dest_dir).expanduser()
    dest.mkdir(parents=True, exist_ok=True)
    n = 0
    skipped: list[str] = []

    for item in inventory.items:
        if not item.audio or not (item.transcript or item.textgrid):
            if item.audio or item.transcript or item.textgrid:
                skipped.append(item.stem)
            continue
        target_dir = dest / item.speaker if per_speaker else dest
        target_dir.mkdir(parents=True, exist_ok=True)

        _place(item.audio, target_dir / f"{item.stem}{item.audio.suffix}", link)
        # Prefer a plain-text transcript; MFA reads .lab and .txt.
        transcript = item.transcript
        if transcript is not None:
            suffix = transcript.suffix if transcript.suffix.lower() in {".lab", ".txt"} else ".lab"
            _place(transcript, target_dir / f"{item.stem}{suffix}", link)
        elif item.textgrid is not None:
            # Align directly from an existing (word-only) TextGrid.
            _place(item.textgrid, target_dir / f"{item.stem}.TextGrid", link)
        n += 1

    return StagingResult(corpus_dir=dest, n_staged=n, skipped=skipped, linked=link)


def _place(src: Path, dst: Path, link: bool) -> None:
    if dst.exists() or dst.is_symlink():
        dst.unlink()
    if link:
        try:
            os.symlink(os.path.abspath(src), dst)
            return
        except (OSError, NotImplementedError):
            pass  # fall back to copy (e.g. Windows without privilege)
    shutil.copy2(src, dst)


# --------------------------------------------------------------------------- #
# Model download / validate / align
# --------------------------------------------------------------------------- #
def download_models(
    acoustic_model: str = DEFAULT_ACOUSTIC_MODEL,
    dictionary: str = DEFAULT_DICTIONARY,
    on_output: Optional[Callable[[str], None]] = None,
    executable: str = "mfa",
) -> list[CommandResult]:
    """Download the acoustic model and dictionary (idempotent in MFA)."""
    results = [
        run_streaming([executable, "model", "download", "acoustic", acoustic_model],
                      on_output=on_output),
        run_streaming([executable, "model", "download", "dictionary", dictionary],
                      on_output=on_output),
    ]
    return results


def validate_corpus(
    corpus_dir: str | os.PathLike,
    dictionary: str = DEFAULT_DICTIONARY,
    acoustic_model: str = DEFAULT_ACOUSTIC_MODEL,
    num_jobs: int = 3,
    on_output: Optional[Callable[[str], None]] = None,
    executable: str = "mfa",
) -> CommandResult:
    return run_streaming(
        [executable, "validate", str(corpus_dir), dictionary, acoustic_model,
         "--num_jobs", str(num_jobs), "--clean"],
        on_output=on_output,
    )


@dataclass
class AlignmentResult:
    result: CommandResult
    output_dir: Path
    textgrids: list[Path] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.result.ok and bool(self.textgrids)


def align_corpus(
    corpus_dir: str | os.PathLike,
    output_dir: str | os.PathLike,
    dictionary: str = DEFAULT_DICTIONARY,
    acoustic_model: str = DEFAULT_ACOUSTIC_MODEL,
    num_jobs: int = 3,
    beam: Optional[int] = None,
    single_speaker: bool = False,
    clean: bool = True,
    extra_args: Optional[list[str]] = None,
    on_output: Optional[Callable[[str], None]] = None,
    executable: str = "mfa",
    timeout: Optional[float] = None,
) -> AlignmentResult:
    """Run ``mfa align`` and collect the resulting TextGrids.

    Produces long-format TextGrids (word + phone tiers) under ``output_dir``.
    """
    output_dir = Path(output_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    args = [
        executable, "align", str(corpus_dir), dictionary, acoustic_model, str(output_dir),
        "--num_jobs", str(num_jobs), "--output_format", "long_textgrid",
    ]
    if clean:
        args.append("--clean")
    if single_speaker:
        args.append("--single_speaker")
    if beam is not None:
        args += ["--beam", str(beam)]
    if extra_args:
        args += list(extra_args)

    result = run_streaming(args, on_output=on_output, timeout=timeout)
    textgrids = sorted(output_dir.rglob("*.TextGrid"))
    return AlignmentResult(result=result, output_dir=output_dir, textgrids=textgrids)


def align_inventory(
    inventory: CorpusInventory,
    output_dir: str | os.PathLike,
    staging_dir: Optional[str | os.PathLike] = None,
    dictionary: str = DEFAULT_DICTIONARY,
    acoustic_model: str = DEFAULT_ACOUSTIC_MODEL,
    on_output: Optional[Callable[[str], None]] = None,
    link: bool = True,
    **align_kwargs,
) -> AlignmentResult:
    """End-to-end: stage a discovered corpus then align it.

    Convenience wrapper for the common case where audio and transcripts were
    discovered (possibly across separate folders) and need staging before MFA.
    """
    output_dir = Path(output_dir).expanduser()
    staging = staging_dir or (output_dir / "_mfa_corpus")
    staged = stage_corpus(inventory, staging, link=link)
    if on_output:
        how = "symlinked" if staged.linked else "copied"
        on_output(f"Staged ({how}) {staged.n_staged} recording(s) into {staged.corpus_dir}")
        if staged.skipped:
            on_output(f"Skipped {len(staged.skipped)} unpaired recording(s).")
    return align_corpus(
        staged.corpus_dir, output_dir, dictionary=dictionary,
        acoustic_model=acoustic_model, on_output=on_output, **align_kwargs,
    )
