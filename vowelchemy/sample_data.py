"""Synthetic vowel data for demos and tests.

Generates a realistic-looking extracted-vowel table plus a matching speaker
demographics table, without needing any audio, MFA, or new-fave.  The data
deliberately encodes two sociolinguistic signals so the plots and separation
metrics have something to show:

* **A stable, well-separated contrast**: BEET (IY) vs BET (EH) — the user's
  running example — with a large F1 difference in every group.
* **An age-graded low-back merger**: LOT (AA) and THOUGHT (AO) are distinct for
  older speakers and increasingly overlapped for younger ones, so JSD-based
  separation drops across apparent time.

Everything is seeded, so output is reproducible for tests.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

# Approximate adult formant targets in Hz (male-ish baseline), F1, F2, F3.
_VOWEL_TARGETS: dict[str, tuple[float, float, float]] = {
    "IY": (300, 2300, 3000),
    "IH": (430, 1990, 2550),
    "EH": (600, 1850, 2500),
    "AE": (750, 1750, 2450),
    "AA": (760, 1150, 2550),
    "AO": (650, 920, 2600),
    "OW": (500, 1000, 2450),
    "UW": (360, 1400, 2400),
    "AH": (680, 1300, 2500),
    "ER": (500, 1400, 1750),
}

_WORDS: dict[str, list[str]] = {
    "IY": ["beet", "seat", "keep", "feed", "team"],
    "IH": ["bit", "sit", "kid", "fill", "wind"],
    "EH": ["bet", "set", "bed", "help", "then"],
    "AE": ["bat", "sat", "bad", "man", "back"],
    "AA": ["bot", "cot", "pod", "lock", "father"],
    "AO": ["bought", "caught", "dawn", "law", "talk"],
    "OW": ["boat", "goat", "code", "know", "road"],
    "UW": ["boot", "suit", "food", "two", "moon"],
    "AH": ["but", "cut", "mud", "sun", "love"],
    "ER": ["bird", "hurt", "word", "her", "learn"],
}

_SEX_FORMANT_SCALE = {"F": 1.16, "M": 1.0, "NB": 1.08}
_AGE_GROUPS = ("Older", "Middle", "Young")


def _age_shift(vowel: str, age_group: str) -> tuple[float, float]:
    """Return (dF1, dF2) in Hz encoding an age-graded low-back merger.

    THOUGHT (AO) drifts toward LOT (AA) for younger speakers; other vowels
    are stable.
    """
    if vowel != "AO":
        return (0.0, 0.0)
    pull = {"Older": 0.0, "Middle": 0.5, "Young": 1.0}[age_group]
    # AA sits at F1=760, F2=1150; nudge AO up toward it.
    return (pull * 90.0, pull * 200.0)


def make_speakers(n_per_cell: int = 3, seed: int = 7) -> pd.DataFrame:
    """Build a balanced speaker demographics table (Sex × Age Group)."""
    rng = np.random.RandomState(seed)
    rows = []
    idx = 0
    for sex in ("F", "M"):
        for age in _AGE_GROUPS:
            for _ in range(n_per_cell):
                idx += 1
                age_years = {
                    "Young": rng.randint(18, 30),
                    "Middle": rng.randint(35, 55),
                    "Older": rng.randint(60, 85),
                }[age]
                rows.append(
                    {
                        "speaker": f"S{idx:02d}",
                        "Sex": sex,
                        "Age Group": age,
                        "Age": age_years,
                    }
                )
    return pd.DataFrame(rows)


def make_vowel_tokens(
    speakers: pd.DataFrame,
    tokens_per_vowel: int = 25,
    seed: int = 7,
) -> pd.DataFrame:
    """Generate a new-fave-style token table for the given speakers."""
    rng = np.random.RandomState(seed + 1)
    records = []
    tok_id = 0
    for _, spk in speakers.iterrows():
        vtl = _SEX_FORMANT_SCALE.get(spk["Sex"], 1.0) * rng.normal(1.0, 0.02)
        for vowel, (t1, t2, t3) in _VOWEL_TARGETS.items():
            d1, d2 = _age_shift(vowel, spk["Age Group"])
            for _ in range(tokens_per_vowel):
                tok_id += 1
                # per-token Gaussian scatter (fraction of target)
                f1 = (t1 + d1) * vtl * rng.normal(1.0, 0.07)
                f2 = (t2 + d2) * vtl * rng.normal(1.0, 0.05)
                f3 = t3 * vtl * rng.normal(1.0, 0.04)
                word = _WORDS[vowel][rng.randint(len(_WORDS[vowel]))]
                dur = float(np.round(rng.lognormal(mean=np.log(0.11), sigma=0.3), 4))
                records.append(
                    {
                        "id": f"t{tok_id:05d}",
                        "speaker": spk["speaker"],
                        "vowel": f"{vowel}1",  # ARPABET + primary-stress digit
                        "word": word,
                        "F1": round(float(f1), 1),
                        "F2": round(float(f2), 1),
                        "F3": round(float(f3), 1),
                        "dur": dur,
                        "stress": 1,
                        "pre_seg": rng.choice(["B", "S", "K", "F", "T", ""]),
                        "fol_seg": rng.choice(["T", "D", "N", "L", "P", ""]),
                        "t_mid": round(float(rng.uniform(0.5, 300.0)), 3),
                    }
                )
    return pd.DataFrame(records)


def make_demo_dataset(
    n_per_cell: int = 3, tokens_per_vowel: int = 25, seed: int = 7
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return ``(tokens, speakers)`` demo dataframes."""
    speakers = make_speakers(n_per_cell=n_per_cell, seed=seed)
    tokens = make_vowel_tokens(speakers, tokens_per_vowel=tokens_per_vowel, seed=seed)
    return tokens, speakers


def write_demo_dataset(out_dir: str | Path, seed: int = 7) -> dict[str, Path]:
    """Write ``demo_vowels.csv`` and ``demo_speakers.csv`` to ``out_dir``."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tokens, speakers = make_demo_dataset(seed=seed)
    vowels_path = out_dir / "demo_vowels.csv"
    speakers_path = out_dir / "demo_speakers.csv"
    tokens.to_csv(vowels_path, index=False)
    speakers.to_csv(speakers_path, index=False)
    return {"vowels": vowels_path, "speakers": speakers_path}


if __name__ == "__main__":  # pragma: no cover
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else "vowelchemy/data"
    paths = write_demo_dataset(target)
    print(f"Wrote demo data to {paths['vowels']} and {paths['speakers']}")
