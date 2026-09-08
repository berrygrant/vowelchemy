"""Integration smoke tests for the external tools (R11).

These are *opt-in*: each is skipped unless the relevant tool (MFA / new-fave /
R+phontrast) is installed and on PATH. On a machine that has them — a lab box or a
CI runner with the tools provisioned — they verify Vowelchemy can actually drive
each tool, catching version drift that unit tests can't.
"""

import pytest

import numpy as np

from vowelchemy import alignment, extraction, metrics, phontrast, sample_data
from vowelchemy.analysis import add_vowel_labels, join_demographics
from vowelchemy.normalization import normalize
from vowelchemy.schema import ColumnSchema

# wait=True: these tests assert on real version strings, so probe synchronously
_mfa = alignment.mfa_status(wait=True)
_nf = extraction.newfave_status(wait=True)
_pj = phontrast.phontrast_status(wait=True)


@pytest.mark.skipif(not _mfa.available, reason="MFA not installed")
def test_mfa_detected_and_versioned():
    assert _mfa.version  # invokable and reports a version


@pytest.mark.skipif(not _nf.available, reason="new-fave not installed")
def test_newfave_detected_and_versioned():
    assert _nf.version


@pytest.mark.skipif(not _pj.available, reason="R + phontrast not installed")
def test_phontrast_end_to_end(tmp_path):
    tokens, speakers = sample_data.make_demo_dataset(n_per_cell=1, tokens_per_vowel=15)
    schema = ColumnSchema.detect(tokens)
    df = add_vowel_labels(join_demographics(tokens, speakers, schema), schema)
    df = normalize(df, schema, "lobanov").data
    res = phontrast.run_phontrast(
        df, features=["F1_norm", "F2_norm"], category_col="vowel_canon", work_dir=tmp_path,
        bw="scott.diag",  # the bandwidth the Python port implements exactly
    )
    assert res.ok and res.data is not None and not res.data.empty
    for col in ("vowel_a", "vowel_b", "jsd", "js_distance", "pillai", "pillai_p_value",
                "bhatt_affinity", "percent_overlap", "pillai_eq", "pillai_null_p95"):
        assert col in res.data.columns

    # Parity: the built-in engine is a port of phontrast, so with the same
    # bandwidth every metric must agree to floating-point precision. This is
    # the drift alarm for future phontrast releases.
    py = metrics.pairwise_separation(df, schema, bw="scott.diag")
    merged = py.merge(res.data, on=["vowel_a", "vowel_b"], suffixes=("_py", "_r"))
    assert len(merged) == len(res.data)
    for col in ("jsd", "js_distance", "pillai", "pillai_p_value", "pillai_eq", "bhatt_dist",
                "bhatt_affinity", "mahalanobis_dist", "percent_overlap", "pillai_null_p95"):
        a, b = merged[f"{col}_py"].astype(float), merged[f"{col}_r"].astype(float)
        assert np.allclose(a, b, atol=1e-8, equal_nan=True), col
