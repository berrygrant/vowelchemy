import numpy as np
import pytest

from vowelchemy import metrics, sample_data
from vowelchemy.analysis import add_vowel_labels, join_demographics
from vowelchemy.normalization import normalize
from vowelchemy.schema import ColumnSchema


def _cluster(center, n=200, spread=0.15, seed=0):
    rng = np.random.RandomState(seed)
    return rng.normal(center, spread, size=(n, 2))


def test_jsd_bounds_and_symmetry():
    a = _cluster([0, 0], seed=1)
    b = _cluster([0, 0], seed=2)  # same distribution
    far = _cluster([50, 50], seed=3)  # disjoint
    jsd_same = metrics.jensen_shannon_divergence(a, b)
    jsd_far = metrics.jensen_shannon_divergence(a, far)
    assert 0.0 <= jsd_same <= 1.0
    assert jsd_same < 0.2  # overlapping -> low
    assert jsd_far > 0.95  # disjoint -> ~1
    # symmetric
    assert metrics.jensen_shannon_divergence(a, far) == pytest.approx(
        metrics.jensen_shannon_divergence(far, a), abs=1e-9
    )


def test_jsd_too_few_points_is_nan():
    assert np.isnan(metrics.jensen_shannon_divergence(np.array([[1.0, 2.0]]), _cluster([0, 0])))


def test_pillai_and_bhattacharyya_extremes():
    a = _cluster([0, 0], seed=1)
    b = _cluster([0, 0], seed=2)
    far = _cluster([50, 50], seed=3)
    assert metrics.pillai_score(a, far) > 0.9
    assert metrics.pillai_score(a, b) < 0.2
    assert metrics.bhattacharyya_overlap(a, b) > 0.8   # near-identical
    assert metrics.bhattacharyya_overlap(a, far) < 0.05  # disjoint


def test_jsd_1d():
    a = np.random.RandomState(0).normal(0, 1, size=(300, 1))
    b = np.random.RandomState(1).normal(10, 1, size=(300, 1))
    assert metrics.jensen_shannon_divergence(a, b) > 0.9


def test_pairwise_separation_captures_merger():
    """On the demo data, LOT~THOUGHT separation should fall across apparent time."""
    tokens, speakers = sample_data.make_demo_dataset()
    schema = ColumnSchema.detect(tokens)
    df = add_vowel_labels(join_demographics(tokens, speakers, schema), schema)
    df = normalize(df, schema, "lobanov").data
    sep = metrics.pairwise_separation(df, schema, vowels=["AA", "AO"], group_by="Age Group")
    by_group = sep.set_index("group_value")["JSD"]
    assert by_group["Older"] > by_group["Middle"] > by_group["Young"]
    assert by_group["Young"] < 0.4  # nearly merged for the young


def test_pairwise_separation_respects_min_tokens():
    tokens, speakers = sample_data.make_demo_dataset()
    schema = ColumnSchema.detect(tokens)
    df = add_vowel_labels(join_demographics(tokens, speakers, schema), schema)
    sep = metrics.pairwise_separation(df, schema, vowels=["IY", "EH"], min_tokens=10_000)
    assert sep.empty  # nothing meets an impossible threshold


def test_jsd_ci_brackets_estimate():
    a = _cluster([0, 0], seed=1)
    b = _cluster([3, 3], seed=2)
    jsd = metrics.jensen_shannon_divergence(a, b)
    lo, hi = metrics.jsd_ci(a, b, n_boot=60, seed=0)
    assert not np.isnan(lo) and lo <= hi
    assert lo - 0.2 <= jsd <= hi + 0.2


def test_pillai_p_lower_for_separated():
    a = _cluster([0, 0], seed=1)
    far = _cluster([50, 50], seed=3)
    same = _cluster([0, 0], seed=2)
    p_sep = metrics.pillai_p(a, far, n_perm=200)
    p_same = metrics.pillai_p(a, same, n_perm=200)
    assert p_sep < 0.05
    assert p_same > p_sep
