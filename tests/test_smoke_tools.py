"""Integration smoke tests for the external tools (R11).

These are *opt-in*: each is skipped unless the relevant tool (MFA / new-fave /
R+phonJSD) is installed and on PATH. On a machine that has them — a lab box or a
CI runner with the tools provisioned — they verify Vowelchemy can actually drive
each tool, catching version drift that unit tests can't.
"""

import pytest

from vowelchemy import alignment, extraction, phonjsd, sample_data
from vowelchemy.analysis import add_vowel_labels, join_demographics
from vowelchemy.normalization import normalize
from vowelchemy.schema import ColumnSchema

_mfa = alignment.mfa_status()
_nf = extraction.newfave_status()
_pj = phonjsd.phonjsd_status()


@pytest.mark.skipif(not _mfa.available, reason="MFA not installed")
def test_mfa_detected_and_versioned():
    assert _mfa.version  # invokable and reports a version


@pytest.mark.skipif(not _nf.available, reason="new-fave not installed")
def test_newfave_detected_and_versioned():
    assert _nf.version


@pytest.mark.skipif(not _pj.available, reason="R + phonJSD not installed")
def test_phonjsd_end_to_end(tmp_path):
    tokens, speakers = sample_data.make_demo_dataset(n_per_cell=1, tokens_per_vowel=15)
    schema = ColumnSchema.detect(tokens)
    df = add_vowel_labels(join_demographics(tokens, speakers, schema), schema)
    df = normalize(df, schema, "lobanov").data
    res = phonjsd.compare_overlap_metrics(
        df, features=["F1_norm", "F2_norm"], category_col="vowel_canon", work_dir=tmp_path
    )
    assert res.ok and res.data is not None and not res.data.empty
