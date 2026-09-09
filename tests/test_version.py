"""The version is declared in four places; a release bump must touch all of them.

`vowelchemy --version`, the sidebar and the update check read
``vowelchemy.__version__``; pip and the packaged app read ``pyproject.toml``;
GitHub's "Cite this repository" reads ``CITATION.cff``; the README shows a
sample of ``vowelchemy doctor``.  Bumping only ``pyproject.toml`` (as a
release tag tempts one to do) leaves the app announcing its own release as
an available update.
"""

import re
from pathlib import Path

from vowelchemy import __version__

ROOT = Path(__file__).resolve().parents[1]


def _first(pattern: str, text: str) -> str:
    match = re.search(pattern, text, re.MULTILINE)
    assert match, pattern
    return match.group(1)


def test_version_declared_consistently():
    pyproject = _first(r'^version = "([^"]+)"', (ROOT / "pyproject.toml").read_text())
    citation = _first(r"^version: (\S+)", (ROOT / "CITATION.cff").read_text())
    readme = _first(r"^  version   : (\S+)", (ROOT / "README.md").read_text())
    assert pyproject == __version__, "pyproject.toml and vowelchemy.__version__ differ"
    assert citation == __version__, "CITATION.cff and vowelchemy.__version__ differ"
    assert readme == __version__, "README's `vowelchemy doctor` sample shows another version"
