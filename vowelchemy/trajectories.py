"""Formant-trajectory support.

new-fave emits not only single-point measurements but full formant *tracks*
(one row per time-slice, or DCT coefficients). This module works with the
long-format tracks table — many rows per vowel *token*, each with a time/
proportion column — and computes **mean trajectories** per vowel (optionally per
group) so diphthongs and vowel-inherent spectral change (VISC) can be plotted.

A tracks table needs, at minimum: a token id (grouping the slices of one vowel),
a time column, a vowel label, and F1/F2. Column detection reuses
:class:`vowelchemy.schema.ColumnSchema`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from .constants import canonical_vowel
from .schema import ColumnSchema


@dataclass
class TrackSchema:
    token_id: str
    time: str

    @classmethod
    def detect(cls, df: pd.DataFrame, schema: ColumnSchema) -> Optional["TrackSchema"]:
        if schema.token_id and schema.time and schema.token_id in df.columns:
            # Only a trajectory if tokens actually have multiple time-slices.
            if df.groupby(schema.token_id).size().max() > 1:
                return cls(token_id=schema.token_id, time=schema.time)
        return None


def is_trajectory_data(df: pd.DataFrame, schema: ColumnSchema) -> bool:
    return TrackSchema.detect(df, schema) is not None


def normalized_time(df: pd.DataFrame, track: TrackSchema) -> pd.Series:
    """Map each token's time column onto [0, 1] within that token."""
    grp = df.groupby(track.token_id)[track.time]
    tmin = grp.transform("min")
    tmax = grp.transform("max")
    span = (tmax - tmin).where(lambda s: s != 0, np.nan)
    return ((df[track.time] - tmin) / span).fillna(0.5)


def mean_trajectories(
    df: pd.DataFrame,
    schema: ColumnSchema,
    track: TrackSchema,
    group_by: Optional[str] = None,
    n_steps: int = 10,
    formants: Optional[list[str]] = None,
) -> pd.DataFrame:
    """Average trajectory per vowel (× group) over ``n_steps`` normalized-time bins.

    Returns tidy rows: ``vowel``, [``group``], ``step`` (0…n_steps-1),
    ``<formant>_mean`` for each formant, and ``n`` tokens contributing.
    """
    if formants is None:
        formants = [c for c in ("F1_norm", "F2_norm") if c in df.columns] or [
            schema.require("f1"), schema.require("f2")
        ]
    d = df.copy()
    d["_nt"] = normalized_time(d, track)
    d["_step"] = np.clip((d["_nt"] * n_steps).astype(int), 0, n_steps - 1)
    vcol = "vowel_canon" if "vowel_canon" in d.columns else schema.require("vowel")
    d["_vowel"] = d[vcol] if vcol == "vowel_canon" else d[vcol].map(canonical_vowel)

    keys = ["_vowel"] + ([group_by] if group_by and group_by in d.columns else []) + ["_step"]
    agg = {f: "mean" for f in formants}
    agg[track.token_id] = "nunique"
    out = d.groupby(keys, dropna=False).agg(agg).reset_index()
    out = out.rename(columns={track.token_id: "n", "_vowel": "vowel", "_step": "step"})
    return out
