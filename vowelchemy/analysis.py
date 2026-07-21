"""Analysis layer: join demographics, select vowels, filter and group.

This is the bridge between raw extracted formants and the tidy dataset a
student downloads or plots.  It:

* attaches a speaker-demographics table (Sex, Age Group, …) to the token table;
* adds canonical vowel labels so "BEET"/"FLEECE"/"IY" all refer to one thing;
* lets the user pick vowels and filter/group by any sociodemographic column;
* produces per-group summary statistics.

All functions are pure (return new frames) and schema-driven.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Mapping, Optional, Sequence

import numpy as np
import pandas as pd

from .constants import canonical_vowel, resolve_vowel, vowel_display_label
from .schema import _ALIASES, ColumnSchema

# Columns that are never sensible *grouping* variables.
_NON_GROUPING_ROLES = {"f1", "f2", "f3", "time", "token_id", "duration"}


def load_vowel_data(path: str | Path) -> pd.DataFrame:
    """Read an extracted-vowel CSV (comma or tab separated, auto-sniffed)."""
    path = Path(path)
    sep = "\t" if path.suffix.lower() in {".tsv", ".tab"} else None
    # sep=None with the python engine sniffs the delimiter.
    return pd.read_csv(path, sep=sep, engine="python")


def load_demographics(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    sep = "\t" if path.suffix.lower() in {".tsv", ".tab"} else None
    return pd.read_csv(path, sep=sep, engine="python")


def _find_speaker_column(df: pd.DataFrame) -> Optional[str]:
    lower = {str(c).strip().lower(): c for c in df.columns}
    for alias in _ALIASES["speaker"]:
        if alias in lower:
            return lower[alias]
    return None


def join_demographics(
    vowels: pd.DataFrame,
    demographics: pd.DataFrame,
    schema: ColumnSchema,
    demographics_speaker_col: Optional[str] = None,
) -> pd.DataFrame:
    """Left-join a speaker demographics table onto the token table.

    The join key on the vowel side is ``schema.speaker``; on the demographics
    side it is auto-detected (or supplied via ``demographics_speaker_col``).
    Demographic columns that would collide with existing token columns are
    suffixed with ``_spk``.
    """
    spk = schema.require("speaker")
    demo_key = demographics_speaker_col or _find_speaker_column(demographics)
    if demo_key is None:
        raise KeyError(
            "Could not find a speaker column in the demographics table; "
            f"columns were {list(demographics.columns)}."
        )
    demo = demographics.copy()
    # Normalize the key to string on both sides so "S01" and 1 match cleanly.
    left = vowels.copy()
    left["_spk_key"] = left[spk].astype(str).str.strip()
    demo["_spk_key"] = demo[demo_key].astype(str).str.strip()
    demo = demo.drop(columns=[demo_key])

    overlap = (set(demo.columns) & set(left.columns)) - {"_spk_key"}
    if overlap:
        demo = demo.rename(columns={c: f"{c}_spk" for c in overlap})

    merged = left.merge(demo, on="_spk_key", how="left").drop(columns="_spk_key")
    return merged


def add_vowel_labels(
    df: pd.DataFrame, schema: ColumnSchema, label_map: Optional[Mapping[str, str]] = None
) -> pd.DataFrame:
    """Add ``vowel_canon`` (bare ARPABET) and ``vowel_label`` (friendly) columns.

    ``label_map`` (canonical code → display label) overrides the built-in
    English keyword labels, so IPA / non-English vowel coding can be labelled.
    """
    vowel = schema.require("vowel")
    out = df.copy()
    out["vowel_canon"] = out[vowel].map(canonical_vowel)
    if label_map:
        out["vowel_label"] = out["vowel_canon"].map(
            lambda v: label_map.get(v, vowel_display_label(v))
        )
    else:
        out["vowel_label"] = out["vowel_canon"].map(vowel_display_label)
    return out


def list_vowels(df: pd.DataFrame, schema: ColumnSchema) -> pd.DataFrame:
    """Return a table of available vowels with token counts, most frequent first."""
    vowel = schema.require("vowel")
    canon = df[vowel].map(canonical_vowel)
    counts = canon.value_counts(dropna=False)
    return pd.DataFrame(
        {
            "vowel": counts.index,
            "label": [vowel_display_label(v) for v in counts.index],
            "n": counts.values,
        }
    )


def select_vowels(
    df: pd.DataFrame, schema: ColumnSchema, vowels: Iterable[str]
) -> pd.DataFrame:
    """Keep only rows whose vowel matches any of ``vowels``.

    Each requested vowel may be given as ARPABET (``IY``), a Wells lexical set
    (``FLEECE``), or a keyword (``BEET``); all resolve to canonical ARPABET.
    Unresolvable names fall back to a direct canonical match so custom codes
    still work.
    """
    vowel = schema.require("vowel")
    wanted: set[str] = set()
    for v in vowels:
        resolved = resolve_vowel(v)
        wanted.add(resolved if resolved else canonical_vowel(v))
    canon = df[vowel].map(canonical_vowel)
    return df[canon.isin(wanted)].copy()


def candidate_grouping_columns(
    df: pd.DataFrame, schema: ColumnSchema, max_cardinality: int = 30
) -> list[str]:
    """Columns suitable for grouping/faceting (categorical, low-cardinality).

    Excludes formant/time/id columns and anything with too many distinct
    values (likely continuous or an identifier).  The speaker column and the
    canonical vowel label are always offered when present.
    """
    role_cols = {
        getattr(schema, role) for role in _NON_GROUPING_ROLES if getattr(schema, role, None)
    }
    norm_cols = {"F1_norm", "F2_norm", "F3_norm"}
    always = [c for c in ("vowel_label", "vowel_canon") if c in df.columns]

    candidates: list[str] = []
    for col in df.columns:
        if col in role_cols or col in norm_cols or col in always:
            continue
        series = df[col]
        n_unique = series.nunique(dropna=True)
        if n_unique <= 1 or n_unique > max_cardinality:
            continue
        if pd.api.types.is_float_dtype(series):
            continue  # continuous
        candidates.append(col)

    # Put speaker and known demographic-ish names first for convenience.
    priority = [schema.speaker] if schema.speaker in candidates else []
    ordered = priority + [c for c in candidates if c not in priority]
    return always + ordered


def apply_filters(
    df: pd.DataFrame, filters: Mapping[str, Sequence]
) -> pd.DataFrame:
    """Keep rows where each ``column`` is in its allowed set of values.

    Empty/None value-sets are ignored (treated as "no filter on this column").
    """
    out = df
    for col, allowed in filters.items():
        if not allowed or col not in out.columns:
            continue
        allowed_set = set(allowed)
        out = out[out[col].isin(allowed_set)]
    return out.copy()


def summarize(
    df: pd.DataFrame,
    schema: ColumnSchema,
    group_by: Sequence[str],
    value_columns: Optional[Sequence[str]] = None,
) -> pd.DataFrame:
    """Per-group mean/SD/N for the given (usually normalized) value columns."""
    if value_columns is None:
        value_columns = [
            c for c in ("F1_norm", "F2_norm", "F3_norm") if c in df.columns
        ] or schema.formant_columns()
    group_by = [g for g in group_by if g in df.columns]
    if not group_by:
        raise ValueError("No valid grouping columns supplied.")

    agg = {c: ["mean", "std", "count"] for c in value_columns}
    grouped = df.groupby(group_by, dropna=False).agg(agg)
    grouped.columns = [f"{col}_{stat}" for col, stat in grouped.columns]
    return grouped.reset_index()


def flag_outliers(
    df: pd.DataFrame,
    schema: ColumnSchema,
    n_sd: float = 2.5,
    value_columns: Optional[Sequence[str]] = None,
) -> pd.DataFrame:
    """Add an ``is_outlier`` column: token far from its speaker×vowel centroid.

    A common cleaning step for automatically-tracked formants.  Outlier =
    beyond ``n_sd`` standard deviations on any formant within its
    speaker×vowel cell.
    """
    spk = schema.require("speaker")
    vowel_col = "vowel_canon" if "vowel_canon" in df.columns else schema.require("vowel")
    if value_columns is None:
        value_columns = schema.formant_columns()

    out = df.copy()
    key = [spk, vowel_col]
    flags = np.zeros(len(out), dtype=bool)
    grouped = out.groupby(key, dropna=False)
    for col in value_columns:
        mean = grouped[col].transform("mean")
        sd = grouped[col].transform("std")
        with np.errstate(invalid="ignore", divide="ignore"):
            z = (out[col].astype(float) - mean) / sd
        flags |= z.abs().gt(n_sd).fillna(False).to_numpy()
    out["is_outlier"] = flags
    return out
