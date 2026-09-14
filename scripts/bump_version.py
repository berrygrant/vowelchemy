#!/usr/bin/env python3
"""Bump — or check — Vowelchemy's version everywhere it is declared.

    python scripts/bump_version.py 0.3.3          # rewrite every declaration
    python scripts/bump_version.py --check        # do they all agree?
    python scripts/bump_version.py --check v0.3.3 # …and match this release tag?
    python scripts/bump_version.py --print        # the declared version (for CI)

The version lives in four places: ``pyproject.toml`` (pip and the packaged
app), ``CITATION.cff`` (GitHub's "Cite this repository"; its release date is
updated too), ``src/vowelchemy/__init__.py`` (what the app, ``vowelchemy
--version`` and the update check report) and the ``vowelchemy doctor``
sample in ``README.md``.  Bumping only one of them leaves the app
announcing its own release as an available update, so the release build
refuses a tag that does not match, and ``tests/test_version.py`` fails when
the four disagree.  No third-party dependencies: this runs before anything
is installed.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# (file, regex with three groups: prefix, version, suffix)
SPOTS = [
    ("pyproject.toml", r'^(version = ")([^"]+)(")'),
    ("CITATION.cff", r"^(version: )(\S+)()"),
    ("src/vowelchemy/__init__.py", r'^(__version__ = ")([^"]+)(")'),
    ("README.md", r"^(  version   : )(\S+)()"),
]
DATE_SPOT = ("CITATION.cff", r"^(date-released: )(\S+)()")
VERSION_RE = re.compile(r"^\d+\.\d+(\.\d+)?([a-z]+\d*)?$")


def _sub(text: str, pattern: str, value: str) -> tuple[str, int]:
    return re.subn(pattern, lambda m: f"{m.group(1)}{value}{m.group(3)}", text, count=1,
                   flags=re.MULTILINE)


def normalize(version: str) -> tuple[tuple[int, ...], str]:
    """``"v0.3"`` and ``"0.3.0"`` compare equal; a suffix like ``rc1`` is kept."""
    s = str(version).strip().lstrip("vV")
    m = re.match(r"(\d+(?:\.\d+)*)(.*)", s)
    if not m:
        return ((), s)
    nums = [int(p) for p in m.group(1).split(".")]
    while len(nums) > 1 and nums[-1] == 0:
        nums.pop()
    return (tuple(nums), m.group(2).strip())


def read_versions(root: Path = ROOT) -> dict[str, str | None]:
    """The version each declaration currently carries (``None`` if not found)."""
    found: dict[str, str | None] = {}
    for rel, pattern in SPOTS:
        text = (root / rel).read_text(encoding="utf-8")
        m = re.search(pattern, text, re.MULTILINE)
        found[rel] = m.group(2) if m else None
    return found


def check(root: Path = ROOT, tag: str | None = None) -> list[str]:
    """Problems with the declarations (empty list = consistent)."""
    found = read_versions(root)
    problems = [f"{rel}: no version declaration found" for rel, v in found.items() if v is None]
    versions = {v for v in found.values() if v}
    if len(versions) > 1:
        detail = ", ".join(f"{rel} = {v}" for rel, v in found.items())
        problems.append(f"the declarations disagree: {detail}")
    if tag is not None and versions:
        declared = next(iter(versions))
        if normalize(tag) != normalize(declared):
            problems.append(
                f"tag {tag} does not match the declared version {declared}; run "
                f"`python scripts/bump_version.py {tag.lstrip('vV')}` and commit before tagging"
            )
    return problems


def bump(root: Path, new: str, date: dt.date | None = None) -> list[str]:
    """Rewrite every declaration to ``new``; returns the files changed."""
    if not VERSION_RE.match(new):
        raise ValueError(f"{new!r} is not a version like 0.3.3 (or 0.4.0rc1)")
    changed: list[str] = []
    for rel, pattern in SPOTS:
        path = root / rel
        text = path.read_text(encoding="utf-8")
        updated, n = _sub(text, pattern, new)
        if n == 0:
            raise ValueError(f"{rel}: no version declaration found")
        if updated != text:
            path.write_text(updated, encoding="utf-8")
            changed.append(rel)
    rel, pattern = DATE_SPOT
    path = root / rel
    text = path.read_text(encoding="utf-8")
    updated, n = _sub(text, pattern, (date or dt.date.today()).isoformat())
    if n and updated != text:
        path.write_text(updated, encoding="utf-8")
        if rel not in changed:
            changed.append(rel)
    return changed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("version", nargs="?", help="new version, e.g. 0.3.3")
    parser.add_argument("--check", nargs="?", const=True, metavar="TAG",
                        help="verify the declarations agree (and match TAG, e.g. v0.3.3)")
    parser.add_argument("--print", action="store_true", dest="print_version",
                        help="print the declared version (after checking it agrees) and exit")
    parser.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.print_version:
        problems = check(args.root)
        if problems:
            for p in problems:
                print(f"error: {p}", file=sys.stderr)
            return 1
        print(next(v for v in read_versions(args.root).values() if v))
        return 0

    if args.check is not None:
        tag = None if args.check is True else args.check
        problems = check(args.root, tag)
        current = read_versions(args.root)
        if problems:
            print("Version check failed:", file=sys.stderr)
            for p in problems:
                print(f"  - {p}", file=sys.stderr)
            return 1
        print(f"Version declarations agree: {next(iter(current.values()))}"
              + (f" (matches tag {tag})" if tag else ""))
        return 0

    if not args.version:
        parser.error("give a version to bump to, or --check")
    try:
        changed = bump(args.root, args.version)
    except ValueError as exc:
        parser.error(str(exc))
    for rel in changed:
        print(f"updated {rel}")
    if not changed:
        print(f"already at {args.version}")
    print(
        f"\nNext:\n  git commit -am 'Bump version to {args.version}' && git push\n"
        f"Once that lands on main, the 'Release on version bump' action tags v{args.version}, "
        "builds the desktop apps and publishes the GitHub release the in-app update check reads."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
