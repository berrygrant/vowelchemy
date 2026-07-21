"""On-disk named projects so work survives a server restart (R10).

A project is a small folder holding the analysis *recipe* (config) plus the
loaded data (vowels / speakers / tracks) as CSVs. Projects live under
``~/.vowelchemy/projects`` by default (override with ``VOWELCHEMY_PROJECTS_DIR``).
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Optional

import pandas as pd


def projects_root() -> Path:
    root = os.environ.get("VOWELCHEMY_PROJECTS_DIR")
    p = Path(root).expanduser() if root else Path.home() / ".vowelchemy" / "projects"
    p.mkdir(parents=True, exist_ok=True)
    return p


def safe_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", (name or "").strip()) or "project"
    return cleaned[:80]


def save_project(
    name: str,
    recipe: dict,
    vowel_df: Optional[pd.DataFrame] = None,
    demographics: Optional[pd.DataFrame] = None,
    tracks_df: Optional[pd.DataFrame] = None,
) -> Path:
    d = projects_root() / safe_name(name)
    d.mkdir(parents=True, exist_ok=True)
    (d / "recipe.json").write_text(json.dumps(recipe, indent=2))
    if vowel_df is not None:
        vowel_df.to_csv(d / "vowels.csv", index=False)
    if demographics is not None:
        demographics.to_csv(d / "speakers.csv", index=False)
    if tracks_df is not None:
        tracks_df.to_csv(d / "tracks.csv", index=False)
    return d


def list_projects() -> list[dict]:
    root = projects_root()
    out: list[dict] = []
    for d in root.iterdir():
        if d.is_dir() and (d / "recipe.json").exists():
            out.append({
                "name": d.name,
                "has_vowels": (d / "vowels.csv").exists(),
                "has_tracks": (d / "tracks.csv").exists(),
                "modified": os.path.getmtime(d),
            })
    return sorted(out, key=lambda x: x["modified"], reverse=True)


def load_project(name: str) -> dict:
    d = projects_root() / safe_name(name)
    if not (d / "recipe.json").exists():
        raise FileNotFoundError(f"No saved project named '{name}'.")
    recipe = json.loads((d / "recipe.json").read_text())

    def _read(fname: str) -> Optional[pd.DataFrame]:
        p = d / fname
        return pd.read_csv(p) if p.exists() else None

    return {
        "recipe": recipe,
        "vowel_df": _read("vowels.csv"),
        "demographics": _read("speakers.csv"),
        "tracks_df": _read("tracks.csv"),
    }
