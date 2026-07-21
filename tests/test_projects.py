import pandas as pd

from vowelchemy import projects


def test_project_save_list_load(tmp_path, monkeypatch):
    monkeypatch.setenv("VOWELCHEMY_PROJECTS_DIR", str(tmp_path))
    recipe = {"version": 1, "normalization": {"method": "lobanov"}, "selected_vowels": ["IY"]}
    vowels = pd.DataFrame({"speaker": ["a"], "vowel": ["IY1"], "F1": [300.0], "F2": [2300.0]})

    projects.save_project("My Study 1", recipe, vowel_df=vowels)
    listed = projects.list_projects()
    assert any(p["name"] == "My_Study_1" and p["has_vowels"] for p in listed)

    loaded = projects.load_project("My Study 1")
    assert loaded["recipe"]["selected_vowels"] == ["IY"]
    assert loaded["vowel_df"] is not None and len(loaded["vowel_df"]) == 1
    assert loaded["tracks_df"] is None


def test_load_missing_project_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("VOWELCHEMY_PROJECTS_DIR", str(tmp_path))
    try:
        projects.load_project("nope")
        assert False, "expected FileNotFoundError"
    except FileNotFoundError:
        pass
