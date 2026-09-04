"""Tests for borrowing MFA / new-fave from another environment.

The scenario these protect: a student double-clicks a launcher (so the app's
own venv is *not* on PATH) and has MFA in a conda environment somewhere else.
"""

import stat
import sys

import pytest

from vowelchemy import toolenv


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """Keep settings and discovery away from the real machine."""
    monkeypatch.setenv("VOWELCHEMY_HOME", str(tmp_path / "state"))
    monkeypatch.delenv("VOWELCHEMY_TOOL_ENV", raising=False)
    monkeypatch.setattr(toolenv.Path, "home", staticmethod(lambda: tmp_path / "home"))
    (tmp_path / "home").mkdir()
    return tmp_path


def make_env(prefix, *tools, bindir="bin"):
    """Create a fake environment prefix holding executable stubs."""
    b = prefix / bindir
    b.mkdir(parents=True, exist_ok=True)
    for tool in tools:
        exe = b / toolenv.TOOL_EXECUTABLES[tool]
        exe.write_text(f"#!/bin/sh\necho '{tool} 9.9.9'\n")
        exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    return prefix


def test_tools_in_finds_executables(tmp_path):
    env = make_env(tmp_path / "aligner", "mfa")
    found = toolenv.tools_in(env)
    assert set(found) == {"mfa"}
    assert found["mfa"].endswith("/mfa")
    assert toolenv.tools_in(tmp_path / "empty") == {}


def test_select_resolve_and_clear(tmp_path):
    env = make_env(tmp_path / "aligner", "mfa", "newfave")
    assert toolenv.selected_prefix() is None

    assert set(toolenv.set_selected_prefix(str(env))) == {"mfa", "newfave"}
    assert toolenv.selected_prefix() == env
    assert toolenv.resolve("mfa") == str(env / "bin" / "mfa")
    # the borrowed bin dir is prepended to PATH for subprocesses
    assert str(env / "bin") in toolenv.subprocess_env()["PATH"].split(":")

    toolenv.set_selected_prefix(None)
    assert toolenv.selected_prefix() is None


def test_selection_survives_a_new_process(tmp_path):
    """The choice is persisted, not just held in memory."""
    env = make_env(tmp_path / "aligner", "mfa")
    toolenv.set_selected_prefix(str(env))
    assert toolenv.read_settings()["tool_env"] == str(env)
    assert toolenv.settings_path().is_file()


def test_selecting_a_folder_without_tools_is_rejected(tmp_path):
    empty = tmp_path / "nothing"
    empty.mkdir()
    with pytest.raises(ValueError, match="doesn't contain"):
        toolenv.set_selected_prefix(str(empty))
    assert toolenv.selected_prefix() is None  # nothing stored


def test_env_var_overrides_stored_setting(tmp_path, monkeypatch):
    stored = make_env(tmp_path / "stored", "mfa")
    override = make_env(tmp_path / "override", "mfa")
    toolenv.set_selected_prefix(str(stored))
    monkeypatch.setenv("VOWELCHEMY_TOOL_ENV", str(override))
    assert toolenv.selected_prefix() == override


def test_status_reports_a_borrowed_tool(tmp_path):
    """The end-to-end payoff: alignment sees MFA once an env is chosen."""
    from vowelchemy import alignment

    assert alignment.mfa_status().available is False
    toolenv.set_selected_prefix(str(make_env(tmp_path / "aligner", "mfa")))
    status = alignment.mfa_status()
    assert status.available is True
    assert "9.9.9" in (status.version or "")


def test_discovery_finds_conda_environments(isolated_home):
    home = isolated_home / "home"
    make_env(home / "miniforge3" / "envs" / "aligner", "mfa")
    make_env(home / "miniconda3" / "envs" / "extract", "newfave")
    (home / "miniforge3" / "envs" / "empty").mkdir(parents=True)

    envs = {e.name: e for e in toolenv.discover_environments(use_conda_cli=False)}
    assert "aligner" in envs and envs["aligner"].tools.keys() == {"mfa"}
    assert "extract" in envs and envs["extract"].tools.keys() == {"newfave"}
    assert "empty" not in envs  # nothing installed there


def test_discovery_ranks_the_selection_first(isolated_home):
    home = isolated_home / "home"
    make_env(home / "miniforge3" / "envs" / "zulu", "newfave")
    chosen = make_env(home / "miniforge3" / "envs" / "alpha", "newfave")
    toolenv.set_selected_prefix(str(chosen))
    envs = toolenv.discover_environments(use_conda_cli=False)
    assert envs[0].name == "alpha"


def test_own_environment_is_searched(tmp_path, monkeypatch):
    """A launcher runs the app without activating its venv, so sys.executable's
    directory must be searched or a pip-installed fave-extract stays invisible."""
    fake_venv = tmp_path / "venv" / "bin"
    fake_venv.mkdir(parents=True)
    exe = fake_venv / "fave-extract"
    exe.write_text("#!/bin/sh\necho 'new-fave 1.3.0'\n")
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setattr(sys, "executable", str(fake_venv / "python"))
    assert toolenv.resolve("fave-extract") == str(exe)


def test_pip_plan_offers_newfave_but_never_mfa():
    cmd, reason = toolenv.pip_install_plan("mfa")
    assert cmd is None and "conda" in reason.lower()

    cmd, reason = toolenv.pip_install_plan("newfave")
    if sys.version_info >= (3, 10):
        assert cmd and cmd[:4] == [sys.executable, "-m", "pip", "install"]
        assert cmd[-1] == "new-fave"
    else:
        assert cmd is None and "3.10" in reason


def test_pip_plan_refuses_inside_a_frozen_app(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    cmd, reason = toolenv.pip_install_plan("newfave")
    assert cmd is None and "packaged app" in reason


def test_app_info_reports_running_code():
    info = toolenv.app_info()
    assert info["version"] and info["python"]
    assert info["location"].endswith("vowelchemy")
