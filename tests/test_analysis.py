import pandas as pd
import pytest

from vowelchemy import analysis
from vowelchemy.schema import ColumnSchema


@pytest.fixture
def tokens():
    return pd.DataFrame(
        {
            "speaker": ["S1", "S1", "S2", "S2"],
            "vowel": ["IY1", "EH1", "IY1", "EH1"],
            "F1": [300.0, 600.0, 320.0, 610.0],
            "F2": [2300.0, 1850.0, 2280.0, 1830.0],
        }
    )


@pytest.fixture
def demographics():
    return pd.DataFrame(
        {"speaker": ["S1", "S2"], "Sex": ["F", "M"], "Age Group": ["Young", "Older"]}
    )


def test_join_demographics(tokens, demographics):
    schema = ColumnSchema.detect(tokens)
    merged = analysis.join_demographics(tokens, demographics, schema)
    assert "Sex" in merged.columns and "Age Group" in merged.columns
    assert list(merged.loc[merged.speaker == "S1", "Sex"]) == ["F", "F"]


def test_add_labels_and_list(tokens):
    schema = ColumnSchema.detect(tokens)
    labeled = analysis.add_vowel_labels(tokens, schema)
    assert set(labeled["vowel_canon"]) == {"IY", "EH"}
    vt = analysis.list_vowels(tokens, schema)
    assert set(vt["vowel"]) == {"IY", "EH"}
    assert vt["n"].sum() == 4


def test_select_vowels_by_keyword(tokens):
    schema = ColumnSchema.detect(tokens)
    only_beet = analysis.select_vowels(tokens, schema, ["BEET"])
    assert set(only_beet["vowel"]) == {"IY1"}
    assert len(only_beet) == 2


def test_candidate_grouping_excludes_formants(tokens, demographics):
    schema = ColumnSchema.detect(tokens)
    merged = analysis.add_vowel_labels(
        analysis.join_demographics(tokens, demographics, schema), schema
    )
    cols = analysis.candidate_grouping_columns(merged, schema)
    assert "F1" not in cols and "F2" not in cols
    assert "Sex" in cols and "Age Group" in cols


def test_apply_filters(tokens, demographics):
    schema = ColumnSchema.detect(tokens)
    merged = analysis.join_demographics(tokens, demographics, schema)
    filtered = analysis.apply_filters(merged, {"Sex": ["F"]})
    assert set(filtered["speaker"]) == {"S1"}
    # empty filter is a no-op
    assert len(analysis.apply_filters(merged, {"Sex": []})) == len(merged)


def test_summarize(tokens, demographics):
    schema = ColumnSchema.detect(tokens)
    merged = analysis.add_vowel_labels(
        analysis.join_demographics(tokens, demographics, schema), schema
    )
    summary = analysis.summarize(merged, schema, ["Sex", "vowel_canon"], ["F1"])
    assert "F1_mean" in summary.columns and "F1_count" in summary.columns
    assert len(summary) == 4  # 2 sexes x 2 vowels
