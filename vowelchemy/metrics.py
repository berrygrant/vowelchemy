"""Vowel separation / overlap metrics — the "phonJSD" step.

The headline metric is the **Jensen-Shannon Divergence (JSD)** between two
vowel categories' distributions in (normalized) formant space.  JSD is a
symmetric, bounded measure of how distinguishable two distributions are:

    JSD(P, Q) = 1/2 KL(P || M) + 1/2 KL(Q || M),   M = 1/2 (P + Q)

Computed with a base-2 logarithm it lies in ``[0, 1]``:

* ``0`` — the two vowels are indistinguishable (fully **merged**),
* ``1`` — their distributions do not overlap at all (fully **separated**).

This is the natural quantity for questions like "are LOT and THOUGHT merging?"
or "how separated are BET and BEET for younger vs older speakers?".  We
estimate each vowel's density with a Gaussian kernel (KDE), fall back to a
fitted 2-D Gaussian when tokens are sparse, and integrate on a shared grid.

Two companion metrics are reported alongside JSD for triangulation:

* **Pillai score** — from a one-way MANOVA of the formants on vowel identity;
  ``0`` = complete overlap, higher = more separated (widely used for merger work).
* **Bhattacharyya overlap** — analytic overlap coefficient of two Gaussians;
  ``1`` = identical, ``0`` = disjoint (the complement sense of JSD).
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Optional, Sequence

import numpy as np
import pandas as pd

from .constants import canonical_vowel, vowel_display_label
from .schema import ColumnSchema

_EPS = 1e-12


@dataclass
class SeparationResult:
    vowel_a: str
    vowel_b: str
    n_a: int
    n_b: int
    jsd: float
    pillai: Optional[float] = None
    bhattacharyya_overlap: Optional[float] = None
    group: Optional[str] = None
    group_value: Optional[object] = None
    method: str = "kde"
    dimensions: tuple[str, ...] = ()
    notes: list[str] = field(default_factory=list)

    def as_row(self) -> dict:
        return {
            "group": self.group,
            "group_value": self.group_value,
            "vowel_a": self.vowel_a,
            "vowel_b": self.vowel_b,
            "pair": f"{self.vowel_a}~{self.vowel_b}",
            "n_a": self.n_a,
            "n_b": self.n_b,
            "JSD": self.jsd,
            "Pillai": self.pillai,
            "Bhattacharyya_overlap": self.bhattacharyya_overlap,
            "method": self.method,
        }


# --------------------------------------------------------------------------- #
# Core JSD
# --------------------------------------------------------------------------- #
def _fit_density(points: np.ndarray, method: str):
    """Return a callable density evaluated on an (N, D) query array."""
    from scipy.stats import gaussian_kde, multivariate_normal

    n, d = points.shape
    use_gaussian = method == "gaussian" or n < max(5, d + 2)
    if not use_gaussian:
        try:
            kde = gaussian_kde(points.T)
            return lambda q: kde(q.T), "kde"
        except (np.linalg.LinAlgError, ValueError):
            use_gaussian = True
    # Fitted Gaussian fallback (ridge-regularized covariance).
    mu = points.mean(axis=0)
    cov = np.cov(points.T) if n > 1 else np.eye(d)
    cov = np.atleast_2d(cov) + np.eye(d) * (np.trace(np.atleast_2d(cov)) / d * 1e-3 + _EPS)
    rv = multivariate_normal(mean=mu, cov=cov, allow_singular=True)
    return lambda q: rv.pdf(q), "gaussian"


def _shared_grid(a: np.ndarray, b: np.ndarray, grid_size: int) -> np.ndarray:
    """Build an evaluation grid spanning both point clouds (D = 1 or 2)."""
    combined = np.vstack([a, b])
    d = combined.shape[1]
    mins = combined.min(axis=0)
    maxs = combined.max(axis=0)
    span = np.where(maxs > mins, maxs - mins, 1.0)
    pad = 0.25 * span
    lo, hi = mins - pad, maxs + pad
    axes = [np.linspace(lo[i], hi[i], grid_size) for i in range(d)]
    if d == 1:
        return axes[0].reshape(-1, 1)
    mesh = np.meshgrid(*axes, indexing="ij")
    return np.column_stack([m.ravel() for m in mesh])


def jensen_shannon_divergence(
    points_a: np.ndarray,
    points_b: np.ndarray,
    method: str = "kde",
    grid_size: Optional[int] = None,
) -> float:
    """JSD (base-2, in [0, 1]) between two point clouds via grid integration.

    ``points_a`` / ``points_b`` are ``(n, D)`` arrays with ``D`` in {1, 2}.
    Returns ``nan`` if either cloud is too small to estimate a density.
    """
    a = np.asarray(points_a, dtype=float)
    b = np.asarray(points_b, dtype=float)
    a = a[~np.isnan(a).any(axis=1)]
    b = b[~np.isnan(b).any(axis=1)]
    if len(a) < 2 or len(b) < 2:
        return float("nan")

    d = a.shape[1]
    if grid_size is None:
        grid_size = 400 if d == 1 else 120

    grid = _shared_grid(a, b, grid_size)
    dens_a, _ = _fit_density(a, method)
    dens_b, _ = _fit_density(b, method)
    p = np.clip(dens_a(grid), 0, None)
    q = np.clip(dens_b(grid), 0, None)
    p_sum, q_sum = p.sum(), q.sum()
    if p_sum <= 0 or q_sum <= 0:
        return float("nan")
    p = p / p_sum
    q = q / q_sum
    m = 0.5 * (p + q)

    def _kl(x, y):
        mask = x > 0
        return float(np.sum(x[mask] * np.log2(x[mask] / (y[mask] + _EPS))))

    jsd = 0.5 * _kl(p, m) + 0.5 * _kl(q, m)
    return float(np.clip(jsd, 0.0, 1.0))


# --------------------------------------------------------------------------- #
# Companion metrics
# --------------------------------------------------------------------------- #
def pillai_score(points_a: np.ndarray, points_b: np.ndarray) -> float:
    """Pillai's trace for a two-group MANOVA (0 = overlap, →1 = separated)."""
    a = np.asarray(points_a, dtype=float)
    b = np.asarray(points_b, dtype=float)
    a = a[~np.isnan(a).any(axis=1)]
    b = b[~np.isnan(b).any(axis=1)]
    if len(a) < 2 or len(b) < 2:
        return float("nan")
    d = a.shape[1]
    grand = np.vstack([a, b]).mean(axis=0)
    mean_a, mean_b = a.mean(axis=0), b.mean(axis=0)

    # Within-group SSCP (E) and between-group SSCP (H).
    e = (a - mean_a).T @ (a - mean_a) + (b - mean_b).T @ (b - mean_b)
    h = (
        len(a) * np.outer(mean_a - grand, mean_a - grand)
        + len(b) * np.outer(mean_b - grand, mean_b - grand)
    )
    total = h + e
    try:
        v = np.trace(h @ np.linalg.inv(total + np.eye(d) * _EPS))
    except np.linalg.LinAlgError:
        return float("nan")
    return float(np.clip(v, 0.0, 1.0))


def bhattacharyya_overlap(points_a: np.ndarray, points_b: np.ndarray) -> float:
    """Bhattacharyya coefficient of two fitted Gaussians (1 = identical)."""
    a = np.asarray(points_a, dtype=float)
    b = np.asarray(points_b, dtype=float)
    a = a[~np.isnan(a).any(axis=1)]
    b = b[~np.isnan(b).any(axis=1)]
    if len(a) < 2 or len(b) < 2:
        return float("nan")
    d = a.shape[1]
    mu1, mu2 = a.mean(axis=0), b.mean(axis=0)
    cov1 = np.atleast_2d(np.cov(a.T)) + np.eye(d) * _EPS
    cov2 = np.atleast_2d(np.cov(b.T)) + np.eye(d) * _EPS
    cov = 0.5 * (cov1 + cov2)
    try:
        inv = np.linalg.inv(cov)
        diff = mu1 - mu2
        term1 = 0.125 * diff @ inv @ diff
        det1 = np.linalg.det(cov1)
        det2 = np.linalg.det(cov2)
        detc = np.linalg.det(cov)
        term2 = 0.5 * np.log(max(detc, _EPS) / max(np.sqrt(det1 * det2), _EPS))
        d_b = term1 + term2
    except np.linalg.LinAlgError:
        return float("nan")
    return float(np.clip(np.exp(-d_b), 0.0, 1.0))


# --------------------------------------------------------------------------- #
# High-level: pairwise separation over selected vowels, optionally by group
# --------------------------------------------------------------------------- #
def _resolve_dimensions(df: pd.DataFrame, dimensions: Optional[Sequence[str]]) -> list[str]:
    if dimensions:
        return [c for c in dimensions if c in df.columns]
    for combo in (("F1_norm", "F2_norm"), ("F1", "F2")):
        if all(c in df.columns for c in combo):
            return list(combo)
    return []


def pair_separation(
    df: pd.DataFrame,
    schema: ColumnSchema,
    vowel_a: str,
    vowel_b: str,
    dimensions: Optional[Sequence[str]] = None,
    method: str = "kde",
    group: Optional[str] = None,
    group_value: Optional[object] = None,
) -> SeparationResult:
    """Compute JSD + companions for one vowel pair on one (sub)frame."""
    dims = _resolve_dimensions(df, dimensions)
    vowel_col = "vowel_canon" if "vowel_canon" in df.columns else schema.require("vowel")
    canon = df[vowel_col].map(canonical_vowel) if vowel_col != "vowel_canon" else df[vowel_col]
    a = df.loc[canon == canonical_vowel(vowel_a), dims].to_numpy(dtype=float)
    b = df.loc[canon == canonical_vowel(vowel_b), dims].to_numpy(dtype=float)

    notes: list[str] = []
    if not dims:
        notes.append("No formant dimensions available for separation.")
    jsd = jensen_shannon_divergence(a, b, method=method) if dims else float("nan")
    pillai = pillai_score(a, b) if dims else float("nan")
    bhatt = bhattacharyya_overlap(a, b) if dims else float("nan")
    return SeparationResult(
        vowel_a=canonical_vowel(vowel_a),
        vowel_b=canonical_vowel(vowel_b),
        n_a=len(a),
        n_b=len(b),
        jsd=jsd,
        pillai=pillai,
        bhattacharyya_overlap=bhatt,
        group=group,
        group_value=group_value,
        method=method,
        dimensions=tuple(dims),
        notes=notes,
    )


def pairwise_separation(
    df: pd.DataFrame,
    schema: ColumnSchema,
    vowels: Optional[Sequence[str]] = None,
    group_by: Optional[str] = None,
    dimensions: Optional[Sequence[str]] = None,
    method: str = "kde",
    min_tokens: int = 5,
) -> pd.DataFrame:
    """Separation metrics for every vowel pair, optionally within each group.

    This directly answers "how separated are these vowels, and does it differ
    across Age Group / Sex?".  Pass a single grouping column via ``group_by``
    to get one row per (group level × vowel pair).
    """
    vowel_col = "vowel_canon" if "vowel_canon" in df.columns else schema.require("vowel")
    canon_all = (
        df[vowel_col].map(canonical_vowel) if vowel_col != "vowel_canon" else df[vowel_col]
    )
    if vowels:
        wanted = [canonical_vowel(v) for v in vowels]
    else:
        wanted = sorted(canon_all.dropna().unique())
    pairs = list(itertools.combinations(sorted(set(wanted)), 2))

    frames: list[tuple[Optional[object], pd.DataFrame]] = []
    if group_by and group_by in df.columns:
        for gval, sub in df.groupby(group_by, dropna=False):
            frames.append((gval, sub))
    else:
        frames.append((None, df))

    rows: list[dict] = []
    for gval, sub in frames:
        sub_canon = (
            sub[vowel_col].map(canonical_vowel)
            if vowel_col != "vowel_canon"
            else sub[vowel_col]
        )
        for va, vb in pairs:
            if (sub_canon == va).sum() < min_tokens or (sub_canon == vb).sum() < min_tokens:
                continue
            res = pair_separation(
                sub, schema, va, vb,
                dimensions=dimensions, method=method,
                group=group_by, group_value=gval,
            )
            row = res.as_row()
            row["vowel_a_label"] = vowel_display_label(va)
            row["vowel_b_label"] = vowel_display_label(vb)
            rows.append(row)

    result = pd.DataFrame(rows)
    if not result.empty:
        result = result.sort_values(
            ["group_value", "JSD"], ascending=[True, False], na_position="first"
        ).reset_index(drop=True)
    return result
