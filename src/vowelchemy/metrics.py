"""Vowel separation / overlap metrics — a Python port of phontrast 2.4.1.

Everything here mirrors the estimators in the `phontrast
<https://github.com/berrygrant/phontrast>`_ R package (Berry, 2026) so that
the built-in engine and the R engine report the same quantities under the
same column names.  For one vowel pair the row contains:

* ``jsd`` — Jensen-Shannon divergence (base 2, in ``[0, 1]``) between the two
  vowels' densities: ``0`` = indistinguishable (merged), ``1`` = disjoint.
  Estimated with phontrast's Monte-Carlo plug-in: each vowel's kernel density
  is evaluated at that vowel's own tokens and the log density ratio against the
  mixture is averaged, with a *partial leave-one-out* correction on the
  self-density (fraction ``n / (n + 20)`` of each token's own kernel is
  removed) that cancels most resubstitution bias without flooring small real
  divergences to 0 (phontrast >= 2.1.0).
* ``js_distance`` — ``sqrt(jsd)``, the Jensen-Shannon *distance*.  Unlike the
  divergence it is a proper metric (Endres & Schindelin, 2003; Fuglede &
  Topsøe, 2004) and is the quantity Berry (2026a) recommends reporting
  alongside JSD.
* ``pillai`` / ``pillai_p_value`` — Pillai-Bartlett trace from a one-way
  MANOVA of the formants on vowel identity, with the F-approximation p-value
  R's ``summary.manova`` reports.  ``0`` = complete overlap.
* ``pillai_eq`` — the *proportion-standardized* Pillai score (Berry, 2026b):
  raw Pillai depends on how unevenly the tokens are split between the two
  vowels, so it is mapped through the Lachenbruch & Mickey (1968) unbiased
  squared Mahalanobis separation to the value a balanced design would give
  (Becker, 1986).  ``NA`` (with ``pillai_eq_fallback = True``) when the
  unbiased separation is negative — common near merger.
* ``bhatt_dist`` / ``bhatt_affinity`` — Bhattacharyya distance and affinity
  (``exp(-distance)``) of two fitted Gaussians (Bhattacharyya, 1943).
* ``mahalanobis_dist`` — Mahalanobis distance between the vowel means under
  the pooled covariance.
* ``percent_overlap`` — the overlapping coefficient ``∫ min(p, q)``, a 0–1
  proportion, estimated with the same Monte-Carlo plug-in as JSD.
* ``pillai_null_p95`` — Stanley & Sneller's (2023, Eq. 1) sample-size
  reference: the 95th percentile of Pillai scores two *merged* classes would
  produce with this many tokens, ``e / m`` where ``m`` is the mean tokens per
  vowel.  A Pillai at or below it is consistent with merger at this N.

Bootstrap uncertainty follows phontrast: tokens are resampled from the pooled
pair with replacement, every metric is recomputed per replicate (so
``js_distance`` is the square root *per replicate*, not of the mean), and
percentile intervals are reported as ``<metric>_ci_lower`` / ``_ci_upper``.

References (full citations in ``docs/REFERENCES.md``): Lin (1991) for JSD;
Endres & Schindelin (2003) and Fuglede & Topsøe (2004) for the distance;
Pillai (1955), Hay, Warren & Drager (2006), Nycz & Hall-Lew (2013) for Pillai
in merger work; Stanley & Sneller (2023) on sample size; Kelley & Tucker
(2020) comparing overlap measures; Becker (1986) and Lachenbruch & Mickey
(1968) behind the balance correction; Berry (2026a, 2026b) for the estimator
comparison and the calibration/balance analysis; Bhattacharyya (1943) and
Johnson (2015) for the affinity.
"""

from __future__ import annotations

import itertools
import math
from typing import Optional, Sequence

import numpy as np
import pandas as pd
from scipy.special import logsumexp
from scipy.stats import f as f_dist

from .analysis import canonical_vowel_series
from .constants import canonical_vowel, vowel_display_label
from .schema import ColumnSchema

# Ridge added to covariance matrices in the parametric metrics (phontrast `eps`).
RIDGE = 1e-6
# Sample size at which the partial leave-one-out correction removes half of
# each token's own kernel (phontrast's `min_tokens` default).
LOO_N0 = 20
# Default number of Monte-Carlo draws per category for ``density="mvnorm"``.
MC_N = 10_000
# phontrast's default minimum *total* tokens for a comparison.
MIN_TOKENS = 20

DENSITIES = ("kde", "mvnorm")
BANDWIDTHS = ("scott.diag", "scott")

# Columns phontrast bootstraps, plus the balance-corrected Pillai.
METRIC_COLUMNS = (
    "pillai", "pillai_eq", "bhatt_dist", "bhatt_affinity",
    "jsd", "js_distance", "mahalanobis_dist", "percent_overlap",
)
# Metrics that live on a 0–1 scale (for axis ranges); the rest are distances.
BOUNDED_METRICS = frozenset(
    {"jsd", "js_distance", "pillai", "pillai_eq", "bhatt_affinity", "percent_overlap"}
)
# Metrics where larger = more separated (the others measure overlap).
SEPARATION_METRICS = frozenset(
    {"jsd", "js_distance", "pillai", "pillai_eq", "bhatt_dist", "mahalanobis_dist"}
)
METRIC_LABELS = {
    "jsd": "JSD",
    "js_distance": "Jensen–Shannon distance (√JSD)",
    "pillai": "Pillai",
    "pillai_eq": "Pillai (balanced-design equivalent)",
    "bhatt_dist": "Bhattacharyya distance",
    "bhatt_affinity": "Bhattacharyya affinity",
    "mahalanobis_dist": "Mahalanobis distance",
    "percent_overlap": "Overlap (proportion)",
}


def _clean(x) -> np.ndarray:
    """``(n, d)`` float array with rows containing NaN/inf removed."""
    x = np.asarray(x, dtype=float)
    if x.ndim == 1:
        x = x.reshape(-1, 1)
    return x[np.isfinite(x).all(axis=1)]


def kde_min_category_tokens(n_features: int) -> int:
    """Tokens a category needs for the KDE-based metrics (phontrast: ``max(2, d + 1)``)."""
    return max(2, int(n_features) + 1)


# --------------------------------------------------------------------------- #
# Kernel density machinery (mirrors phontrast's `scott.diag` + MC plug-in)
# --------------------------------------------------------------------------- #
def scott_diag_bandwidth(x: np.ndarray) -> np.ndarray:
    """Diagonal Scott rule-of-thumb bandwidth matrix (phontrast ``bw = "scott.diag"``).

    ``H = diag((n^(-1/(d+4)) * sd_j)^2)``; a constant column falls back to a
    tenth of its spread (or 1) so the kernel stays proper, as in phontrast.
    """
    n, d = x.shape
    sds = x.std(axis=0, ddof=1) if n > 1 else np.zeros(d)
    bad = ~np.isfinite(sds) | (sds <= 0)
    if bad.any():
        spread = np.max(np.vstack([np.nan_to_num(sds), x.max(axis=0) - x.min(axis=0),
                                   np.ones(d)]), axis=0)
        sds = np.where(bad, spread / 10.0, sds)
    h = n ** (-1.0 / (d + 4))
    return np.diag((h * sds) ** 2)


def scott_bandwidth(x: np.ndarray) -> np.ndarray:
    """Full-covariance Scott bandwidth ``n^(-2/(d+4)) * cov`` (scipy's default).

    Not a phontrast option — offered because a full matrix follows the tilt of
    correlated F1/F2 clouds the way phontrast's default ``Hpi`` plug-in does.
    """
    n, d = x.shape
    cov = np.atleast_2d(np.cov(x.T)) if n > 1 else np.eye(d)
    cov = cov + np.eye(d) * RIDGE
    try:
        np.linalg.cholesky(cov)
    except np.linalg.LinAlgError:
        return scott_diag_bandwidth(x)
    return n ** (-2.0 / (d + 4)) * cov


def _bandwidth(x: np.ndarray, bw: str) -> np.ndarray:
    if bw == "scott.diag":
        return scott_diag_bandwidth(x)
    if bw == "scott":
        return scott_bandwidth(x)
    raise ValueError(f"unknown bandwidth {bw!r}; choose from {BANDWIDTHS}")


def _kernel_at_origin(H: np.ndarray) -> float:
    """``K_H(0)``: the Gaussian kernel's value at its own centre (for leave-one-out)."""
    d = H.shape[0]
    sign, logdet = np.linalg.slogdet(H)
    return float((2 * math.pi) ** (-d / 2) * math.exp(-0.5 * logdet))


def kde_log_density(train: np.ndarray, eval_points: np.ndarray, H: np.ndarray) -> np.ndarray:
    """Log of a Gaussian KDE with bandwidth matrix ``H`` at ``eval_points``.

    Exact for diagonal and full bandwidth matrices (whitened with a Cholesky
    factor); chunked so memory stays bounded for large token sets.
    """
    n, d = train.shape
    L = np.linalg.cholesky(H)
    logdet = 2.0 * np.log(np.diag(L)).sum()
    log_norm = -0.5 * (d * math.log(2 * math.pi) + logdet) - math.log(n)
    Linv = np.linalg.inv(L)
    tw = train @ Linv.T
    out = np.empty(len(eval_points))
    chunk = max(1, min(1000, int(2_000_000 // max(n * d, 1))))
    for start in range(0, len(eval_points), chunk):
        ew = eval_points[start:start + chunk] @ Linv.T
        sq = ((ew[:, None, :] - tw[None, :, :]) ** 2).sum(axis=-1)
        out[start:start + chunk] = logsumexp(-0.5 * sq, axis=1)
    return out + log_norm


def _loo_alpha(n: int) -> float:
    """Strength of the partial leave-one-out correction: ½ at n = 20, → 1 as n grows."""
    return n / (n + LOO_N0)


def _loo_logdens(log_dens: np.ndarray, n: int, kh0: float, alpha: float) -> np.ndarray:
    """Partial leave-one-out log density at a KDE's own training points.

    ``p_alpha(x_i) = (n * p_hat(x_i) - alpha * K_H(0)) / (n - alpha)`` removes
    a fraction ``alpha`` of the point's own kernel (``alpha = 1`` is classical
    leave-one-out).  ``-inf`` where the subtraction is not positive.
    """
    a = math.log(n) + log_dens
    b = math.log(alpha) + math.log(kh0)
    out = np.full_like(a, -np.inf)
    ok = a > b
    out[ok] = a[ok] + np.log1p(-np.exp(b - a[ok]))
    return out - math.log(n - alpha)


def _mc_pair_kde(a: np.ndarray, b: np.ndarray, bw: str) -> dict:
    """Densities each category's KDE assigns to both samples (phontrast ``.kde_mc_pair``)."""
    H1, H2 = _bandwidth(a, bw), _bandwidth(b, bw)
    return {
        "logp1": kde_log_density(a, a, H1), "logq1": kde_log_density(b, a, H2),
        "logp2": kde_log_density(a, b, H1), "logq2": kde_log_density(b, b, H2),
        "n1": len(a), "n2": len(b),
        "kh0_1": _kernel_at_origin(H1), "kh0_2": _kernel_at_origin(H2),
    }


def _mvn_fit(x: np.ndarray, ridge: float) -> tuple[np.ndarray, np.ndarray]:
    d = x.shape[1]
    cov = np.atleast_2d(np.cov(x.T)) if len(x) > 1 else np.eye(d)
    return x.mean(axis=0), cov + np.eye(d) * ridge


def _mvn_logdens(x: np.ndarray, mu: np.ndarray, S: np.ndarray) -> np.ndarray:
    d = len(mu)
    L = np.linalg.cholesky(S)
    logdet = 2.0 * np.log(np.diag(L)).sum()
    z = np.linalg.solve(L, (x - mu).T)
    return -0.5 * (d * math.log(2 * math.pi) + logdet + (z * z).sum(axis=0))


def _mc_pair_mvnorm(a: np.ndarray, b: np.ndarray, mc_n: int, seed: Optional[int],
                    ridge: float = RIDGE) -> Optional[dict]:
    """Fresh draws from one fitted Gaussian per category (phontrast ``density = "mvnorm"``)."""
    mu1, S1 = _mvn_fit(a, ridge)
    mu2, S2 = _mvn_fit(b, ridge)
    try:
        L1, L2 = np.linalg.cholesky(S1), np.linalg.cholesky(S2)
    except np.linalg.LinAlgError:
        return None
    rng = np.random.default_rng(seed)
    d = a.shape[1]
    x1 = rng.standard_normal((mc_n, d)) @ L1.T + mu1
    x2 = rng.standard_normal((mc_n, d)) @ L2.T + mu2
    return {
        "logp1": _mvn_logdens(x1, mu1, S1), "logq1": _mvn_logdens(x1, mu2, S2),
        "logp2": _mvn_logdens(x2, mu1, S1), "logq2": _mvn_logdens(x2, mu2, S2),
        "n1": len(a), "n2": len(b), "kh0_1": None, "kh0_2": None,
    }


def _mc_pair(a: np.ndarray, b: np.ndarray, density: str, bw: str, mc_n: int,
             seed: Optional[int]) -> Optional[dict]:
    if density == "kde":
        return _mc_pair_kde(a, b, bw)
    if density == "mvnorm":
        return _mc_pair_mvnorm(a, b, mc_n, seed)
    raise ValueError(f"unknown density {density!r}; choose from {DENSITIES}")


def _jsd_mc(mc: dict, loo: bool) -> float:
    """Monte-Carlo plug-in JSD in bits, clamped to ``[0, 1]`` (phontrast ``.jsd_mc``)."""
    ln2 = math.log(2)
    logp1 = (_loo_logdens(mc["logp1"], mc["n1"], mc["kh0_1"], _loo_alpha(mc["n1"]))
             if loo else mc["logp1"])
    logm1 = math.log(0.5) + np.logaddexp(logp1, mc["logq1"])
    t1 = (logp1 - logm1) / ln2
    logq2 = (_loo_logdens(mc["logq2"], mc["n2"], mc["kh0_2"], _loo_alpha(mc["n2"]))
             if loo else mc["logq2"])
    logm2 = math.log(0.5) + np.logaddexp(mc["logp2"], logq2)
    t2 = (logq2 - logm2) / ln2
    t1, t2 = t1[np.isfinite(t1)], t2[np.isfinite(t2)]
    if not len(t1) or not len(t2):
        return float("nan")
    return float(min(max(0.5 * t1.mean() + 0.5 * t2.mean(), 0.0), 1.0))


def _overlap_mc(mc: dict) -> float:
    """Overlapping coefficient ``∫ min(p, q)`` (phontrast ``.overlap_mc``; no leave-one-out)."""
    o1 = np.minimum(1.0, np.exp(mc["logq1"] - mc["logp1"]))
    o2 = np.minimum(1.0, np.exp(mc["logp2"] - mc["logq2"]))
    o1, o2 = o1[np.isfinite(o1)], o2[np.isfinite(o2)]
    if not len(o1) or not len(o2):
        return float("nan")
    return float(min(max(0.5 * o1.mean() + 0.5 * o2.mean(), 0.0), 1.0))


# --------------------------------------------------------------------------- #
# Distributional metrics
# --------------------------------------------------------------------------- #
def jensen_shannon_divergence(
    points_a, points_b,
    density: str = "kde",
    bw: str = "scott.diag",
    loo: bool = True,
    mc_n: int = MC_N,
    seed: Optional[int] = 0,
) -> float:
    """JSD (base 2, in ``[0, 1]``) between two point clouds; ``nan`` if too sparse.

    ``density="kde"`` (default) is phontrast's Monte-Carlo plug-in with the
    partial leave-one-out correction (``loo``); ``density="mvnorm"`` fits one
    Gaussian per category and draws ``mc_n`` fresh points from each instead
    (no correction needed).  Each category needs at least ``d + 1`` tokens.
    """
    a, b = _clean(points_a), _clean(points_b)
    if a.shape[1] != b.shape[1]:
        raise ValueError("points_a and points_b must have the same number of columns")
    if min(len(a), len(b)) < kde_min_category_tokens(a.shape[1]):
        return float("nan")
    mc = _mc_pair(a, b, density, bw, mc_n, seed)
    if mc is None:
        return float("nan")
    return _jsd_mc(mc, loo=loo and density == "kde")


def jensen_shannon_distance(points_a, points_b, **kwargs) -> float:
    """``sqrt(JSD)`` — the Jensen-Shannon distance (a proper metric)."""
    return float(math.sqrt(jensen_shannon_divergence(points_a, points_b, **kwargs)))


def percent_overlap(
    points_a, points_b,
    density: str = "kde",
    bw: str = "scott.diag",
    mc_n: int = MC_N,
    seed: Optional[int] = 0,
) -> float:
    """Overlapping coefficient of the two densities as a 0–1 proportion."""
    a, b = _clean(points_a), _clean(points_b)
    if min(len(a), len(b)) < kde_min_category_tokens(a.shape[1]):
        return float("nan")
    mc = _mc_pair(a, b, density, bw, mc_n, seed)
    return float("nan") if mc is None else _overlap_mc(mc)


# --------------------------------------------------------------------------- #
# Pillai trace, its F-test, and the proportion-standardized score
# --------------------------------------------------------------------------- #
def _sscp(a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Between-group (H) and within-group (E) SSCP matrices of a two-group MANOVA."""
    grand = np.vstack([a, b]).mean(axis=0)
    mean_a, mean_b = a.mean(axis=0), b.mean(axis=0)
    e = (a - mean_a).T @ (a - mean_a) + (b - mean_b).T @ (b - mean_b)
    h = (len(a) * np.outer(mean_a - grand, mean_a - grand)
         + len(b) * np.outer(mean_b - grand, mean_b - grand))
    return np.atleast_2d(h), np.atleast_2d(e)


def pillai_test(points_a, points_b) -> dict:
    """Pillai trace with the F-approximation p-value of R's ``summary.manova``.

    Returns ``{"pillai", "p_value", "F", "df1", "df2"}``; values are ``nan``
    when a group has fewer than two tokens or the error SSCP is singular.
    For two groups the approximation is exact-in-form: ``F = ((N − p − 1)/p)
    · V/(1 − V)`` on ``(p, N − p − 1)`` degrees of freedom.
    """
    nan = {"pillai": float("nan"), "p_value": float("nan"),
           "F": float("nan"), "df1": float("nan"), "df2": float("nan")}
    a, b = _clean(points_a), _clean(points_b)
    if len(a) < 2 or len(b) < 2:
        return nan
    p = a.shape[1]
    N = len(a) + len(b)
    h, e = _sscp(a, b)
    try:
        v = float(np.trace(np.linalg.solve(h + e, h)))
    except np.linalg.LinAlgError:
        return nan
    if not np.isfinite(v):
        return nan
    v = min(max(v, 0.0), 1.0)
    df1, df2 = p, N - p - 1
    if df2 <= 0:
        return {**nan, "pillai": v}
    if v >= 1.0:
        return {"pillai": v, "p_value": 0.0, "F": float("inf"), "df1": df1, "df2": df2}
    F = (df2 / df1) * v / (1.0 - v)
    return {"pillai": v, "p_value": float(f_dist.sf(F, df1, df2)), "F": F,
            "df1": df1, "df2": df2}


def pillai_score(points_a, points_b) -> float:
    """Pillai's trace for a two-group MANOVA (0 = overlap, → 1 = separated)."""
    return pillai_test(points_a, points_b)["pillai"]


def _error_sscp_full_rank(a: np.ndarray, b: np.ndarray) -> bool:
    """phontrast's guard: the within-class residual matrix must have full column rank."""
    resid = np.vstack([a - a.mean(axis=0), b - b.mean(axis=0)])
    return np.linalg.matrix_rank(resid) >= a.shape[1]


_STANDARDIZED_NA = {
    "H": float("nan"), "d2_plugin": float("nan"), "d2_unbiased": float("nan"),
    "pillai_eq": float("nan"), "pillai_eq_fallback": None, "d2_fallback": float("nan"),
    "bias_2p_over_H": float("nan"), "fragile_minority": None,
}


def pillai_standardized(V: float, n1: int, n2: int, p: int) -> dict:
    """Proportion-standardized Pillai score (phontrast ``pillai_overlap(proportion_standardized=TRUE)``).

    With realized counts ``n1``, ``n2`` (``N = n1 + n2``), ``p`` features,
    error df ``ν_e = N − 2`` and ``H = 2·n1·n2/N``:

    * ``d2_plugin = ν_e · [V/(1−V)] / (N · π1 · (1−π1))`` — the plug-in
      squared Mahalanobis separation implied by the raw Pillai score;
    * ``d2_unbiased = (ν_e − p − 1)/ν_e · d2_plugin − 2p/H`` — Lachenbruch &
      Mickey's (1968) unbiased estimator;
    * ``pillai_eq = d2_unbiased / (4 + d2_unbiased)`` — Becker's (1986) map
      back to the Pillai score a balanced design would produce.

    When ``d2_unbiased < 0`` (a common near-merger outcome) ``pillai_eq`` is
    ``nan``, ``pillai_eq_fallback`` is ``True`` and ``d2_fallback`` keeps the
    multiplicatively corrected first term — which still carries the
    split-dependent bias ``bias_2p_over_H`` and is *not* a balanced-design
    equivalent.  ``fragile_minority`` flags a minority class smaller than
    ``p + 1``.  All fields are ``nan`` when ``ν_e − p − 1 <= 0`` or ``V`` is
    not a finite score in ``[0, 1)``.
    """
    out = dict(_STANDARDIZED_NA)
    if V is None or not np.isfinite(V) or V < 0 or V >= 1 or n1 < 2 or n2 < 2:
        return out
    N = n1 + n2
    nu_e = N - 2
    if nu_e - p - 1 <= 0:
        return out
    H = 2.0 * n1 * n2 / N
    pi1 = n1 / N
    theta = V / (1.0 - V)
    d2_plugin = nu_e * theta / (N * pi1 * (1.0 - pi1))
    first_term = (nu_e - p - 1) / nu_e * d2_plugin
    bias = 2.0 * p / H
    d2_unbiased = first_term - bias
    fallback = bool(d2_unbiased < 0)
    out.update({
        "H": H, "d2_plugin": d2_plugin, "d2_unbiased": d2_unbiased,
        "pillai_eq": float("nan") if fallback else d2_unbiased / (4.0 + d2_unbiased),
        "pillai_eq_fallback": fallback,
        "d2_fallback": first_term if fallback else float("nan"),
        "bias_2p_over_H": bias,
        "fragile_minority": bool(min(n1, n2) < p + 1),
    })
    return out


def pillai_null_p95(n1: int, n2: int) -> float:
    """Stanley & Sneller's (2023, Eq. 1) 95th-percentile Pillai under merger: ``e / m``.

    ``m`` is the mean tokens per vowel class (``(n1 + n2) / 2``).  Berry
    (2026b) shows the formula runs a few percent below the exact null
    quantile, so treat it as a guide, not a test.
    """
    m = (n1 + n2) / 2.0
    if m <= 0:
        return float("nan")
    return float(min(1.0, math.e / m))


def pillai_perm_p(points_a, points_b, n_perm: int = 1000, seed: int = 0) -> float:
    """Permutation p-value for the Pillai trace (label shuffling; Nycz & Hall-Lew, 2013)."""
    a, b = _clean(points_a), _clean(points_b)
    if len(a) < 3 or len(b) < 3:
        return float("nan")
    observed = pillai_score(a, b)
    if np.isnan(observed):
        return float("nan")
    combined = np.vstack([a, b])
    na = len(a)
    rng = np.random.RandomState(seed)
    count = 0
    for _ in range(n_perm):
        perm = rng.permutation(len(combined))
        v = pillai_score(combined[perm[:na]], combined[perm[na:]])
        if not np.isnan(v) and v >= observed:
            count += 1
    return float((count + 1) / (n_perm + 1))


# --------------------------------------------------------------------------- #
# Parametric distances
# --------------------------------------------------------------------------- #
def bhattacharyya(points_a, points_b, eps: float = RIDGE) -> tuple[float, float]:
    """``(distance, affinity)`` of two fitted Gaussians (phontrast ``bhattacharyya_mvnorm``).

    ``distance = ⅛ Δμ' S⁻¹ Δμ + ½ log(|S| / sqrt(|S1||S2|))`` with
    ``S = (S1 + S2)/2`` after an ``eps`` ridge; ``affinity = exp(−distance)``
    (1 = identical, 0 = disjoint).
    """
    a, b = _clean(points_a), _clean(points_b)
    d = a.shape[1]
    if min(len(a), len(b)) < kde_min_category_tokens(d):
        return float("nan"), float("nan")
    mu1, mu2 = a.mean(axis=0), b.mean(axis=0)
    S1 = np.atleast_2d(np.cov(a.T)) + np.eye(d) * eps
    S2 = np.atleast_2d(np.cov(b.T)) + np.eye(d) * eps
    S = 0.5 * (S1 + S2)
    try:
        diff = mu2 - mu1
        term1 = 0.125 * diff @ np.linalg.solve(S, diff)
        signs, logdets = zip(*(np.linalg.slogdet(m) for m in (S, S1, S2)))
    except np.linalg.LinAlgError:
        return float("nan"), float("nan")
    if any(s <= 0 for s in signs):
        return float("nan"), float("nan")
    term2 = 0.5 * (logdets[0] - 0.5 * (logdets[1] + logdets[2]))
    dist = float(term1 + term2)
    return dist, float(math.exp(-dist))


def bhattacharyya_affinity(points_a, points_b, eps: float = RIDGE) -> float:
    """Bhattacharyya affinity ``exp(−distance)`` (1 = identical Gaussians)."""
    return bhattacharyya(points_a, points_b, eps)[1]


def mahalanobis_distance(points_a, points_b, eps: float = RIDGE) -> float:
    """Mahalanobis distance between the two means under the pooled covariance."""
    a, b = _clean(points_a), _clean(points_b)
    d = a.shape[1]
    if min(len(a), len(b)) < kde_min_category_tokens(d):
        return float("nan")
    n1, n2 = len(a), len(b)
    pooled = ((n1 - 1) * np.atleast_2d(np.cov(a.T)) + (n2 - 1) * np.atleast_2d(np.cov(b.T))) / (n1 + n2 - 2)
    pooled = pooled + np.eye(d) * eps
    diff = b.mean(axis=0) - a.mean(axis=0)
    try:
        q = float(diff @ np.linalg.solve(pooled, diff))
    except np.linalg.LinAlgError:
        return float("nan")
    return float(math.sqrt(max(q, 0.0)))


# --------------------------------------------------------------------------- #
# One pair, all metrics (+ bootstrap)
# --------------------------------------------------------------------------- #
def pair_metrics(
    points_a, points_b,
    density: str = "kde",
    bw: str = "scott.diag",
    loo: bool = True,
    mc_n: int = MC_N,
    seed: Optional[int] = 0,
    eps: float = RIDGE,
) -> dict:
    """Every phontrast metric for one category pair, keyed by phontrast's column names.

    Keys: ``n_a, n_b, n_tokens, pillai, pillai_p_value, bhatt_dist,
    bhatt_affinity, jsd, js_distance, mahalanobis_dist, percent_overlap`` plus
    the proportion-standardized fields from :func:`pillai_standardized` and
    ``pillai_null_p95``.  Metrics a category is too small for are ``nan``.
    """
    a, b = _clean(points_a), _clean(points_b)
    if a.shape[1] != b.shape[1]:
        raise ValueError("points_a and points_b must have the same number of columns")
    d = a.shape[1]
    n1, n2 = len(a), len(b)
    row: dict = {"n_a": n1, "n_b": n2, "n_tokens": n1 + n2}

    pt = pillai_test(a, b)
    row["pillai"], row["pillai_p_value"] = pt["pillai"], pt["p_value"]

    dense_ok = min(n1, n2) >= kde_min_category_tokens(d)
    row["bhatt_dist"], row["bhatt_affinity"] = bhattacharyya(a, b, eps) if dense_ok else (float("nan"),) * 2
    mc = _mc_pair(a, b, density, bw, mc_n, seed) if dense_ok else None
    jsd = _jsd_mc(mc, loo=loo and density == "kde") if mc is not None else float("nan")
    row["jsd"] = jsd
    row["js_distance"] = float(math.sqrt(jsd)) if np.isfinite(jsd) else float("nan")
    row["mahalanobis_dist"] = mahalanobis_distance(a, b, eps) if dense_ok else float("nan")
    row["percent_overlap"] = _overlap_mc(mc) if mc is not None else float("nan")

    std = (pillai_standardized(row["pillai"], n1, n2, d)
           if n1 >= 2 and n2 >= 2 and _error_sscp_full_rank(a, b) else dict(_STANDARDIZED_NA))
    row.update(std)
    row["pillai_null_p95"] = pillai_null_p95(n1, n2)
    return row


def bootstrap_pair_metrics(
    points_a, points_b,
    n_boot: int = 1000,
    conf_level: float = 0.95,
    seed: Optional[int] = 0,
    metrics: Sequence[str] = METRIC_COLUMNS,
    **opts,
) -> dict:
    """phontrast-style pooled bootstrap: ``<metric>_n_boot/_mean/_sd/_ci_lower/_ci_upper``.

    Tokens are resampled with replacement from the *pooled* pair (so the
    split between the two vowels varies as it would in a new sample), every
    metric is recomputed on each replicate, and percentile intervals at
    ``conf_level`` are taken over the finite replicates.  Replicates in which a
    category drops below the KDE minimum are skipped, as phontrast skips
    replicates whose estimators error.  ``opts`` go to :func:`pair_metrics`.
    """
    a, b = _clean(points_a), _clean(points_b)
    d = a.shape[1]
    floor = kde_min_category_tokens(d)
    pooled = np.vstack([a, b])
    labels = np.r_[np.zeros(len(a), dtype=int), np.ones(len(b), dtype=int)]
    n = len(pooled)
    rng = np.random.default_rng(seed)
    draws: dict[str, list[float]] = {m: [] for m in metrics}
    if n >= 2 * floor:
        for _ in range(int(n_boot)):
            idx = rng.integers(0, n, n)
            lab = labels[idx]
            ra, rb = pooled[idx][lab == 0], pooled[idx][lab == 1]
            if len(ra) < floor or len(rb) < floor:
                continue
            # Fresh Monte-Carlo draws per replicate (only matters for mvnorm).
            row = pair_metrics(ra, rb, **{**opts, "seed": int(rng.integers(0, 2**31 - 1))})
            for m in metrics:
                draws[m].append(row.get(m, float("nan")))
    alpha = 1.0 - conf_level
    out: dict = {"n_boot": int(n_boot), "conf_level": conf_level}
    for m in metrics:
        vals = np.asarray([v for v in draws[m] if v is not None], dtype=float)
        vals = vals[np.isfinite(vals)]
        out[f"{m}_n_boot"] = int(len(vals))
        out[f"{m}_mean"] = float(vals.mean()) if len(vals) else float("nan")
        out[f"{m}_sd"] = float(vals.std(ddof=1)) if len(vals) > 1 else float("nan")
        if len(vals):
            lo, hi = np.quantile(vals, [alpha / 2, 1 - alpha / 2])
            out[f"{m}_ci_lower"], out[f"{m}_ci_upper"] = float(lo), float(hi)
        else:
            out[f"{m}_ci_lower"] = out[f"{m}_ci_upper"] = float("nan")
    return out


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
    density: str = "kde",
    bw: str = "scott.diag",
    group: Optional[str] = None,
    group_value: Optional[object] = None,
    bootstrap: int = 0,
    conf_level: float = 0.95,
    permutations: int = 0,
    seed: Optional[int] = 0,
    mc_n: int = MC_N,
) -> dict:
    """All metrics for one vowel pair on one (sub)frame, as a flat row dict.

    ``bootstrap`` > 0 adds phontrast-style bootstrap columns for every metric;
    ``permutations`` > 0 adds ``pillai_perm_p`` (label-shuffling test).
    """
    dims = _resolve_dimensions(df, dimensions)
    canon = canonical_vowel_series(df, schema)
    va, vb = canonical_vowel(vowel_a), canonical_vowel(vowel_b)
    a = df.loc[canon == va, dims].to_numpy(dtype=float) if dims else np.empty((0, 0))
    b = df.loc[canon == vb, dims].to_numpy(dtype=float) if dims else np.empty((0, 0))
    a, b = _clean(a) if dims else a, _clean(b) if dims else b

    row: dict = {
        "group": group, "group_value": group_value,
        "vowel_a": va, "vowel_b": vb, "pair": f"{va}~{vb}",
    }
    opts = dict(density=density, bw=bw, mc_n=mc_n)
    if dims:
        row.update(pair_metrics(a, b, seed=seed, **opts))
    else:
        row.update({"n_a": len(a), "n_b": len(b), "n_tokens": len(a) + len(b)})
    if dims and permutations > 0 and np.isfinite(row.get("pillai", float("nan"))):
        row["pillai_perm_p"] = pillai_perm_p(a, b, n_perm=permutations, seed=seed or 0)
    if dims and bootstrap > 0:
        row.update(bootstrap_pair_metrics(a, b, n_boot=bootstrap, conf_level=conf_level,
                                          seed=seed, **opts))
    row["density"] = density
    row["bw"] = bw if density == "kde" else None
    row["features"] = "×".join(dims)
    return row


def pairwise_separation(
    df: pd.DataFrame,
    schema: ColumnSchema,
    vowels: Optional[Sequence[str]] = None,
    group_by: Optional[str] = None,
    dimensions: Optional[Sequence[str]] = None,
    density: str = "kde",
    bw: str = "scott.diag",
    min_tokens: int = MIN_TOKENS,
    bootstrap: int = 0,
    conf_level: float = 0.95,
    permutations: int = 0,
    seed: Optional[int] = 0,
    mc_n: int = MC_N,
) -> pd.DataFrame:
    """Separation metrics for every vowel pair, optionally within each group.

    One row per (group level × vowel pair) with phontrast's column names
    (``jsd``, ``js_distance``, ``pillai``, ``pillai_eq``, ``pillai_p_value``,
    ``bhatt_dist``, ``bhatt_affinity``, ``mahalanobis_dist``,
    ``percent_overlap``, …).  ``min_tokens`` is phontrast's threshold on the
    pair's *total* tokens (default 20); a pair also needs at least two tokens
    of each vowel.  ``bootstrap`` / ``permutations`` add uncertainty columns.
    """
    if vowels:
        wanted = [canonical_vowel(v) for v in vowels]
    else:
        wanted = sorted(canonical_vowel_series(df, schema).dropna().unique())
    pairs = list(itertools.combinations(sorted(set(wanted)), 2))

    frames: list[tuple[Optional[object], pd.DataFrame]] = []
    if group_by and group_by in df.columns:
        for gval, sub in df.groupby(group_by, dropna=False):
            frames.append((gval, sub))
    else:
        frames.append((None, df))

    dims = _resolve_dimensions(df, dimensions)
    rows: list[dict] = []
    for gval, sub in frames:
        sub_canon = canonical_vowel_series(sub, schema)
        complete = sub[dims].notna().all(axis=1) if dims else pd.Series(True, index=sub.index)
        counts = sub_canon[complete].value_counts()
        for va, vb in pairs:
            n_a, n_b = int(counts.get(va, 0)), int(counts.get(vb, 0))
            if n_a < 2 or n_b < 2 or n_a + n_b < min_tokens:
                continue
            row = pair_separation(
                sub, schema, va, vb, dimensions=dims, density=density, bw=bw,
                group=group_by, group_value=gval, bootstrap=bootstrap,
                conf_level=conf_level, permutations=permutations, seed=seed, mc_n=mc_n,
            )
            row["vowel_a_label"] = vowel_display_label(va)
            row["vowel_b_label"] = vowel_display_label(vb)
            rows.append(row)

    result = pd.DataFrame(rows)
    if not result.empty:
        result = result.sort_values(
            ["group_value", "jsd"], ascending=[True, False], na_position="first"
        ).reset_index(drop=True)
    return result
