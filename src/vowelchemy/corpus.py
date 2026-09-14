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
import shutil
import subprocess
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

from .constants import (
    AUDIO_EXTENSIONS,
    PHONE_TIER_NAMES,
    TEXTGRID_EXTENSIONS,
    TRANSCRIPT_TEXT_EXTENSIONS,
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


# Filename fragments that mark a CSV as likely formant/vowel extraction output
# (new-fave's primary output is ``*_points.csv``). Shared by find_vowel_data
# and suggest_corpus_layout so the two detectors never drift apart.
VOWEL_CSV_HINTS = ("vowel", "formant", "fave", "tracks", "points", "measurement", "_norm")


def find_vowel_data(*search_dirs: str | os.PathLike) -> list[Path]:
    """Return candidate extracted-vowel CSV files under the given directories.

    We look for ``.csv`` files whose names match :data:`VOWEL_CSV_HINTS` so the
    app can offer to skip straight to analysis when data already exists.
    """
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
            if any(h in name for h in VOWEL_CSV_HINTS) and path not in seen:
                seen.add(path)
                found.append(path)
    return sorted(found)


# --------------------------------------------------------------------------- #
# Layout auto-detection (fuzzy: find the sub-folders that hold each field)
# --------------------------------------------------------------------------- #
_SPEAKER_CSV_RE = re.compile(r"speaker|demograph|meta|subject|participant|social|info", re.I)


@dataclass
class LayoutSuggestion:
    root: Path
    audio_dir: Optional[Path] = None
    transcript_dir: Optional[Path] = None
    aligned_dir: Optional[Path] = None
    speakers_csv: Optional[Path] = None
    n_wav: int = 0
    n_transcript: int = 0
    n_aligned: int = 0
    audio_dirs: list[Path] = field(default_factory=list)
    transcript_dirs: list[Path] = field(default_factory=list)
    aligned_dirs: list[Path] = field(default_factory=list)
    vowel_csvs: list[Path] = field(default_factory=list)

    def to_dict(self) -> dict:
        def s(p):
            return str(p) if p else None

        return {
            "root": str(self.root),
            "audio_dir": s(self.audio_dir),
            "transcript_dir": s(self.transcript_dir),
            "aligned_dir": s(self.aligned_dir),
            "speakers_csv": s(self.speakers_csv),
            "counts": {"wav": self.n_wav, "transcript": self.n_transcript, "aligned": self.n_aligned},
            "audio_dirs": [str(p) for p in self.audio_dirs],
            "transcript_dirs": [str(p) for p in self.transcript_dirs],
            "aligned_dirs": [str(p) for p in self.aligned_dirs],
            "vowel_csvs": [str(p) for p in self.vowel_csvs],
        }


def _common_ancestor(paths: list[Path], root: Path) -> Optional[Path]:
    if not paths:
        return None
    dirs = [str(p.parent) for p in paths]
    try:
        return Path(os.path.commonpath(dirs))
    except ValueError:
        return root


def suggest_corpus_layout(
    root: str | os.PathLike, max_files: int = 60000, max_sniff: int = 300
) -> LayoutSuggestion:
    """Scan ``root`` and guess which sub-folders hold audio / transcripts / alignments.

    Detection is content-based (which folders actually contain ``.wav`` files,
    transcripts, or *aligned* TextGrids), with each field's suggested folder set
    to the shallowest common ancestor of the matching files — so a corpus laid
    out as ``root/audio/<speaker>/*.wav`` resolves ``audio_dir`` to ``root/audio``.
    """
    root = Path(root).expanduser().resolve()
    wavs: list[Path] = []
    transcripts: list[Path] = []
    aligned: list[Path] = []
    csvs: list[Path] = []
    seen_files = 0
    sniffed = 0

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for fn in filenames:
            ext = os.path.splitext(fn)[1].lower()
            path = Path(dirpath) / fn
            if ext == ".wav":
                wavs.append(path)
            elif ext in {".lab", ".txt"}:
                transcripts.append(path)
            elif ext == ".textgrid":
                if sniffed < max_sniff:
                    sniffed += 1
                    (aligned if is_aligned_textgrid(path) else transcripts).append(path)
                else:
                    transcripts.append(path)  # assume unaligned once past the sniff budget
            elif ext in {".csv", ".tsv"}:
                csvs.append(path)
            seen_files += 1
        if seen_files > max_files:
            break

    audio_dir = _common_ancestor(wavs, root)
    transcript_dir = _common_ancestor(transcripts, root) or audio_dir
    aligned_dir = _common_ancestor(aligned, root)

    vowel_csvs = [p for p in csvs if any(h in p.name.lower() for h in VOWEL_CSV_HINTS)]
    speaker_csvs = [
        p for p in csvs if _SPEAKER_CSV_RE.search(p.name) and p not in vowel_csvs
    ]
    speakers_csv = speaker_csvs[0] if speaker_csvs else None

    def dirs_of(paths: list[Path]) -> list[Path]:
        return sorted({p.parent for p in paths})

    return LayoutSuggestion(
        root=root,
        audio_dir=audio_dir,
        transcript_dir=transcript_dir,
        aligned_dir=aligned_dir,
        speakers_csv=speakers_csv,
        n_wav=len(wavs),
        n_transcript=len(transcripts),
        n_aligned=len(aligned),
        audio_dirs=dirs_of(wavs)[:25],
        transcript_dirs=dirs_of(transcripts)[:25],
        aligned_dirs=dirs_of(aligned)[:25],
        vowel_csvs=sorted(vowel_csvs)[:25],
    )


# --------------------------------------------------------------------------- #
# Server-side directory browser (the app's backend runs on the user's machine)
# --------------------------------------------------------------------------- #
def _contains_ext(directory: Path, exts: tuple[str, ...], max_depth: int = 1) -> bool:
    """True if a file with one of ``exts`` exists in ``directory`` or, up to
    ``max_depth`` levels down, a sub-directory — so a parent ``audio/`` folder is
    flagged even when the ``.wav`` files sit in per-speaker sub-folders."""
    stack: list[tuple[Path, int]] = [(directory, 0)]
    scanned = 0
    while stack:
        d, depth = stack.pop()
        try:
            with os.scandir(d) as it:
                for e in it:
                    if e.is_file() and os.path.splitext(e.name)[1].lower() in exts:
                        return True
                    if e.is_dir() and depth < max_depth and not e.name.startswith("."):
                        stack.append((Path(e.path), depth + 1))
        except OSError:
            continue
        scanned += 1
        if scanned > 250:  # bound the work for huge trees
            break
    return False


def is_within_root(path: str | os.PathLike, root: Optional[str | os.PathLike]) -> bool:
    """True if ``path`` is ``root`` or nested under it (or ``root`` is None)."""
    if not root:
        return True
    root_p = Path(root).expanduser().resolve()
    p = Path(path).expanduser().resolve()
    return p == root_p or root_p in p.parents


def list_directory(
    path: Optional[str | os.PathLike] = None,
    exts: Optional[list[str]] = None,
    max_entries: int = 3000,
    root: Optional[str | os.PathLike] = None,
) -> dict:
    """List sub-directories (and optionally files of given extensions) of ``path``.

    Powers the "click to select a directory" picker. Defaults to ``root`` (or the
    user's home directory). When ``root`` is set the browser is *confined* to it
    — paths outside are clamped back to ``root`` and you cannot navigate above it.
    Each sub-directory is annotated with whether it contains audio or transcripts.
    """
    root_p = Path(root).expanduser().resolve() if root else None
    base = Path(path).expanduser().resolve() if path else (root_p or Path.home())
    if root_p is not None and not is_within_root(base, root_p):
        base = root_p  # clamp escapes back to the confinement root
    if not base.is_dir():
        raise NotADirectoryError(str(base))
    wanted = {("." + e.lstrip(".")).lower() for e in exts} if exts else None

    dirs: list[dict] = []
    files: list[dict] = []
    try:
        with os.scandir(base) as it:
            for entry in it:
                if entry.name.startswith("."):
                    continue
                try:
                    if entry.is_dir():
                        dp = Path(entry.path)
                        dirs.append({
                            "name": entry.name,
                            "path": str(dp),
                            "has_wav": _contains_ext(dp, (".wav",)),
                            "has_transcript": _contains_ext(dp, (".lab", ".txt", ".textgrid")),
                        })
                    elif wanted and os.path.splitext(entry.name)[1].lower() in wanted:
                        files.append({"name": entry.name, "path": entry.path})
                except OSError:
                    continue
                if len(dirs) + len(files) > max_entries:
                    break
    except PermissionError as exc:
        raise PermissionError(f"Cannot read {base}: {exc}") from exc

    dirs.sort(key=lambda d: d["name"].lower())
    files.sort(key=lambda f: f["name"].lower())
    if root_p is not None and base == root_p:
        parent = None  # can't navigate above the confinement root
    else:
        parent = str(base.parent) if base.parent != base else None
    home = str(root_p) if root_p is not None else str(Path.home())
    return {"path": str(base), "parent": parent, "home": home,
            "dirs": dirs, "files": files, "confined": root_p is not None}


# --------------------------------------------------------------------------- #
# Folders dropped on the app, and the system's own folder chooser
# --------------------------------------------------------------------------- #
# A browser never reveals where a dropped folder lives — only its name and, for
# a directory, its top-level listing. That is enough to find it: look in the
# places corpora live (Desktop, Documents, Downloads, home, mounted drives) for
# a folder with that name and prefer the one whose contents match the listing.
# Folders that never hold a corpus are skipped so the search stays quick.
_SKIP_DIR_NAMES = {
    "node_modules", "Library", ".venv", "venv", "__pycache__", "site-packages",
    "Applications", "System", "Windows", "Program Files", "Program Files (x86)",
    "AppData", "$RECYCLE.BIN", "System Volume Information", "lost+found",
    "proc", "sys", "dev", "Trash", ".Trash",
}
# macOS aliases and Windows shortcuts drop with a suffix on the target's name.
_ALIAS_SUFFIXES = (" alias", ".alias", " - shortcut", ".lnk", " shortcut")


def normalize_dropped_name(name: str) -> str:
    """The folder a dropped item stands for: an alias/shortcut sheds its suffix."""
    n = str(name).strip()
    lowered = n.lower()
    for suffix in _ALIAS_SUFFIXES:
        if lowered.endswith(suffix) and len(n) > len(suffix):
            return n[: -len(suffix)].rstrip()
    return n


def default_search_roots(root: Optional[str | os.PathLike] = None) -> list[Path]:
    """Where to look for a dropped folder, most likely first (or just ``root``)."""
    if root:
        return [Path(root).expanduser()]
    home = Path.home()
    roots = [home / d for d in ("Desktop", "Documents", "Downloads")] + [home]
    for mount in (Path("/Volumes"), Path("/mnt"), Path("/media"), Path("/run/media")):
        try:
            if mount.is_dir():
                roots += sorted(p for p in mount.iterdir() if p.is_dir())
        except OSError:
            continue
    if sys.platform == "win32":
        roots += [Path(f"{d}:\\") for d in "DEFGHIJKLMNOPQRSTUVWXYZ" if Path(f"{d}:\\").is_dir()]
    roots.append(Path.cwd())
    out: list[Path] = []
    seen: set[Path] = set()
    for r in roots:
        try:
            resolved = r.resolve()
        except OSError:
            continue
        if resolved.is_dir() and resolved not in seen:
            seen.add(resolved)
            out.append(r)
    return out


def _listing_overlap(directory: Path, sample: set[str], cap: int = 5000) -> tuple[float, int, int]:
    """``(score, matched, total)``: how much of the dropped listing this folder holds."""
    if not sample:
        return 0.5, 0, 0
    names: set[str] = set()
    try:
        with os.scandir(directory) as it:
            for i, entry in enumerate(it):
                names.add(entry.name)
                if i >= cap:
                    break
    except OSError:
        return 0.0, 0, len(sample)
    matched = len(sample & names)
    return matched / len(sample), matched, len(sample)


def locate_folder(
    name: str,
    entries: Optional[Iterable[str]] = None,
    kind: str = "directory",
    roots: Optional[Iterable[str | os.PathLike]] = None,
    root: Optional[str | os.PathLike] = None,
    max_depth: int = 5,
    time_budget: float = 4.0,
    limit: int = 20,
) -> list[dict]:
    """Candidate locations for a folder someone dropped on the app.

    ``kind="directory"`` finds folders named ``name`` (alias suffixes removed)
    and scores each by how many of the dropped top-level ``entries`` it holds;
    ``kind="file"`` finds folders *containing* a file named ``name`` (the
    dropped item was a file, e.g. a recording inside the corpus) and reports
    that file too.  Searches ``roots`` (default: :func:`default_search_roots`,
    or just ``root`` when the browser is confined) breadth-first to
    ``max_depth``, skipping hidden and system folders, within ``time_budget``
    seconds.  Each candidate: ``path``, ``score`` (1.0 = every dropped entry
    found), ``matched``, ``total``, ``depth`` and, for files, ``file``.
    """
    wanted = normalize_dropped_name(name)
    if not wanted:
        return []
    wanted_lower = wanted.lower()
    sample = {e for e in (entries or []) if e}
    deadline = time.monotonic() + time_budget
    search_roots = [Path(r) for r in roots] if roots else default_search_roots(root)

    results: list[dict] = []
    found: set[Path] = set()
    visited: set[Path] = set()

    def add(path: Path, score: float, matched: int, total: int, file: Optional[Path] = None) -> None:
        try:
            key = path.resolve()
        except OSError:
            return
        if key in found:
            return
        found.add(key)
        entry = {"path": str(path), "score": round(score, 3), "matched": matched, "total": total,
                 "depth": len(path.parts)}
        if file is not None:
            entry["file"] = str(file)
        results.append(entry)

    for start in search_roots:
        queue: deque[tuple[Path, int]] = deque([(start, 0)])
        while queue:
            if time.monotonic() > deadline or len(results) >= limit * 3:
                break
            directory, depth = queue.popleft()
            try:
                key = directory.resolve()
            except OSError:
                continue
            if key in visited:
                continue
            visited.add(key)
            try:
                with os.scandir(directory) as it:
                    children = list(it)
            except OSError:
                continue
            for child in children:
                try:
                    is_dir = child.is_dir(follow_symlinks=False)
                except OSError:
                    continue
                if not is_dir:
                    if kind == "file" and child.name.lower() == wanted_lower:
                        add(directory, 1.0, 1, 1, file=Path(child.path))
                    continue
                if kind == "directory" and child.name.lower() == wanted_lower:
                    add(Path(child.path), *_listing_overlap(Path(child.path), sample))
                if (depth < max_depth and not child.name.startswith(".")
                        and child.name not in _SKIP_DIR_NAMES):
                    queue.append((Path(child.path), depth + 1))

    results.sort(key=lambda r: (-r["score"], r["depth"], r["path"].lower()))
    return results[:limit]


def _powershell() -> Optional[str]:
    return shutil.which("powershell") or shutil.which("pwsh")


def native_dialog_available() -> bool:
    """Can this machine show its own folder chooser (osascript / PowerShell / zenity …)?"""
    if sys.platform == "darwin":
        return shutil.which("osascript") is not None
    if sys.platform == "win32":
        return _powershell() is not None
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        return False
    if shutil.which("zenity") or shutil.which("kdialog"):
        return True
    if getattr(sys, "frozen", False):
        return False  # the packaged app cannot run `python -c` for a tkinter dialog
    import importlib.util

    return importlib.util.find_spec("tkinter") is not None


def _native_dialog_command(title: str, start: Optional[str], mode: str) -> Optional[list[str]]:
    """The subprocess that shows the dialog and prints the chosen path."""
    want_file = mode == "file"
    if sys.platform == "darwin":
        if not shutil.which("osascript"):
            return None
        esc = title.replace("\\", "\\\\").replace('"', '\\"')
        line = f'set chosen to choose {"file" if want_file else "folder"} with prompt "{esc}"'
        if start:
            start_esc = start.replace("\\", "\\\\").replace('"', '\\"')
            line += f' default location POSIX file "{start_esc}"'
        return ["osascript", "-e", line, "-e", "POSIX path of chosen"]
    if sys.platform == "win32":
        ps = _powershell()
        if not ps:
            return None
        q = lambda s: s.replace("'", "''")  # noqa: E731
        lines = [
            "Add-Type -AssemblyName System.Windows.Forms",
            "$owner = New-Object System.Windows.Forms.Form",
            "$owner.TopMost = $true",
        ]
        if want_file:
            lines += [
                "$d = New-Object System.Windows.Forms.OpenFileDialog",
                f"$d.Title = '{q(title)}'",
            ] + ([f"$d.InitialDirectory = '{q(start)}'"] if start else []) + [
                "if ($d.ShowDialog($owner) -eq [System.Windows.Forms.DialogResult]::OK) { Write-Output $d.FileName }",
            ]
        else:
            lines += [
                "$d = New-Object System.Windows.Forms.FolderBrowserDialog",
                f"$d.Description = '{q(title)}'",
                "$d.ShowNewFolderButton = $false",
            ] + ([f"$d.SelectedPath = '{q(start)}'"] if start else []) + [
                "if ($d.ShowDialog($owner) -eq [System.Windows.Forms.DialogResult]::OK) { Write-Output $d.SelectedPath }",
            ]
        return [ps, "-NoProfile", "-STA", "-Command", "; ".join(lines)]
    if shutil.which("zenity"):
        cmd = ["zenity", "--file-selection", f"--title={title}"]
        if not want_file:
            cmd.append("--directory")
        if start:
            cmd.append(f"--filename={start.rstrip('/')}/")
        return cmd
    if shutil.which("kdialog"):
        flag = "--getopenfilename" if want_file else "--getexistingdirectory"
        return ["kdialog", flag, start or str(Path.home()), "--title", title]
    if getattr(sys, "frozen", False):
        return None
    script = (
        "import tkinter, tkinter.filedialog as fd; r = tkinter.Tk(); r.withdraw(); "
        "r.attributes('-topmost', True); "
        f"print(fd.{'askopenfilename' if want_file else 'askdirectory'}(title={title!r}"
        + (f", initialdir={start!r}" if start else "") + ") or '')"
    )
    return [sys.executable, "-c", script]


def native_folder_dialog(
    title: str = "Choose a folder",
    start: Optional[str | os.PathLike] = None,
    mode: str = "dir",
    timeout: float = 600.0,
) -> Optional[str]:
    """Show the operating system's own folder (or file) chooser; ``None`` if cancelled.

    The server runs on the user's machine, so the dialog appears on their
    screen — the most accurate way to point the app at a folder.  Raises
    ``RuntimeError`` when no dialog can be shown here.
    """
    start_dir = None
    if start:
        p = Path(start).expanduser()
        start_dir = str(p if p.is_dir() else p.parent) if (p.is_dir() or p.parent.is_dir()) else None
    cmd = _native_dialog_command(title, start_dir, mode)
    if cmd is None:
        raise RuntimeError("No system folder dialog is available on this machine — "
                           "use Browse… or type the path.")
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(f"Could not open the folder dialog: {exc}") from exc
    lines = [ln.strip() for ln in res.stdout.splitlines() if ln.strip()]
    chosen = lines[-1] if lines else ""
    if not chosen:
        cancelled = res.returncode in (0, 1) or "cancel" in (res.stderr or "").lower()
        if not cancelled:
            raise RuntimeError((res.stderr or "").strip()
                               or f"The folder dialog failed (exit {res.returncode}).")
        return None
    return os.path.normpath(chosen)
