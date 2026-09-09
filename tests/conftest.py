import pytest


@pytest.fixture(autouse=True)
def no_update_check(monkeypatch):
    """Tests never talk to GitHub; tests of the check itself inject a fetcher."""
    monkeypatch.setenv("VOWELCHEMY_NO_UPDATE_CHECK", "1")
