"""Coverage tests for API routes not exercised by test_api.py.

Together with test_api.py, every route in vowelchemy.api is hit at least once
(align/extract via their no-corpus validation paths — running the real tools
is the smoke suite's job).
"""

import io

import pytest
from fastapi.testclient import TestClient

from vowelchemy.api import app
from vowelchemy.sample_data import make_demo_dataset


@pytest.fixture
def client():
    return TestClient(app)


def H(session):
    return {"X-Vowelchemy-Session": session}


def _demo_csvs(tmp_path):
    tokens, speakers = make_demo_dataset(n_per_cell=1, tokens_per_vowel=8)
    vp = tmp_path / "demo_vowels.csv"
    sp = tmp_path / "demo_speakers.csv"
    tokens.to_csv(vp, index=False)
    speakers.to_csv(sp, index=False)
    return vp, sp, tokens, speakers


def test_corpus_validate(client, tmp_path):
    ok = client.post("/api/corpus/validate", json={"path": str(tmp_path)}).json()
    assert ok["ok"] is True
    bad = client.post("/api/corpus/validate", json={"path": str(tmp_path / "nope")}).json()
    assert bad["ok"] is False and bad["message"]


def test_corpus_scan_and_speakers(client, tmp_path):
    (tmp_path / "s1").mkdir()
    (tmp_path / "s1" / "rec.wav").write_bytes(b"RIFF")
    (tmp_path / "s1" / "rec.lab").write_text("hello")
    _vp, sp, _t, _s = _demo_csvs(tmp_path)
    res = client.post(
        "/api/corpus/scan",
        json={"audio_dir": str(tmp_path), "speakers_path": str(sp)},
        headers=H("cov-scan"),
    ).json()
    assert res["summary"]["paired"] == 1
    assert res["summary"]["needs_alignment"] == 1
    # the demo vowel csv in the same tree is offered for direct loading
    assert any(p.endswith("demo_vowels.csv") for p in res["existing_vowel_csvs"])

    bad = client.post("/api/corpus/scan", json={"audio_dir": str(tmp_path / "nope")},
                      headers=H("cov-scan"))
    assert bad.status_code == 400


def test_voweldata_load_path_and_errors(client, tmp_path):
    vp, _sp, tokens, _s = _demo_csvs(tmp_path)
    res = client.post("/api/voweldata/load", json={"csv_path": str(vp)}, headers=H("cov-load")).json()
    assert res["n_tokens"] == len(tokens)
    bad = client.post("/api/voweldata/load", json={"csv_path": str(tmp_path / "missing.csv")},
                      headers=H("cov-load"))
    assert bad.status_code == 400  # friendly error, not a 500


def test_voweldata_and_demographics_upload_tsv(client, tmp_path):
    vp, sp, tokens, speakers = _demo_csvs(tmp_path)
    # re-serialize as TSV to prove delimiter sniffing on uploads
    tsv = tokens.to_csv(sep="\t", index=False).encode()
    res = client.post("/api/voweldata/upload", files={"file": ("vowels.tsv", io.BytesIO(tsv), "text/tab-separated-values")},
                      headers=H("cov-up")).json()
    assert res["n_tokens"] == len(tokens)
    assert res["schema"]["f1"] == "F1"  # columns split correctly, not one mega-column

    dtsv = speakers.to_csv(sep="\t", index=False).encode()
    dres = client.post("/api/demographics/upload", files={"file": ("spk.tsv", io.BytesIO(dtsv), "text/tab-separated-values")},
                       headers=H("cov-up")).json()
    assert dres["n_speakers"] == len(speakers)
    assert "Age Group" in dres["columns"]


def test_extract_requires_corpus(client):
    assert client.post("/api/extract", json={}, headers=H("cov-noext")).status_code == 400


def test_normalization_methods_listing(client):
    methods = client.get("/api/normalization/methods").json()
    keys = {m["key"] for m in methods}
    assert {"lobanov", "labov_anae", "nearey", "bark", "watt_fabricius", "none"} <= keys


def test_figure_ridgeline(client):
    h = H("cov-ridge")
    client.post("/api/demo", headers=h)
    fig = client.post("/api/figure/ridgeline",
                      json={"value": "F1_norm", "group": "Age Group"}, headers=h).json()
    assert len(fig["data"]) >= 3  # one density per age group


def test_separation_csv_download(client):
    h = H("cov-sepcsv")
    client.post("/api/demo", headers=h)
    client.post("/api/dataset", json={"selected_vowels": ["AA", "AO"]}, headers=h)
    res = client.get("/api/separation/csv", headers=h)
    assert res.status_code == 200
    assert b"JSD" in res.content


def test_vowelmap_upload(client):
    h = H("cov-map")
    client.post("/api/demo", headers=h)
    mapping = b"code,label\nIY,i\xcb\x90 (FLEECE)\nEH,\xc9\x9b (DRESS)\n"
    res = client.post("/api/vowelmap/upload",
                      files={"file": ("map.csv", io.BytesIO(mapping), "text/csv")},
                      headers=h).json()
    assert res["n"] == 2
    vowels = client.get("/api/vowels", headers=h).json()
    assert any(v["vowel"] == "IY" for v in vowels)


def test_projects_endpoints(client, tmp_path, monkeypatch):
    monkeypatch.setenv("VOWELCHEMY_PROJECTS_DIR", str(tmp_path))
    h = H("cov-proj")
    client.post("/api/demo", headers=h)
    saved = client.post("/api/projects/save", json={"name": "cov study"}, headers=h).json()
    assert any(p["name"] == "cov_study" for p in saved["projects"])
    listed = client.get("/api/projects").json()
    assert any(p["name"] == "cov_study" for p in listed["projects"])
    loaded = client.post("/api/projects/load", json={"name": "cov study"}, headers=H("cov-proj2")).json()
    assert loaded["n_tokens"] > 0
    missing = client.post("/api/projects/load", json={"name": "nope"}, headers=h)
    assert missing.status_code == 404


def test_tracks_load_and_vowels(client, tmp_path):
    from vowelchemy.sample_data import make_demo_tracks

    tracks, _speakers = make_demo_tracks(n_per_cell=1)
    tp = tmp_path / "tracks.csv"
    tracks.to_csv(tp, index=False)
    h = H("cov-tracks")
    res = client.post("/api/tracks/load", json={"csv_path": str(tp)}, headers=h).json()
    assert res["n_tokens"] > 0
    vowels = client.get("/api/tracks/vowels", headers=h).json()
    assert any(v["vowel"] == "AY" and v["keyword"] == "BITE" for v in vowels)
    # a non-tracks CSV is rejected with a helpful 400
    vp, _sp, _t, _s = _demo_csvs(tmp_path)
    bad = client.post("/api/tracks/load", json={"csv_path": str(vp)}, headers=h)
    assert bad.status_code == 400


def test_tools_overview_and_environment_selection(client, tmp_path, monkeypatch):
    import stat

    monkeypatch.setenv("VOWELCHEMY_HOME", str(tmp_path / "state"))
    monkeypatch.delenv("VOWELCHEMY_TOOL_ENV", raising=False)

    overview = client.get("/api/tools").json()
    assert overview["selected"] is None
    # MFA is never offered as a pip install; new-fave may be, depending on Python.
    assert overview["install"]["mfa"]["possible"] is False
    assert "conda" in overview["install"]["mfa"]["reason"].lower()
    assert overview["app"]["version"]

    # a folder with neither tool is refused with a helpful message
    bad = client.post("/api/tools/environment", json={"path": str(tmp_path)})
    assert bad.status_code == 400 and "doesn't contain" in bad.json()["detail"]

    env = tmp_path / "aligner"
    (env / "bin").mkdir(parents=True)
    exe = env / "bin" / "mfa"
    exe.write_text("#!/bin/sh\necho 'mfa 3.4.2'\n")
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)

    chosen = client.post("/api/tools/environment", json={"path": str(env)}).json()
    assert chosen["selected"] == str(env)
    assert chosen["tools"]["mfa"]["available"] is True
    # the choice shows up in the status the sidebar polls
    assert client.get("/api/status").json()["tool_env"] == str(env)

    # Regression: every tools response must carry the environment list. When the
    # POST omitted it, the UI blanked its list and selecting looked like a no-op.
    assert "environments" in chosen
    assert any(e["path"] == str(env) for e in chosen["environments"])

    cleared = client.post("/api/tools/environment", json={"path": None}).json()
    assert cleared["selected"] is None
    assert "environments" in cleared


def test_install_can_target_the_selected_environment_when_the_app_cannot(
    client, tmp_path, monkeypatch
):
    """The packaged app can't pip into itself, so it offers the chosen env instead."""
    import stat
    import sys

    monkeypatch.setenv("VOWELCHEMY_HOME", str(tmp_path / "state"))
    monkeypatch.delenv("VOWELCHEMY_TOOL_ENV", raising=False)
    env = tmp_path / "extract"
    (env / "bin").mkdir(parents=True)
    py = env / "bin" / "python3"
    py.write_text('#!/bin/sh\ncase "$*" in *version_info*) echo "3 12";; esac\nexit 0\n')
    py.chmod(py.stat().st_mode | stat.S_IEXEC)
    exe = env / "bin" / "fave-extract"
    exe.write_text("#!/bin/sh\necho 1.3.0\n")
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)

    client.post("/api/tools/environment", json={"path": str(env)})
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    body = client.get("/api/tools").json()
    assert body["install"]["newfave"]["possible"] is True
    assert body["install"]["newfave"]["target"] == "env"
    assert body["install"]["newfave"]["env_name"] == "extract"


def test_tools_environments_listing(client, tmp_path, monkeypatch):
    monkeypatch.setenv("VOWELCHEMY_HOME", str(tmp_path / "state"))
    body = client.get("/api/tools/environments").json()
    assert isinstance(body["environments"], list)
    assert "tools" in body and "install" in body


def test_install_endpoint_refuses_mfa(client):
    res = client.post("/api/tools/install", json={"tool": "mfa"})
    assert res.status_code == 400
    assert "pip" in res.json()["detail"].lower()


def test_glossary_includes_references(client):
    body = client.get("/api/glossary").json()
    assert len(body["terms"]) > 5
    assert any("Lobanov" in r["work"] for r in body["references"])
