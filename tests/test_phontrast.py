import pandas as pd
import pytest

from vowelchemy import phontrast


def test_r_string_vector():
    assert phontrast._r_string_vector(["F1_norm", "F2_norm"]) == 'c("F1_norm", "F2_norm")'


def test_build_r_script_calls_phontrast_and_balance_correction():
    script = phontrast.build_r_script(["F1_norm", "F2_norm"], "vowel_canon", "Age Group")
    assert "library(phontrast)" in script
    assert "phontrast(" in script and "compare_overlap_metrics" not in script  # deprecated in 2.0.0
    assert "pillai_overlap(sub_i, features, category_col, proportion_standardized = TRUE)" in script
    assert 'features     <- c("F1_norm", "F2_norm")' in script
    assert 'category_col <- "vowel_canon"' in script
    assert 'group_col    <- "Age Group"' in script
    assert 'bw = "Hpi"' in script and 'density = "kde"' in script
    assert "do_boot = FALSE" in script and "progress = FALSE" in script
    assert "utils::combn(vowels, 2" in script  # one phontrast() call per vowel pair
    assert "pillai_null_p95" in script

    script_nogroup = phontrast.build_r_script(["F1_norm", "F2_norm"], "vowel_canon", None)
    assert "group_col    <- NULL" in script_nogroup


def test_build_r_script_bootstrap_and_options():
    script = phontrast.build_r_script(
        ["F1_norm"], "vowel_canon", None, bw="scott.diag", density="mvnorm",
        mc_n=5000, min_tokens=30, n_boot=250, conf_level=0.9,
    )
    assert "do_boot = TRUE" in script and "n_boot = 250" in script and "conf_level = 0.9" in script
    assert 'bw = "scott.diag"' in script and 'density = "mvnorm"' in script
    assert "mc_n = 5000L" in script and "min_tokens = 30" in script
    with pytest.raises(ValueError):
        phontrast.build_r_script(["F1_norm"], "vowel_canon", None, bw="scott")  # not an R option


def test_status_is_graceful_without_r():
    status = phontrast.phontrast_status()
    assert isinstance(status.available, bool)  # never raises even if R is absent


def test_status_requires_a_new_enough_phontrast():
    old = phontrast.PhontrastStatus(rscript_path="/usr/bin/Rscript", package="phontrast", version="1.2.0")
    assert old.package_installed and not old.supported and not old.available
    assert "2.3.1" in old.install_hint and "install.packages" in old.install_hint
    legacy = phontrast.PhontrastStatus(rscript_path="/usr/bin/Rscript", package="phonJSD", version="1.0.0")
    assert not legacy.available
    new = phontrast.PhontrastStatus(rscript_path="/usr/bin/Rscript", package="phontrast", version="2.4.1")
    assert new.supported and new.available
    assert new.install_hint == phontrast.PHONTRAST_INSTALL_HINT


def test_run_phontrast_without_r(tmp_path):
    df = pd.DataFrame(
        {"vowel_canon": ["IY", "EH"], "F1_norm": [-1.0, 1.0], "F2_norm": [1.0, -1.0]}
    )
    res = phontrast.run_phontrast(
        df, features=["F1_norm", "F2_norm"], category_col="vowel_canon",
        work_dir=tmp_path, rscript="definitely-not-rscript-xyz",
    )
    # It should write the R driver + input CSV regardless, and report gracefully.
    assert res.script_path.exists()
    assert res.input_csv.exists()
    assert not res.ok
    assert any("Rscript" in n for n in res.notes)
    assert phontrast.compare_overlap_metrics is phontrast.run_phontrast  # pre-0.3 name
