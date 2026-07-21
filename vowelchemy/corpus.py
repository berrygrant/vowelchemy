"""Corpus discovery: locate and pair audio with transcripts.

This module answers the first questions in the pipeline:

* Where are the ``.wav`` files and where are the transcripts?  They may live in
  the same folder, in separate folders, or in per-speaker sub-folders, and the
  corpus may be a remotely mounted filesystem.
* Which recordings already have a **force-aligned** TextGrid (a phone tier)?
* Is there already **extracted vowel data** we can jump straight to?

Everything here is filesystem-only and dependency-light so it is fast and
easy to unit-test.  TextGrid inspection uses a tolerant tier-name *sniffer*
rather than a full parse — we only need to know which tiers exist, and that
should work for both long- and short-format TextGrids and mild encoding noise.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

from .constants import (
    AUDIO_EXTENSIONS,
    PHONE_TIER_NAMES,
    TEXTGRID_EXTENSIONS,
    TRANSCRIPT_TEXT_EXTENSIONS,
    WORD_TIER_NAMES,
)

_TIER_NAME_RE = re.compile(r'name\s*=\s*"((?:[^"\\]|\\.)*)"')
_QUOTED_RE = re.compile(r'"((?:[^"\\]|\\.)*)"')
_TIER_CLASS_TOKENS = {"IntervalTier", "TextTier"}


# --------------------------------------------------------------------------- #
# TextGrid inspection
# --------------------------------------------------------------------------- #
def sniff_textgrid_tiers(path: Path) -> list[str]:
    """Return the tier names declared in a TextGrid without a full parse.

    Handles both TextGrid serialisations:

    * **long** — lines like ``name = "words"``
    * **short** — a bare ``"IntervalTier"`` line followed by the name line

    Returns an empty list if the file cannot be read as a TextGrid.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    if "TextGrid" not in text and "IntervalTier" not in text:
        return []

    # Long format: explicit ``name = "..."`` entries (skip the file-level
    # object which does not use ``name =``).
    long_names = _TIER_NAME_RE.findall(text)
    if long_names:
        return [n.strip() for n in long_names]

    # Short format: every ``"IntervalTier"``/``"TextTier"`` token is followed by
    # the tier's quoted name.
    tokens = _QUOTED_RE.findall(text)
    tiers: list[str] = []
    for i, tok in enumerate(tokens):
        if tok in _TIER_CLASS_TOKENS and i + 1 < len(tokens):
            tiers.append(tokens[i + 1].strip())
    return tiers


def is_aligned_textgrid(path: Path) -> bool:
    """True if the TextGrid contains a phone-level tier (i.e. force-aligned)."""
    tiers = {t.lower() for t in sniff_textgrid_tiers(path)}
    return bool(tiers & PHONE_TIER_NAMES)


def textgrid_has_word_tier(path: Path) -> bool:
    tiers = {t.lower() for t in sniff_textgrid_tiers(path)}
    return bool(tiers & WORD_TIER_NAMES)


# --------------------------------------------------------------------------- #
# Discovery data structures
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class CorpusItem:
    """A single recording and whatever transcript/alignment goes with it."""

    stem: str
    speaker: str
    audio: Optional[Path] = None
    transcript: Optional[Path] = None  # plain .lab/.txt transcript
    textgrid: Optional[Path] = None  # a TextGrid (aligned or not)
    aligned: bool = False  # textgrid exists and has a phone tier

    @property
    def has_audio(self) -> bool:
        return self.audio is not None

    @property
    def has_transcript(self) -> bool:
        return self.transcript is not None or self.textgrid is not None

    @property
    def is_pairable(self) -> bool:
        """Ready to align: has audio and some source transcript text."""
        return self.has_audio and (self.transcript is not None or self.textgrid is not None)


@dataclass
class CorpusInventory:
    """The result of scanning a corpus location."""

    items: list[CorpusItem] = field(default_factory=list)
    audio_dir: Optional[Path] = None
    transcript_dir: Optional[Path] = None
    warnings: list[str] = field(default_factory=list)

    # -- convenience views ------------------------------------------------- #
    @property
    def paired(self) -> list[CorpusItem]:
        return [i for i in self.items if i.has_audio and i.has_transcript]

    @property
    def audio_without_transcript(self) -> list[CorpusItem]:
        return [i for i in self.items if i.has_audio and not i.has_transcript]

    @property
    def transcript_without_audio(self) -> list[CorpusItem]:
        return [i for i in self.items if not i.has_audio and i.has_transcript]

    @property
    def aligned(self) -> list[CorpusItem]:
        return [i for i in self.items if i.aligned]

    @property
    def needs_alignment(self) -> list[CorpusItem]:
        """Recordings that can be aligned but don't yet have a phone tier."""
        return [i for i in self.items if i.is_pairable and not i.aligned]

    @property
    def speakers(self) -> list[str]:
        return sorted({i.speaker for i in self.items})

    @property
    def fully_aligned(self) -> bool:
        pairable = [i for i in self.items if i.is_pairable]
        return bool(pairable) and all(i.aligned for i in pairable)

    def summary(self) -> dict:
        return {
            "recordings": len(self.items),
            "paired": len(self.paired),
            "aligned": len(self.aligned),
            "needs_alignment": len(self.needs_alignment),
            "audio_without_transcript": len(self.audio_without_transcript),
            "transcript_without_audio": len(self.transcript_without_audio),
            "speakers": len(self.speakers),
        }


# --------------------------------------------------------------------------- #
# Path validation (supports remote mounts)
# --------------------------------------------------------------------------- #
@dataclass
class PathStatus:
    path: Path
    exists: bool
    is_dir: bool
    readable: bool
    message: str

    @property
    def ok(self) -> bool:
        return self.exists and self.is_dir and self.readable


def validate_location(path: str | os.PathLike) -> PathStatus:
    """Validate a corpus directory, tolerating remotely mounted filesystems.

    A remote corpus (SSHFS / SMB / NFS) simply appears as a normal path once
    mounted, so we only check existence, that it is a directory, and that it is
    readable — never assume local disk.
    """
    p = Path(path).expanduser()
    try:
        exists = p.exists()
    except OSError as exc:  # e.g. a stale network mount
        return PathStatus(p, False, False, False, f"Cannot stat path ({exc}).")
    if not exists:
        return PathStatus(p, False, False, False, "Path does not exist.")
    is_dir = p.is_dir()
    if not is_dir:
        return PathStatus(p, True, False, False, "Path exists but is not a directory.")
    readable = os.access(p, os.R_OK | os.X_OK)
    if not readable:
        return PathStatus(p, True, True, False, "Directory exists but is not readable.")
    return PathStatus(p, True, True, True, "OK")


# --------------------------------------------------------------------------- #
# Discovery
# --------------------------------------------------------------------------- #
def _iter_files(root: Path, extensions: set[str]) -> Iterable[Path]:
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            if os.path.splitext(name)[1].lower() in extensions:
                yield Path(dirpath) / name


def _infer_speaker(file_path: Path, root: Path) -> str:
    """Infer a speaker id from directory layout.

    MFA/new-fave corpora are commonly organised as ``root/<speaker>/file.wav``.
    If the file sits directly in ``root`` we fall back to ``"unknown"`` — the
    real speaker id can still be supplied later via a demographics table.
    """
    try:
        rel = file_path.relative_to(root)
    except ValueError:
        return file_path.parent.name or "unknown"
    parts = rel.parts
    if len(parts) >= 2:
        return parts[0]
    return "unknown"


def _index_by_stem(
    root: Path, extensions: set[str], warnings: list[str], kind: str
) -> dict[str, Path]:
    """Map basename-stem -> path. Warn (but keep first) on stem collisions."""
    index: dict[str, Path] = {}
    for path in _iter_files(root, extensions):
        stem = path.stem
        if stem in index and index[stem] != path:
            warnings.append(
                f"Duplicate {kind} basename '{stem}' "
                f"({index[stem].name} and {path.name}); using the first."
            )
            continue
        index.setdefault(stem, path)
    return index


def discover_corpus(
    audio_dir: str | os.PathLike,
    transcript_dir: Optional[str | os.PathLike] = None,
    aligned_dir: Optional[str | os.PathLike] = None,
) -> CorpusInventory:
    """Scan for audio + transcripts and pair them by basename.

    Parameters
    ----------
    audio_dir:
        Directory (searched recursively) containing ``.wav`` files.
    transcript_dir:
        Directory containing transcripts (``.lab``/``.txt``) and/or TextGrids.
        Defaults to ``audio_dir`` (the common single-folder corpus).
    aligned_dir:
        Optional separate directory holding force-aligned TextGrids (e.g. an
        MFA output folder).  TextGrids found here take priority when detecting
        alignment.
    """
    audio_root = Path(audio_dir).expanduser()
    transcript_root = Path(transcript_dir).expanduser() if transcript_dir else audio_root
    warnings: list[str] = []

    audios = _index_by_stem(audio_root, AUDIO_EXTENSIONS, warnings, "audio")
    transcripts = _index_by_stem(
        transcript_root, TRANSCRIPT_TEXT_EXTENSIONS, warnings, "transcript"
    )
    # TextGrids may be in the transcript dir, alongside audio, and/or a dedicated
    # aligned dir.  Later sources override earlier ones for the same stem so an
    # explicit ``aligned_dir`` wins.
    textgrids: dict[str, Path] = {}
    for source in (transcript_root, audio_root):
        textgrids.update(_index_by_stem(source, TEXTGRID_EXTENSIONS, warnings, "TextGrid"))
    if aligned_dir:
        aligned_root = Path(aligned_dir).expanduser()
        textgrids.update(_index_by_stem(aligned_root, TEXTGRID_EXTENSIONS, warnings, "TextGrid"))

    stems = sorted(set(audios) | set(transcripts) | set(textgrids))
    items: list[CorpusItem] = []
    for stem in stems:
        audio = audios.get(stem)
        transcript = transcripts.get(stem)
        textgrid = textgrids.get(stem)
        anchor = audio or transcript or textgrid
        speaker = _infer_speaker(anchor, audio_root if audio else transcript_root)
        aligned = bool(textgrid and is_aligned_textgrid(textgrid))
        items.append(
            CorpusItem(
                stem=stem,
                speaker=speaker,
                audio=audio,
                transcript=transcript,
                textgrid=textgrid,
                aligned=aligned,
            )
        )

    return CorpusInventory(
        items=items,
        audio_dir=audio_root,
        transcript_dir=transcript_root,
        warnings=warnings,
    )


def find_vowel_data(*search_dirs: str | os.PathLike) -> list[Path]:
    """Return candidate extracted-vowel CSV files under the given directories.

    We look for ``.csv`` files whose names hint at formant/vowel extraction
    output (``*vowel*``, ``*formant*``, ``*fave*``, ``*_norm*``) so the app can
    offer to skip straight to analysis when data already exists.
    """
    hints = ("vowel", "formant", "fave", "_norm", "tracks", "measurement")
    found: list[Path] = []
    seen: set[Path] = set()
    for d in search_dirs:
        if d is None:
            continue
        root = Path(d).expanduser()
        if not root.is_dir():
            continue
        for path in _iter_files(root, {".csv"}):
            name = path.name.lower()
            if any(h in name for h in hints) and path not in seen:
                seen.add(path)
                found.append(path)
    return sorted(found)
