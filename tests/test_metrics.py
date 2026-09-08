import math

import numpy as np
import pytest
from scipy.stats import f_oneway

from vowelchemy import metrics, sample_data
from vowelchemy.analysis import add_vowel_labels, join_demographics
from vowelchemy.normalization import normalize
from vowelchemy.schema import ColumnSchema


def _cluster(center, n=200, spread=0.15, seed=0):
    rng = np.random.RandomState(seed)
    return rng.normal(center, spread, size=(n, 2))


def _demo_frame():
    tokens, speakers = sample_data.make_demo_dataset()
    schema = ColumnSchema.detect(tokens)
    df = add_vowel_labels(join_demographics(tokens, speakers, schema), schema)
    return normalize(df, schema, "lobanov").data, schema


# --------------------------------------------------------------------------- #
# Jensen-Shannon divergence / distance
# --------------------------------------------------------------------------- #
def test_jsd_bounds_and_symmetry():
    a = _cluster([0, 0], seed=1)
    b = _cluster([0, 0], seed=2)  # same distribution
    far = _cluster([50, 50], seed=3)  # disjoint
    jsd_same = metrics.jensen_shannon_divergence(a, b)
    jsd_far = metrics.jensen_shannon_divergence(a, far)
    assert 0.0 <= jsd_same <= 1.0
    assert jsd_same < 0.2  # overlapping -> low
    assert jsd_far > 0.95  # disjoint -> ~1
    assert metrics.jensen_shannon_divergence(a, far) == pytest.approx(
        metrics.jensen_shannon_divergence(far, a), abs=1e-9
    )


def test_jsd_too_few_points_is_nan():
    assert np.isnan(metrics.jensen_shannon_divergence(np.array([[1.0, 2.0]]), _cluster([0, 0])))
    # phontrast's floor: each category needs d + 1 tokens for the KDE metrics.
    assert np.isnan(metrics.jensen_shannon_divergence(_cluster([0, 0], n=2), _cluster([0, 0])))
    assert not np.isnan(metrics.jensen_shannon_divergence(_cluster([0, 0], n=3), _cluster([0, 0])))


def test_jsd_1d():
    a = np.random.RandomState(0).normal(0, 1, size=(300, 1))
    b = np.random.RandomState(1).normal(10, 1, size=(300, 1))
    assert metrics.jensen_shannon_divergence(a, b) > 0.9


def test_js_distance_is_sqrt_of_jsd():
    a, b = _cluster([0, 0], seed=1), _cluster([0.4, 0.4], seed=2)
    jsd = metrics.jensen_shannon_divergence(a, b)
    assert metrics.jensen_shannon_distance(a, b) == pytest.approx(math.sqrt(jsd))
    row = metrics.pair_metrics(a, b)
    assert row["js_distance"] == pytest.approx(math.sqrt(row["jsd"]))
    assert row["js_distance"] >= row["jsd"]  # sqrt stretches the low end


def test_partial_leave_one_out_removes_resubstitution_bias():
    """Without the correction the self-density is inflated, so JSD is biased upward."""
    a, b = _cluster([0, 0], seed=1), _cluster([0, 0], seed=2)
    naive = metrics.jensen_shannon_divergence(a, b, loo=False)
    corrected = metrics.jensen_shannon_divergence(a, b, loo=True)
    assert naive > corrected
    assert corrected < 0.05


def test_mvnorm_density_matches_kde_on_gaussian_data():
    a, b = _cluster([0, 0], seed=1), _cluster([0.5, 0.5], seed=2)
    kde = metrics.jensen_shannon_divergence(a, b)
    mvn = metrics.jensen_shannon_divergence(a, b, density="mvnorm", seed=0)
    assert abs(kde - mvn) < 0.1
    # Seeded Monte-Carlo draws are reproducible.
    assert mvn == metrics.jensen_shannon_divergence(a, b, density="mvnorm", seed=0)


def test_full_scott_bandwidth_option():
    a, b = _cluster([0, 0], seed=1), _cluster([0.5, 0.5], seed=2)
    diag = metrics.jensen_shannon_divergence(a, b, bw="scott.diag")
    full = metrics.jensen_shannon_divergence(a, b, bw="scott")
    assert abs(diag - full) < 0.1
    with pytest.raises(ValueError):
        metrics.jensen_shannon_divergence(a, b, bw="nope")


# --------------------------------------------------------------------------- #
# Pillai: trace, F-test, balance correction, null threshold
# --------------------------------------------------------------------------- #
def test_pillai_extremes():
    a, b, far = _cluster([0, 0], seed=1), _cluster([0, 0], seed=2), _cluster([50, 50], seed=3)
    assert metrics.pillai_score(a, far) > 0.9
    assert metrics.pillai_score(a, b) < 0.2


def test_pillai_test_matches_anova_in_one_dimension():
    """With one feature the Pillai F-test is the one-way ANOVA F-test."""
    a = np.random.RandomState(0).normal(0, 1, size=(40, 1))
    b = np.random.RandomState(1).normal(0.6, 1, size=(25, 1))
    res = metrics.pillai_test(a, b)
    F, p = f_oneway(a.ravel(), b.ravel())
    assert res["F"] == pytest.approx(F)
    assert res["p_value"] == pytest.approx(p)
    assert (res["df1"], res["df2"]) == (1, 63)


def test_pillai_standardized_reproduces_phontrast_formula():
    # V = 0.3 from n1 = 30, n2 = 90 tokens in two dimensions (hand-computed).
    out = metrics.pillai_standardized(0.3, 30, 90, 2)
    assert out["H"] == pytest.approx(45.0)
    assert out["d2_plugin"] == pytest.approx(118 * (0.3 / 0.7) / (120 * 0.25 * 0.75))
    assert out["d2_unbiased"] == pytest.approx((115 / 118) * out["d2_plugin"] - 4 / 45)
    assert out["pillai_eq"] == pytest.approx(out["d2_unbiased"] / (4 + out["d2_unbiased"]))
    assert out["pillai_eq_fallback"] is False and np.isnan(out["d2_fallback"])
    assert out["bias_2p_over_H"] == pytest.approx(4 / 45)
    assert out["fragile_minority"] is False


def test_pillai_standardized_fallback_and_undefined_cases():
    near_merger = metrics.pillai_standardized(0.01, 10, 10, 2)
    assert near_merger["pillai_eq_fallback"] is True
    assert np.isnan(near_merger["pillai_eq"]) and not np.isnan(near_merger["d2_fallback"])
    # nu_e - p - 1 <= 0 -> everything NA
    undefined = metrics.pillai_standardized(0.3, 2, 3, 2)
    assert np.isnan(undefined["pillai_eq"]) and undefined["pillai_eq_fallback"] is None
    # A minority class smaller than p + 1 is flagged, not refused.
    fragile = metrics.pillai_standardized(0.3, 2, 40, 2)
    assert fragile["fragile_minority"] is True


def test_pillai_eq_removes_dependence_on_class_balance():
    """Same underlying separation, balanced vs 15/85 split: raw Pillai moves, pillai_eq barely."""
    rng = np.random.RandomState(7)
    mu_a, mu_b = np.array([0.0, 0.0]), np.array([1.4, 1.4])  # D^2 = 3.92
    balanced = metrics.pair_metrics(rng.normal(mu_a, 1, (400, 2)), rng.normal(mu_b, 1, (400, 2)))
    skewed = metrics.pair_metrics(rng.normal(mu_a, 1, (120, 2)), rng.normal(mu_b, 1, (680, 2)))
    raw_gap = abs(balanced["pillai"] - skewed["pillai"])
    eq_gap = abs(balanced["pillai_eq"] - skewed["pillai_eq"])
    assert raw_gap > 0.08  # imbalance depresses raw Pillai noticeably
    assert eq_gap < raw_gap / 3
    assert balanced["pillai_eq"] == pytest.approx(3.92 / 7.92, abs=0.06)


def test_pillai_null_p95_is_stanley_sneller_e_over_m():
    assert metrics.pillai_null_p95(10, 10) == pytest.approx(math.e / 10)  # the paper's 0.2718 example
    assert metrics.pillai_null_p95(1, 1) == 1.0  # clipped
    assert metrics.pillai_null_p95(150, 150) < 0.02


def test_pillai_perm_p_lower_for_separated():
    a, far, same = _cluster([0, 0], seed=1), _cluster([50, 50], seed=3), _cluster([0, 0], seed=2)
    p_sep = metrics.pillai_perm_p(a, far, n_perm=200)
    p_same = metrics.pillai_perm_p(a, same, n_perm=200)
    assert p_sep < 0.05
    assert p_same > p_sep


# --------------------------------------------------------------------------- #
# Parametric distances and overlap
# --------------------------------------------------------------------------- #
def test_bhattacharyya_and_mahalanobis_extremes():
    a, b, far = _cluster([0, 0], seed=1), _cluster([0, 0], seed=2), _cluster([50, 50], seed=3)
    dist_same, aff_same = metrics.bhattacharyya(a, b)
    dist_far, aff_far = metrics.bhattacharyya(a, far)
    assert aff_same > 0.8 and dist_same < 0.25  # near-identical
    assert aff_far < 0.05 and dist_far > dist_same  # disjoint
    assert aff_same == pytest.approx(math.exp(-dist_same))
    assert metrics.mahalanobis_distance(a, b) < 0.5
    assert metrics.mahalanobis_distance(a, far) > 100


def test_percent_overlap_extremes():
    a, b, far = _cluster([0, 0], seed=1), _cluster([0, 0], seed=2), _cluster([50, 50], seed=3)
    assert metrics.percent_overlap(a, b) > 0.7
    assert metrics.percent_overlap(a, far) < 0.01
    assert metrics.percent_overlap(a, b, density="mvnorm") > 0.7


def test_pair_metrics_has_phontrast_columns():
    row = metrics.pair_metrics(_cluster([0, 0], n=40, seed=1), _cluster([0.3, 0.3], n=120, seed=2))
    for col in ("n_tokens", "pillai", "pillai_p_value", "bhatt_dist", "bhatt_affinity", "jsd",
                "js_distance", "mahalanobis_dist", "percent_overlap", "pillai_eq",
                "pillai_eq_fallback", "pillai_null_p95"):
        assert col in row
    assert row["n_tokens"] == 160
    assert 0 <= row["pillai_p_value"] <= 1


# --------------------------------------------------------------------------- #
# Bootstrap
# --------------------------------------------------------------------------- #
def test_bootstrap_brackets_estimate_and_takes_sqrt_per_replicate():
    a, b = _cluster([0, 0], seed=1), _cluster([1.5, 1.5], seed=2)
    point = metrics.pair_metrics(a, b)
    boot = metrics.bootstrap_pair_metrics(a, b, n_boot=60, seed=0)
    assert boot["jsd_n_boot"] == 60
    assert boot["jsd_ci_lower"] <= boot["jsd_ci_upper"]
    assert boot["jsd_ci_lower"] - 0.15 <= point["jsd"] <= boot["jsd_ci_upper"] + 0.15
    # sqrt is applied to each replicate (phontrast), so by Jensen's inequality
    # the mean distance is at most the sqrt of the mean divergence.
    assert boot["js_distance_mean"] <= math.sqrt(boot["jsd_mean"]) + 1e-9
    assert boot["pillai_eq_n_boot"] > 0
    for col in ("pillai", "bhatt_affinity", "mahalanobis_dist", "percent_overlap"):
        assert not np.isnan(boot[f"{col}_ci_upper"])


# --------------------------------------------------------------------------- #
# Pairwise separation on the demo corpus
# --------------------------------------------------------------------------- #
def test_pairwise_separation_captures_merger():
    """On the demo data, LOT~THOUGHT separation should fall across apparent time."""
    df, schema = _demo_frame()
    sep = metrics.pairwise_separation(df, schema, vowels=["AA", "AO"], group_by="Age Group")
    by_group = sep.set_index("group_value")
    assert by_group.loc["Older", "jsd"] > by_group.loc["Middle", "jsd"] > by_group.loc["Young", "jsd"]
    assert by_group.loc["Young", "jsd"] < 0.4  # nearly merged for the young
    assert by_group.loc["Older", "js_distance"] > by_group.loc["Young", "js_distance"]
    assert by_group.loc["Older", "pillai_eq"] > by_group.loc["Young", "pillai_eq"]
    assert np.allclose(by_group["pillai_null_p95"], math.e / 150)  # 150 tokens per vowel
    assert set(sep["density"]) == {"kde"} and set(sep["bw"]) == {"scott.diag"}


def test_pairwise_separation_respects_min_tokens():
    df, schema = _demo_frame()
    sep = metrics.pairwise_separation(df, schema, vowels=["IY", "EH"], min_tokens=10_000)
    assert sep.empty  # nothing meets an impossible threshold


def test_pairwise_separation_bootstrap_and_permutation_columns():
    df, schema = _demo_frame()
    sep = metrics.pairwise_separation(df, schema, vowels=["AA", "AO"], group_by="Age Group",
                                      bootstrap=30, permutations=50)
    for col in ("jsd_ci_lower", "jsd_ci_upper", "js_distance_ci_upper", "pillai_eq_mean",
                "pillai_perm_p", "n_boot", "conf_level"):
        assert col in sep.columns
    assert (sep["n_boot"] == 30).all()
