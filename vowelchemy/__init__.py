"""Vowelchemy: turn conversational speech corpora into analyzable vowel data.

The package is intentionally split into a light-weight *library* (corpus
discovery, normalization, analysis, metrics, visualization) that has only
scientific-Python dependencies, and a FastAPI *backend* (:mod:`vowelchemy.api`)
that serves both the JSON API and the built React front-end — launched with
``vowelchemy app``.

Importing :mod:`vowelchemy` does **not** import FastAPI, so the library can be
used from scripts, notebooks, and tests without the web stack.
"""

from pathlib import Path
from typing import Optional

__version__ = "0.1.0"


def webui_dir() -> Optional[Path]:
    """Locate the built React UI, or ``None`` if it hasn't been built.

    The production build lives *inside* the package (``vowelchemy/webui``) so
    it ships in the wheel; a dev checkout that predates a build may still have
    the legacy ``frontend/dist`` next to the package, which we accept too.
    """
    packaged = Path(__file__).resolve().parent / "webui"
    if (packaged / "index.html").is_file():
        return packaged
    legacy = Path(__file__).resolve().parent.parent / "frontend" / "dist"
    if (legacy / "index.html").is_file():
        return legacy
    return None


__all__ = ["__version__", "webui_dir"]
