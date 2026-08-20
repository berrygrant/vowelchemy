"""Vowel formant normalization.

Normalization removes anatomical (vocal-tract-length) differences between
speakers so their vowels can be compared on a common scale.  Vowelchemy keeps
the math **transparent and post-hoc**: raw Hz formants are extracted once, and
any method can be (re)applied instantly without re-running extraction — which
is exactly what you want when teaching students the difference between methods.

Every method writes generic ``F1_norm`` / ``F2_norm`` / ``F3_norm`` columns and
records what it did in a :class:`NormalizationResult`, so downstream code never
needs to know which method was used.

Methods
-------
``lobanov`` (default)
    Speaker-intrinsic z-score, per formant:  ``(F - mean) / sd``.  This is the
    normalization used in the *Atlas of North American English* tradition.
``labov_anae``
    Labov's ANAE log-mean *scaling* method.  A single per-speaker factor
    rescales the whole vowel space to a shared grand mean ``G`` (default the
    Telsur constant 6.896874), returning interpretable scaled-Hz values.
``nearey`` / ``nearey1``
    Log-mean centering, shared (formant-extrinsic) or individual
    (formant-intrinsic).
``bark``
    Traunmüller Bark-scale transform of each formant (a psychoacoustic
    rescaling, not a speaker normalization).
``watt_fabricius``
    Modified S-centroid ratio (Fabricius, Watt & Johnson 2009); needs corner
    vowels (defaults FLEECE=IY, TRAP=AE).
``none``
    Pass raw Hz through as ``*_norm`` so downstream code is uniform.

References: Lobanov (1971); Labov, Ash & Boberg (2006), *ANAE*; Nearey (1978);
Watt & Fabricius (2002); Fabricius, Watt & Johnson (2009); Traunmüller (1990).
See also NORM (Thomas & Kendall) and Barreda's note that ANAE == log-mean.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import numpy as np
import pandas as pd

from .constants import DEFAULT_NORMALIZATION, canonical_vowel
from .schema import ColumnSchema

# The Telsur grand log-mean Labov reported for 345 speakers ("Telsur G").
ANAE_TELSUR_G = 6.896874

NORM_COLUMNS = {"f1": "F1_norm", "f2": "F2_norm", "f3": "F3_norm"}


@dataclass
class NormalizationResult:
    """Outcome of a normalization run."""

    data: pd.DataFrame
    method: str
    units: str
    norm_columns: dict[str, str]  # logical field -> new column name
    notes: list[str] = field(default_factory=list)


@dataclass
class MethodInfo:
    key: str
    label: str
    description: str
    units: str


def available_methods() -> list[MethodInfo]:
    """Method metadata for building UI menus."""
    return [
        MethodInfo(
            "lobanov", "Lobanov (z-score) — ANAE default",
            "Per-speaker z-score of each formant. The de-facto sociophonetic standard.",
            "z-score (SD units)",
        ),
        MethodInfo(
            "labov_anae", "Labov ANAE (log-mean scaling)",
            "Single per-speaker scaling factor to a shared grand mean G; returns scaled Hz.",
            "scaled Hz",
        ),
        MethodInfo(
            "nearey", "Nearey (shared log-mean)",
            "Subtract one per-speaker log-mean from every formant (formant-extrinsic).",
            "log-Hz (centered)",
        ),
        MethodInfo(
            "nearey1", "Nearey1 (individual log-mean)",
            "Subtract a per-speaker, per-formant log-mean (formant-intrinsic).",
            "log-Hz (centered)",
        ),
        MethodInfo(
            "bark", "Bark transform (Traunmüller)",
            "Convert each formant to the Bark psychoacoustic scale (vowel-intrinsic).",
            "Bark",
        ),
        MethodInfo(
            "watt_fabricius", "Watt–Fabricius (modified S-centroid)",
            "Divide each formant by a per-speaker centroid built from corner vowels.",
            "S-centroid ratio",
        ),
        MethodInfo(
            "none", "None (raw Hz)",
            "No normalization; carry raw Hz forward.",
            "Hz",
        ),
    ]


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #
def normalize(
    df: pd.DataFrame,
    schema: ColumnSchema,
    method: str = DEFAULT_NORMALIZATION,
    *,
    g_value: float = ANAE_TELSUR_G,
    corner_high: str = "IY",
    corner_low: str = "AE",
) -> NormalizationResult:
    """Add normalized formant columns to ``df`` using ``method``.

    Returns a :class:`NormalizationResult` wrapping a copy of ``df`` with
    ``F1_norm``/``F2_norm``/``F3_norm`` populated where applicable.
    """
    method = (method or "none").lower()
    out = df.copy()
    notes: list[str] = []

    spk = schema.require("speaker")
    f1 = schema.require("f1")
    f2 = schema.require("f2")
    f3 = schema.f3  # optional

    formants = [("f1", f1), ("f2", f2)] + ([("f3", f3)] if f3 else [])

    dispatch = {
        "lobanov": _lobanov,
        "labov_anae": _labov_anae,
        "nearey": _nearey_shared,
        "nearey1": _nearey_individual,
        "bark": _bark,
        "watt_fabricius": _watt_fabricius,
        "none": _identity,
    }
    if method not in dispatch:
        raise ValueError(
            f"Unknown normalization method '{method}'. "
            f"Choose from {sorted(dispatch)}."
        )

    units = _method_units(method)
    norm_columns = dispatch[method](
        out, spk, formants, schema,
        notes=notes, g_value=g_value,
        corner_high=corner_high, corner_low=corner_low,
    )
    out["norm_method"] = method
    return NormalizationResult(
        data=out, method=method, units=units, norm_columns=norm_columns, notes=notes
    )


def _method_units(method: str) -> str:
    return {m.key: m.units for m in available_methods()}.get(method, "")


# --------------------------------------------------------------------------- #
# Individual methods.  Each returns {logical_field: new_column_name}.
# --------------------------------------------------------------------------- #
def _identity(out, spk, formants, schema, *, notes, **_) -> dict:
    cols = {}
    for key, col in formants:
        newcol = NORM_COLUMNS[key]
        out[newcol] = out[col].astype(float)
        cols[key] = newcol
    return cols


def _lobanov(out, spk, formants, schema, *, notes, **_) -> dict:
    cols = {}
    grp = out.groupby(spk, dropna=False)
    for key, col in formants:
        vals = out[col].astype(float)
        mean = grp[col].transform("mean")
        sd = grp[col].transform("std")  # sample SD (ddof=1)
        newcol = NORM_COLUMNS[key]
        with np.errstate(invalid="ignore", divide="ignore"):
            out[newcol] = (vals - mean) / sd
        cols[key] = newcol
    n_singletons = (grp[formants[0][1]].transform("count") < 2).sum()
    if n_singletons:
        notes.append(
            f"{int(n_singletons)} token(s) belong to speakers with <2 tokens; "
            "their z-scores are undefined (NaN)."
        )
    return cols


def _labov_anae(out, spk, formants, schema, *, notes, g_value, **_) -> dict:
    """Log-mean scaling to a shared grand mean; returns scaled Hz."""
    f1_col, f2_col = formants[0][1], formants[1][1]
    ln_f1 = _safe_log(out[f1_col], notes, "F1")
    ln_f2 = _safe_log(out[f2_col], notes, "F2")

    # Per-speaker S = mean of ln(F1) and ln(F2) pooled across all tokens.
    tmp = pd.DataFrame({spk: out[spk], "_lnf1": ln_f1, "_lnf2": ln_f2})
    per_speaker = tmp.groupby(spk, dropna=False)[["_lnf1", "_lnf2"]].mean().mean(axis=1)
    s = out[spk].map(per_speaker)

    factor = np.exp(g_value - s)  # multiplicative rescaling per token's speaker
    cols = {}
    for key, col in formants:
        newcol = NORM_COLUMNS[key]
        out[newcol] = out[col].astype(float) * factor
        cols[key] = newcol
    notes.append(
        f"Labov ANAE scaling with G={g_value:g} "
        f"({'Telsur constant' if abs(g_value - ANAE_TELSUR_G) < 1e-9 else 'custom'}). "
        "Values are rescaled Hz."
    )
    return cols


def _nearey_shared(out, spk, formants, schema, *, notes, **_) -> dict:
    """Formant-extrinsic: subtract one per-speaker log-mean from every formant."""
    logs = {key: _safe_log(out[col], notes, col) for key, col in formants}
    stacked = pd.concat([logs[key].rename(key) for key, _ in formants], axis=1)
    stacked[spk] = out[spk].values
    # single grand log-mean per speaker, pooled across formants and tokens
    grand = stacked.groupby(spk, dropna=False)[[k for k, _ in formants]].mean().mean(axis=1)
    gmap = out[spk].map(grand)
    cols = {}
    for key, _col in formants:
        newcol = NORM_COLUMNS[key]
        out[newcol] = logs[key] - gmap
        cols[key] = newcol
    return cols


def _nearey_individual(out, spk, formants, schema, *, notes, **_) -> dict:
    """Formant-intrinsic: subtract a per-speaker, per-formant log-mean."""
    cols = {}
    for key, col in formants:
        ln = _safe_log(out[col], notes, col)
        ln_by_speaker = ln.groupby(out[spk]).transform("mean")
        newcol = NORM_COLUMNS[key]
        out[newcol] = ln - ln_by_speaker
        cols[key] = newcol
    return cols


def _bark(out, spk, formants, schema, *, notes, **_) -> dict:
    cols = {}
    for key, col in formants:
        newcol = NORM_COLUMNS[key]
        out[newcol] = hz_to_bark(out[col].astype(float))
        cols[key] = newcol
    return cols


def _watt_fabricius(out, spk, formants, schema, *, notes, corner_high, corner_low, **_) -> dict:
    """Modified S-centroid (Fabricius, Watt & Johnson 2009).

    S(F1) = (2*F1[i] + F1[a]) / 3    (u' has F1 = F1[i])
    S(F2) = (F2[i] + F1[i]) / 2      (u' has F2 = F1[i]; F2[a] dropped in the
                                      2009 modification)
    then F1' = F1 / S(F1), F2' = F2 / S(F2).
    """
    f1_col, f2_col = formants[0][1], formants[1][1]
    vowel_col = schema.require("vowel")
    canon = out[vowel_col].map(canonical_vowel)
    hi, lo = canonical_vowel(corner_high), canonical_vowel(corner_low)

    s_f1: dict = {}
    s_f2: dict = {}
    missing_speakers: list[str] = []
    for speaker, sub in out.groupby(spk, dropna=False):
        csub = canon.loc[sub.index]
        f1_i = sub.loc[csub == hi, f1_col].astype(float).mean()
        f2_i = sub.loc[csub == hi, f2_col].astype(float).mean()
        f1_a = sub.loc[csub == lo, f1_col].astype(float).mean()
        if np.isnan(f1_i) or np.isnan(f2_i) or np.isnan(f1_a):
            missing_speakers.append(str(speaker))
            s_f1[speaker] = np.nan
            s_f2[speaker] = np.nan
            continue
        s_f1[speaker] = (2 * f1_i + f1_a) / 3.0
        s_f2[speaker] = (f2_i + f1_i) / 2.0

    out["F1_norm"] = out[f1_col].astype(float) / out[spk].map(s_f1)
    out["F2_norm"] = out[f2_col].astype(float) / out[spk].map(s_f2)
    cols = {"f1": "F1_norm", "f2": "F2_norm"}
    if missing_speakers:
        notes.append(
            "Watt–Fabricius needs both corner vowels "
            f"({hi}=FLEECE and {lo}=TRAP). Missing for speaker(s): "
            f"{', '.join(sorted(set(missing_speakers)))}; their tokens are NaN. "
            "Consider Lobanov instead for conversational data with sparse corners."
        )
    return cols


# --------------------------------------------------------------------------- #
# Small numeric helpers
# --------------------------------------------------------------------------- #
def hz_to_bark(freq: pd.Series | np.ndarray) -> np.ndarray:
    """Traunmüller (1990) Hz→Bark conversion: 26.81/(1 + 1960/f) - 0.53."""
    f = np.asarray(freq, dtype=float)
    with np.errstate(invalid="ignore", divide="ignore"):
        return 26.81 / (1.0 + 1960.0 / f) - 0.53


def _safe_log(series: pd.Series, notes: list[str], name: str) -> pd.Series:
    vals = series.astype(float)
    nonpos = (vals <= 0) | vals.isna()
    if nonpos.any():
        notes.append(
            f"{int(nonpos.sum())} non-positive/missing {name} value(s) set to NaN before log."
        )
        vals = vals.where(~nonpos, np.nan)
    return np.log(vals)
