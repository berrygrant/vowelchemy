import sys

import pytest

from vowelchemy import __version__, updates


@pytest.fixture
def online(monkeypatch, tmp_path):
    """Undo the suite-wide opt-out so the check runs (with an injected fetcher)."""
    monkeypatch.delenv("VOWELCHEMY_NO_UPDATE_CHECK", raising=False)
    monkeypatch.setenv("VOWELCHEMY_HOME", str(tmp_path / "state"))
    updates.invalidate()
    yield
    updates.invalidate()


def test_parse_version_orders_tags_like_releases():
    v = updates.parse_version
    assert v("v0.3") == v("0.3.0") == ((0, 3), 1)
    assert v("0.3.1") > v("v0.3") > v("0.2.1") > v("0.2")
    assert v("0.3.1rc1") < v("0.3.1") and v("0.3.1rc1") > v("0.3")
    assert v("1.0.0-beta.2") < v("1.0.0")
    assert v("nonsense") < v("0.0.1") and v(None) == ((), 0)
    assert v("v10.2") > v("v9.9.9")


def test_update_available_when_a_newer_release_exists(online):
    info = updates.check_updates(current="0.3.0", fetch=lambda: ("v0.4.0", "https://x/rel/v0.4.0"))
    assert info.checked and info.update_available and info.latest == "0.4.0"
    assert info.url == "https://x/rel/v0.4.0" and info.error is None
    assert "0.4.0" in updates.update_hint(info) and "https://x/rel/v0.4.0" in updates.update_hint(info)
    same = updates.check_updates(current="0.4.0", fetch=lambda: ("v0.4", "u"))
    assert same.checked and not same.update_available
    assert "Up to date" in updates.update_hint(same)
    newer_local = updates.check_updates(current="0.5.0.dev0", fetch=lambda: ("v0.4.0", "u"))
    assert not newer_local.update_available  # a dev build ahead of the release is not "outdated"


def test_check_never_raises_offline(online):
    def boom():
        raise OSError("no network")

    info = updates.check_updates(current="0.3.0", fetch=boom)
    assert info.checked and not info.update_available and "OSError" in info.error
    assert "offline" in updates.update_hint(info)
    assert info.as_dict()["hint"] == updates.update_hint(info)


def test_opt_out_env_and_setting(online, monkeypatch):
    monkeypatch.setenv("VOWELCHEMY_NO_UPDATE_CHECK", "1")
    info = updates.check_updates(fetch=lambda: ("v9.9", "u"))
    assert info.disabled and info.checked and not info.update_available
    assert "off" in updates.update_hint(info)
    monkeypatch.delenv("VOWELCHEMY_NO_UPDATE_CHECK")
    from vowelchemy import toolenv

    toolenv.write_settings({"check_updates": False})
    assert updates.is_disabled()
    assert updates.cached_update_check().disabled


def test_cached_check_returns_placeholder_then_answer(online, monkeypatch):
    calls = []

    def fetch():
        calls.append(1)
        return ("v0.4.0", "u")

    monkeypatch.setattr(updates, "fetch_latest", fetch)
    first = updates.cached_update_check(wait=True)
    assert first.checked and first.update_available and first.current == __version__
    again = updates.cached_update_check()
    assert again is first and len(calls) == 1  # fresh answers are reused
    updates.invalidate()
    placeholder = updates.cached_update_check()  # background refresh: no waiting
    assert isinstance(placeholder, updates.UpdateInfo)
    assert updates.cached_update_check(wait=True).checked


def test_hint_tells_frozen_apps_to_download(online, monkeypatch):
    info = updates.check_updates(current="0.3.0", fetch=lambda: ("v0.4.0", "https://x/rel"))
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert "download" in updates.update_hint(info).lower()
    monkeypatch.delattr(sys, "frozen")
    assert "git pull" in updates.update_hint(info)


def test_cli_prints_version(capsys):
    from vowelchemy import cli

    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])
    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == f"vowelchemy {__version__}"
