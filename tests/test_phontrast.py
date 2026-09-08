import stat

import pandas as pd
import pytest

from vowelchemy import phontrast, toolenv


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    """Settings in a temp home, no chosen R, no R found via PATH/platform/conda."""
    monkeypatch.setenv("VOWELCHEMY_HOME", str(tmp_path / "state"))
    monkeypatch.delenv("VOWELCHEMY_RSCRIPT", raising=False)
    monkeypatch.setattr(phontrast, "_platform_rscripts", lambda: [])
    monkeypatch.setattr(phontrast, "_conda_rscripts", lambda: [])
    monkeypatch.setattr(toolenv, "resolve", lambda exe: None)
    toolenv.invalidate_caches()
    yield tmp_path
    toolenv.invalidate_caches()


def fake_rscript(path, r_version="4.4.1", package=None, version=None, lib="/home/x/R/lib"):
    """A shell stub that answers the probe the way Rscript would."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f'echo "R {r_version}"', f'echo "LIB {lib}"']
    if package:
        lines.append(f'echo "PKG {package} {version}"')
    path.write_text("#!/bin/sh\n" + "\n".join(lines) + "\n")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return path


# --------------------------------------------------------------------------- #
# The generated R driver
# --------------------------------------------------------------------------- #
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


# --------------------------------------------------------------------------- #
# Finding R and phontrast
# --------------------------------------------------------------------------- #
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
    # R found, package missing: the hint names the R that was checked.
    bare = phontrast.PhontrastStatus(rscript_path="/opt/R/bin/Rscript", r_version="4.4.1")
    assert "/opt/R/bin/Rscript" in bare.install_hint and "install.packages" in bare.install_hint
    assert phontrast.PhontrastStatus(rscript_path=None, probing=True).install_hint == "Looking for R…"


def test_rscript_in_accepts_the_program_or_a_folder(tmp_path):
    exe = fake_rscript(tmp_path / "R-4.4.1" / "bin" / "Rscript")
    assert phontrast.rscript_in(exe) == str(exe)
    assert phontrast.rscript_in(tmp_path / "R-4.4.1") == str(exe)  # an R home
    assert phontrast.rscript_in(tmp_path / "R-4.4.1" / "bin") == str(exe)  # its bin dir
    assert phontrast.rscript_in(tmp_path) is None
    assert phontrast.rscript_in(tmp_path / "nowhere") is None


def test_probe_reads_version_library_and_package(tmp_path):
    exe = fake_rscript(tmp_path / "Rscript", package="phontrast", version="2.4.1", lib="/home/x/R/lib")
    assert phontrast.probe_rscript(str(exe)) == {
        "path": str(exe), "r_version": "4.4.1", "home": None, "library": "/home/x/R/lib",
        "package": "phontrast", "version": "2.4.1",
    }
    assert phontrast.probe_rscript(str(fake_rscript(tmp_path / "bare" / "Rscript")))["package"] is None
    not_r = tmp_path / "not_r"
    not_r.write_text("#!/bin/sh\necho hello\n")
    not_r.chmod(not_r.stat().st_mode | stat.S_IEXEC)
    assert phontrast.probe_rscript(str(not_r)) is None
    assert phontrast.probe_rscript(str(tmp_path / "missing")) is None


def test_status_prefers_the_r_that_has_a_usable_phontrast(isolated, monkeypatch):
    bare = fake_rscript(isolated / "bare" / "Rscript")
    old = fake_rscript(isolated / "old" / "Rscript", r_version="4.2.0", package="phontrast", version="1.2.0")
    good = fake_rscript(isolated / "good" / "Rscript", package="phontrast", version="2.4.1")
    monkeypatch.setattr(phontrast, "_platform_rscripts", lambda: [bare, old, good])
    status = phontrast.phontrast_status(wait=True)
    assert status.available and status.rscript_path == str(good)
    assert status.r_version == "4.4.1" and status.library == "/home/x/R/lib"
    assert [c["path"] for c in status.candidates] == [str(bare), str(old), str(good)]
    assert status.selected is None
    assert [phontrast._supported(c) for c in status.candidates] == [False, False, True]


def test_two_launchers_of_one_installation_are_listed_once(isolated, monkeypatch, tmp_path):
    def launcher(name):
        p = isolated / name / "Rscript"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('#!/bin/sh\necho "R 4.4.1"\necho "HOME /opt/R/4.4.1/lib/R"\necho "LIB /x"\n')
        p.chmod(p.stat().st_mode | stat.S_IEXEC)
        return p

    a, b = launcher("usr_bin"), launcher("usr_lib_R_bin")
    monkeypatch.setattr(phontrast, "_platform_rscripts", lambda: [a, b])
    status = phontrast.phontrast_status(wait=True)
    assert [c["path"] for c in status.candidates] == [str(a)]
    assert status.candidates[0]["home"] == "/opt/R/4.4.1/lib/R"


def test_status_explains_an_r_without_phontrast(isolated, monkeypatch):
    bare = fake_rscript(isolated / "bare" / "Rscript")
    monkeypatch.setattr(phontrast, "_platform_rscripts", lambda: [bare])
    status = phontrast.phontrast_status(wait=True)
    assert not status.available and status.rscript_path == str(bare)
    assert str(bare) in status.install_hint and "Install phontrast" in status.install_hint
    cmd, reason = phontrast.install_plan(status.rscript_path)
    assert cmd[0] == str(bare) and 'install.packages("phontrast"' in cmd[-1] and reason == ""
    assert "R_LIBS_USER" in cmd[-1]  # no admin rights needed


def test_no_r_anywhere(isolated):
    status = phontrast.phontrast_status(wait=True)
    assert status.rscript_path is None and not status.available and not status.probing
    assert status.install_hint == phontrast.PHONTRAST_INSTALL_HINT
    cmd, reason = phontrast.install_plan(None)
    assert cmd is None and "cloud.r-project.org" in reason


def test_chosen_r_wins_and_is_validated(isolated, monkeypatch):
    other = fake_rscript(isolated / "other" / "Rscript", package="phontrast", version="2.4.1")
    chosen = fake_rscript(isolated / "chosen" / "R" / "bin" / "Rscript", r_version="4.5.0",
                          package="phontrast", version="2.4.1")
    monkeypatch.setattr(phontrast, "_platform_rscripts", lambda: [other])
    with pytest.raises(ValueError):
        phontrast.set_selected_rscript(str(isolated / "nowhere"))
    not_r = isolated / "not_r" / "Rscript"
    not_r.parent.mkdir()
    not_r.write_text("#!/bin/sh\necho nope\n")
    not_r.chmod(not_r.stat().st_mode | stat.S_IEXEC)
    with pytest.raises(ValueError):
        phontrast.set_selected_rscript(str(not_r))

    assert phontrast.set_selected_rscript(str(isolated / "chosen" / "R")) == str(chosen)  # a folder
    assert phontrast.selected_rscript() == str(chosen)
    status = phontrast.phontrast_status(wait=True)
    assert status.rscript_path == str(chosen) and status.selected == str(chosen)
    assert status.r_version == "4.5.0"
    assert [c["path"] for c in status.candidates] == [str(chosen), str(other)]

    assert phontrast.set_selected_rscript(None) is None
    assert phontrast.selected_rscript() is None
    assert phontrast.phontrast_status(wait=True).rscript_path == str(other)

    monkeypatch.setenv("VOWELCHEMY_RSCRIPT", str(chosen))
    assert phontrast.selected_rscript() == str(chosen)  # the env var wins


def test_run_phontrast_uses_the_r_it_found(isolated, monkeypatch, tmp_path):
    """The driver runs with the discovered Rscript, not a bare `Rscript` on PATH."""
    calls = []

    def fake_run(args, on_output=None, timeout=None):
        calls.append(list(args))
        return phontrast.CommandResult(list(args), 1, "", "stub")

    good = fake_rscript(isolated / "good" / "Rscript", package="phontrast", version="2.4.1")
    monkeypatch.setattr(phontrast, "_platform_rscripts", lambda: [good])
    monkeypatch.setattr(phontrast, "run_streaming", fake_run)
    df = pd.DataFrame({"vowel_canon": ["IY", "EH"], "F1_norm": [-1.0, 1.0], "F2_norm": [1.0, -1.0]})
    res = phontrast.run_phontrast(df, features=["F1_norm", "F2_norm"], work_dir=tmp_path / "w")
    assert calls and calls[0][0] == str(good)
    assert not res.ok and any("did not produce" in n for n in res.notes)


def test_run_phontrast_without_r(isolated, tmp_path):
    df = pd.DataFrame(
        {"vowel_canon": ["IY", "EH"], "F1_norm": [-1.0, 1.0], "F2_norm": [1.0, -1.0]}
    )
    res = phontrast.run_phontrast(
        df, features=["F1_norm", "F2_norm"], category_col="vowel_canon",
        work_dir=tmp_path / "w", rscript="definitely-not-rscript-xyz",
    )
    # It should write the R driver + input CSV regardless, and report gracefully.
    assert res.script_path.exists()
    assert res.input_csv.exists()
    assert not res.ok
    assert any("Rscript" in n for n in res.notes)
    assert phontrast.compare_overlap_metrics is phontrast.run_phontrast  # pre-0.3 name
