"""Finding a folder dropped on the app, and the system folder dialog."""

import shutil
import sys

import pytest

from vowelchemy import corpus


def test_normalize_dropped_name_strips_alias_and_shortcut_suffixes():
    n = corpus.normalize_dropped_name
    assert n("PREP_V2 alias") == "PREP_V2"
    assert n("PREP_V2.alias") == "PREP_V2"
    assert n("Corpus.lnk") == "Corpus"
    assert n("Corpus - Shortcut") == "Corpus"
    assert n("  plain  ") == "plain"
    assert n("alias") == "alias"  # a folder actually called that


@pytest.fixture
def places(tmp_path):
    desk = tmp_path / "Desktop" / "PREP_V2"
    desk.mkdir(parents=True)
    (desk / "s01.wav").write_bytes(b"RIFF")
    (desk / "s01.lab").write_text("hi")
    (desk / "speakers.csv").write_text("speaker\ns01\n")
    old = tmp_path / "Documents" / "archive" / "PREP_V2"
    old.mkdir(parents=True)
    (old / "notes.txt").write_text("old copy")
    (tmp_path / "node_modules" / "PREP_V2").mkdir(parents=True)  # never a corpus
    (tmp_path / ".cache" / "PREP_V2").mkdir(parents=True)  # hidden
    return tmp_path, desk, old


def test_locate_prefers_the_folder_whose_contents_match(places):
    root, desk, old = places
    res = corpus.locate_folder("PREP_V2", entries=["s01.wav", "s01.lab", "speakers.csv"], roots=[root])
    assert [r["path"] for r in res] == [str(desk), str(old)]
    assert res[0]["score"] == 1.0 and res[0]["matched"] == 3 and res[0]["total"] == 3
    assert res[1]["score"] == 0.0
    # Without a listing both are plausible; the shallower one comes first.
    plain = corpus.locate_folder("PREP_V2", roots=[root])
    assert [r["path"] for r in plain] == [str(desk), str(old)]
    assert all(r["score"] == 0.5 for r in plain)
    # An alias drops with a suffix; the search is case-insensitive.
    assert {r["path"] for r in corpus.locate_folder("prep_v2 alias", roots=[root])} == {str(desk), str(old)}
    assert corpus.locate_folder("nothing-here", roots=[root]) == []
    assert corpus.locate_folder("   ", roots=[root]) == []


def test_locate_by_a_file_inside_the_corpus(places):
    root, desk, _ = places
    res = corpus.locate_folder("s01.wav", kind="file", roots=[root])
    assert len(res) == 1 and res[0]["path"] == str(desk) and res[0]["file"] == str(desk / "s01.wav")
    csv = corpus.locate_folder("speakers.csv", kind="file", roots=[root])
    assert csv[0]["file"] == str(desk / "speakers.csv")


def test_locate_respects_depth_root_and_confinement(tmp_path):
    deep = tmp_path / "a" / "b" / "c" / "d" / "e" / "f" / "PREP"
    deep.mkdir(parents=True)
    assert corpus.locate_folder("PREP", roots=[tmp_path], max_depth=3) == []
    assert corpus.locate_folder("PREP", roots=[tmp_path], max_depth=8)[0]["path"] == str(deep)
    # A confinement root replaces the usual places.
    assert corpus.default_search_roots(root=tmp_path / "a") == [tmp_path / "a"]
    assert corpus.locate_folder("PREP", root=tmp_path / "a", max_depth=8)[0]["path"] == str(deep)
    usual = corpus.default_search_roots()
    assert usual and all(p.is_dir() for p in usual)


def test_native_dialog_availability_and_commands(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    assert corpus.native_dialog_available() is False  # headless: no dialog possible

    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/zenity" if name == "zenity" else None)
    assert corpus.native_dialog_available() is True
    cmd = corpus._native_dialog_command("Pick", str(tmp_path), "dir")
    assert cmd[0] == "zenity" and "--directory" in cmd and f"--filename={tmp_path}/" in cmd
    assert "--directory" not in corpus._native_dialog_command("Pick", None, "file")

    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/osascript" if name == "osascript" else None)
    cmd = corpus._native_dialog_command('Pick "the" folder', str(tmp_path), "dir")
    assert cmd[0] == "osascript" and "choose folder" in cmd[2] and 'Pick \\"the\\" folder' in cmd[2]
    assert f'POSIX file "{tmp_path}"' in cmd[2] and cmd[-1] == "POSIX path of chosen"
    assert "choose file" in corpus._native_dialog_command("Pick", None, "file")[2]

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(shutil, "which", lambda name: r"C:\ps.exe" if name == "powershell" else None)
    cmd = corpus._native_dialog_command("It's here", r"C:\data", "dir")
    assert cmd[:3] == [r"C:\ps.exe", "-NoProfile", "-STA"]
    assert "FolderBrowserDialog" in cmd[-1] and "$d.Description = 'It''s here'" in cmd[-1]
    assert "OpenFileDialog" in corpus._native_dialog_command("Pick", None, "file")[-1]


def test_native_dialog_runs_the_command_and_reads_the_choice(monkeypatch, tmp_path):
    calls = []

    class Result:
        def __init__(self, out, code=0, err=""):
            self.stdout, self.returncode, self.stderr = out, code, err

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return outcomes.pop(0)

    outcomes = [Result(f"{tmp_path}/\n"), Result("", 1, "User canceled."), Result("", 2, "boom")]
    monkeypatch.setattr(corpus, "_native_dialog_command", lambda t, s, m: ["fake-dialog", t])
    monkeypatch.setattr(corpus.subprocess, "run", fake_run)
    assert corpus.native_folder_dialog("Pick", start=tmp_path) == str(tmp_path)  # trailing slash dropped
    assert corpus.native_folder_dialog("Pick") is None  # cancelled
    with pytest.raises(RuntimeError):
        corpus.native_folder_dialog("Pick")
    assert calls[0] == ["fake-dialog", "Pick"]
    monkeypatch.setattr(corpus, "_native_dialog_command", lambda t, s, m: None)
    with pytest.raises(RuntimeError):
        corpus.native_folder_dialog("Pick")
