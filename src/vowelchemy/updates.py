"""Which Vowelchemy is this, and is there a newer one?

The app shows its version in the sidebar and in ``vowelchemy --version`` /
``vowelchemy doctor``, and — once per session, off the request path — asks
GitHub for the newest release so a lab machine running last term's build says
so.  The check is a single anonymous request to the public releases API, it
fails silently offline, and it can be switched off with
``VOWELCHEMY_NO_UPDATE_CHECK=1`` (or ``"check_updates": false`` in
``~/.vowelchemy/settings.json``).
"""

from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Callable, Optional
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from . import toolenv

REPO = "berrygrant/vowelchemy"
RELEASES_URL = f"https://github.com/{REPO}/releases"
LATEST_API = f"https://api.github.com/repos/{REPO}/releases/latest"
TAGS_API = f"https://api.github.com/repos/{REPO}/tags"
OPT_OUT_ENV = "VOWELCHEMY_NO_UPDATE_CHECK"
CHECK_TTL = 6 * 3600  # re-ask GitHub at most every six hours


def current_version() -> str:
    from . import __version__

    return __version__


def parse_version(text: object) -> tuple[tuple[int, ...], int]:
    """Sortable key for a version or tag: ``"v0.3.1rc1"`` → ``((0, 3, 1), 0)``.

    Trailing zeros are dropped so ``v0.3`` equals ``0.3.0``; the second element
    is 0 for a pre-release (a/b/rc/dev) and 1 for a final release, so
    ``0.3.1rc1 < 0.3.1``.  Anything unparseable sorts below every version.
    """
    s = str(text or "").strip().lstrip("vV")
    m = re.match(r"(\d+(?:\.\d+)*)(.*)", s)
    if not m:
        return ((), 0)
    nums = [int(p) for p in m.group(1).split(".")]
    while len(nums) > 1 and nums[-1] == 0:
        nums.pop()
    pre = bool(re.match(r"[-._]?(a|b|rc|alpha|beta|dev|pre)", m.group(2).strip().lower()))
    return (tuple(nums), 0 if pre else 1)


@dataclass
class UpdateInfo:
    current: str = field(default_factory=current_version)
    latest: Optional[str] = None
    url: str = RELEASES_URL
    update_available: bool = False
    checked: bool = False  # a check has finished (successfully or not)
    error: Optional[str] = None
    disabled: bool = False
    checked_at: Optional[float] = None

    def as_dict(self) -> dict:
        d = asdict(self)
        d["hint"] = update_hint(self)
        return d


def is_disabled() -> bool:
    if os.environ.get(OPT_OUT_ENV, "").strip().lower() in ("1", "true", "yes", "on"):
        return True
    return toolenv.read_settings().get("check_updates") is False


def fetch_latest(timeout: float = 4.0) -> tuple[str, str]:
    """``(tag, url)`` of the newest GitHub release, falling back to the newest tag."""
    headers = {"User-Agent": f"vowelchemy/{current_version()}",
               "Accept": "application/vnd.github+json"}
    try:
        with urlopen(Request(LATEST_API, headers=headers), timeout=timeout) as resp:
            data = json.load(resp)
        tag = data.get("tag_name") or data.get("name")
        if tag:
            return str(tag), str(data.get("html_url") or RELEASES_URL)
    except HTTPError as exc:
        if exc.code != 404:  # 404: no release published yet — tags may still exist
            raise
    with urlopen(Request(TAGS_API, headers=headers), timeout=timeout) as resp:
        tags = json.load(resp)
    names = [t.get("name") for t in tags if isinstance(t, dict) and t.get("name")]
    if not names:
        raise ValueError("no releases or tags found")
    best = max(names, key=parse_version)
    return str(best), f"{RELEASES_URL}/tag/{best}"


def check_updates(
    current: Optional[str] = None,
    fetch: Optional[Callable[[], tuple[str, str]]] = None,
) -> UpdateInfo:
    """Compare ``current`` with the newest release; never raises."""
    info = UpdateInfo(current=current or current_version())
    if is_disabled():
        info.disabled = True
        info.checked = True
        return info
    try:
        tag, url = (fetch or fetch_latest)()
    except Exception as exc:  # offline, rate-limited, odd payload — all fine
        info.error = f"{type(exc).__name__}: {exc}"[:200]
    else:
        info.latest = str(tag).strip().lstrip("vV")
        info.url = url
        info.update_available = parse_version(tag) > parse_version(info.current)
    info.checked = True
    info.checked_at = time.time()
    return info


_CACHE: dict[str, Optional[UpdateInfo]] = {"info": None}
_INFLIGHT = threading.Lock()


def cached_update_check(wait: bool = False) -> UpdateInfo:
    """The most recent check, refreshed at most every :data:`CHECK_TTL` seconds.

    ``wait=False`` returns the last answer (or an unchecked placeholder) and
    refreshes in the background, so a status request never waits on GitHub.
    """
    if is_disabled():
        return UpdateInfo(disabled=True, checked=True)
    info = _CACHE["info"]
    fresh = (info is not None and info.checked and not info.disabled
             and (time.time() - (info.checked_at or 0)) < CHECK_TTL)
    if fresh:
        return info
    if wait:
        info = check_updates()
        _CACHE["info"] = info
        return info
    if _INFLIGHT.acquire(blocking=False):
        def run() -> None:
            try:
                _CACHE["info"] = check_updates()
            finally:
                _INFLIGHT.release()

        threading.Thread(target=run, daemon=True).start()
    return info if info is not None else UpdateInfo()


def invalidate() -> None:
    _CACHE["info"] = None


def update_hint(info: UpdateInfo) -> str:
    """One line for the sidebar tooltip, ``doctor`` and the app banner."""
    if info.disabled:
        return f"Update checks are off ({OPT_OUT_ENV})."
    if not info.checked:
        return "Checking for a newer release…"
    if info.error:
        return "Could not check for updates (offline?)."
    if not info.update_available:
        return f"Up to date (newest release: {info.latest})."
    if getattr(sys, "frozen", False):
        return f"Vowelchemy {info.latest} is out — download it from {info.url}"
    return (f"Vowelchemy {info.latest} is out — {info.url} . Re-download the ZIP (the "
            "launcher updates itself), or `git pull` and `pip install .`.")
