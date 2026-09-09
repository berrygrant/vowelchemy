"""scripts/bump_version.py keeps the four version declarations in step."""

import datetime as dt
import importlib.util
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "bump_version.py"


def _load():
    spec = importlib.util.spec_from_file_location("bump_version", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def repo_copy(tmp_path):
    """The four declaring files, copied so a test bump never touches the repo."""
    for rel in ("pyproject.toml", "CITATION.cff", "src/vowelchemy/__init__.py", "README.md"):
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / rel, dst)
    return tmp_path


def test_repo_declarations_agree():
    bv = _load()
    assert bv.check(ROOT) == []
    from vowelchemy import __version__

    assert set(bv.read_versions(ROOT).values()) == {__version__}


def test_bump_rewrites_every_spot_and_the_release_date(repo_copy):
    bv = _load()
    changed = bv.bump(repo_copy, "9.9.9", date=dt.date(2030, 1, 2))
    assert set(changed) == {"pyproject.toml", "CITATION.cff", "src/vowelchemy/__init__.py", "README.md"}
    assert set(bv.read_versions(repo_copy).values()) == {"9.9.9"}
    assert "date-released: 2030-01-02" in (repo_copy / "CITATION.cff").read_text()
    assert bv.check(repo_copy) == [] and bv.check(repo_copy, "v9.9.9") == []
    assert bv.bump(repo_copy, "9.9.9", date=dt.date(2030, 1, 2)) == []  # idempotent
    with pytest.raises(ValueError):
        bv.bump(repo_copy, "not-a-version")


def test_check_reports_disagreement_and_tag_mismatch(repo_copy):
    bv = _load()
    init = repo_copy / "src/vowelchemy/__init__.py"
    init.write_text(init.read_text().replace(bv.read_versions(repo_copy)["pyproject.toml"], "0.0.1"))
    problems = bv.check(repo_copy)
    assert len(problems) == 1 and "disagree" in problems[0] and "0.0.1" in problems[0]
    bv.bump(repo_copy, "1.2.0")
    assert bv.check(repo_copy, "v1.2") == []  # v1.2 is 1.2.0
    mismatch = bv.check(repo_copy, "v1.3.0")
    assert mismatch and "does not match" in mismatch[0] and "bump_version.py 1.3.0" in mismatch[0]


def test_cli_check_exit_codes(repo_copy, capsys):
    bv = _load()
    assert bv.main(["--check", "--root", str(repo_copy)]) == 0
    assert "agree" in capsys.readouterr().out
    assert bv.main(["9.9.9", "--root", str(repo_copy)]) == 0
    assert "Release on version bump" in capsys.readouterr().out
    assert bv.main(["--check", "v9.9.8", "--root", str(repo_copy)]) == 1
    assert "does not match" in capsys.readouterr().err
    # --print is what the release action reads; it refuses to print a
    # disagreeing set of declarations.
    assert bv.main(["--print", "--root", str(repo_copy)]) == 0
    assert capsys.readouterr().out.strip() == "9.9.9"
    init = repo_copy / "src/vowelchemy/__init__.py"
    init.write_text(init.read_text().replace("9.9.9", "9.9.8"))
    assert bv.main(["--print", "--root", str(repo_copy)]) == 1
    assert "disagree" in capsys.readouterr().err
