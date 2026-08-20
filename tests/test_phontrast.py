import pandas as pd

from vowelchemy import phontrast


def test_r_string_vector():
    assert phontrast._r_string_vector(["F1_norm", "F2_norm"]) == 'c("F1_norm", "F2_norm")'


def test_build_r_script_group_and_null():
    script_grouped = phontrast.build_r_script(
        ["F1_norm", "F2_norm"], "vowel_canon", "Age Group", "wide"
    )
    assert "library(phontrast)" in script_grouped
    assert "compare_overlap_metrics" in script_grouped
    assert 'features     = c("F1_norm", "F2_norm")' in script_grouped
    assert 'category_col = "vowel_canon"' in script_grouped
    assert 'group_col    = "Age Group"' in script_grouped

    script_nogroup = phontrast.build_r_script(["F1_norm", "F2_norm"], "vowel_canon", None)
    assert "group_col    = NULL" in script_nogroup


def test_status_is_graceful_without_r():
    status = phontrast.phontrast_status()
    assert isinstance(status.available, bool)  # never raises even if R is absent


def test_compare_overlap_metrics_without_r(tmp_path):
    df = pd.DataFrame(
        {"vowel_canon": ["IY", "EH"], "F1_norm": [-1.0, 1.0], "F2_norm": [1.0, -1.0]}
    )
    res = phontrast.compare_overlap_metrics(
        df, features=["F1_norm", "F2_norm"], category_col="vowel_canon",
        work_dir=tmp_path, rscript="definitely-not-rscript-xyz",
    )
    # It should write the R driver + input CSV regardless, and report gracefully.
    assert res.script_path.exists()
    assert res.input_csv.exists()
    assert not res.ok
    assert any("Rscript" in n for n in res.notes)
