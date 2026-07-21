"""API tests for the FastAPI backend (replaces the old Streamlit app test)."""

import pytest
from fastapi.testclient import TestClient

from vowelchemy.api import app


@pytest.fixture
def client():
    return TestClient(app)


def H(session="test"):
    return {"X-Vowelchemy-Session": session}


def test_health_not_shadowed_by_static_mount(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_status_reports_tools_and_empty_data(client):
    body = client.get("/api/status", headers=H("s-status")).json()
    for tool in ("mfa", "newfave", "phonjsd"):
        assert isinstance(body["tools"][tool]["available"], bool)
    assert body["data"]["loaded"] is False


def test_demo_then_dataset_and_csv(client):
    h = H("s-demo")
    demo = client.post("/api/demo", headers=h).json()
    assert demo["n_tokens"] == 4500
    ds = client.post("/api/dataset", json={"selected_vowels": ["BEET", "BET"], "filters": {}}, headers=h).json()
    assert ds["n_total"] == 900  # 2 vowels x 18 speakers x 25 tokens
    csv = client.get("/api/dataset/csv", headers=h)
    assert csv.status_code == 200
    assert csv.headers["content-type"].startswith("text/csv")
    assert b"F1_norm" in csv.content


def test_normalization_switch(client):
    h = H("s-norm")
    client.post("/api/demo", headers=h)
    res = client.post("/api/normalization", json={"method": "labov_anae"}, headers=h).json()
    assert "Hz" in res["units"]
    bad = client.post("/api/normalization", json={"method": "nope"}, headers=h)
    assert bad.status_code == 400


def test_schema_get_and_override(client):
    h = H("s-schema")
    client.post("/api/demo", headers=h)
    sch = client.get("/api/schema", headers=h).json()
    assert sch["schema"]["speaker"] == "speaker"
    assert "F1" in sch["columns"]
    res = client.post("/api/schema", json={"overrides": {"f1": "F1"}}, headers=h).json()
    assert res["missing_required"] == []


def test_figures_return_plotly_json(client):
    h = H("s-fig")
    client.post("/api/demo", headers=h)
    cross = client.post(
        "/api/figure/cross",
        json={"formant": "F1_norm", "x": "Age Group", "split": "vowel_label", "kind": "violin", "vowels": ["IY", "EH"]},
        headers=h,
    ).json()
    assert "data" in cross and "layout" in cross and len(cross["data"]) >= 2
    space = client.post("/api/figure/vowel-space", json={"color": "vowel_canon"}, headers=h).json()
    assert len(space["data"]) > 0


def test_separation_builtin_captures_merger(client):
    h = H("s-sep")
    client.post("/api/demo", headers=h)
    res = client.post(
        "/api/separation",
        json={"vowels": ["AA", "AO"], "group_by": "Age Group", "engine": "builtin"},
        headers=h,
    ).json()
    recs = res["builtin"]["records"]
    by_group = {r["group_value"]: r["JSD"] for r in recs}
    assert by_group["Older"] > by_group["Young"]  # merger across apparent time
    assert res["figure_bar"] is not None


def test_separation_requires_data(client):
    r = client.post("/api/separation", json={"vowels": [], "engine": "builtin"}, headers=H("s-empty"))
    assert r.status_code == 400


def test_grouping_columns(client):
    h = H("s-group")
    client.post("/api/demo", headers=h)
    body = client.get("/api/grouping-columns", headers=h).json()
    assert "Age Group" in body["columns"] and "Sex" in body["columns"]
    assert "F1_norm" in body["norm_formants"]


def test_corpus_autodetect_and_browse(client, tmp_path):
    # A realistic multi-speaker layout: audio + transcripts in separate trees.
    for spk in ("s1", "s2"):
        (tmp_path / "audio" / spk).mkdir(parents=True)
        (tmp_path / "texts" / spk).mkdir(parents=True)
        (tmp_path / "audio" / spk / "r.wav").write_bytes(b"RIFF")
        (tmp_path / "texts" / spk / "r.lab").write_text("hi")

    det = client.post("/api/corpus/autodetect", json={"root_dir": str(tmp_path)}).json()
    assert det["audio_dir"].endswith("/audio")
    assert det["transcript_dir"].endswith("/texts")
    assert det["counts"]["wav"] == 2

    br = client.get("/api/browse", params={"path": str(tmp_path)}).json()
    dirs = {d["name"]: d for d in br["dirs"]}
    assert "audio" in dirs and "texts" in dirs
    assert dirs["audio"]["has_wav"] is True  # detected one level deep
    assert br["parent"] is not None

    bad = client.post("/api/corpus/autodetect", json={"root_dir": str(tmp_path / "nope")})
    assert bad.status_code == 400


def test_align_requires_corpus_and_jobs_404(client):
    assert client.post("/api/align", json={}, headers=H("s-noalign")).status_code == 400
    assert client.get("/api/jobs/unknown-id").status_code == 404
