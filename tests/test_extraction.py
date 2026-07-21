from pathlib import Path

import pandas as pd

from vowelchemy import extraction
from vowelchemy.corpus import discover_corpus


def test_build_command_corpus_mode():
    cmd = extraction._build_command(
        Path("/stage"), "fave-extract", "corpus",
        speakers_file=None, destination=None, exclude_overlaps=False, extra_args=None,
    )
    assert cmd == ["fave-extract", "corpus", "/stage"]


def test_build_command_with_options():
    cmd = extraction._build_command(
        Path("/stage"), "fave-extract", "subcorpora",
        speakers_file=Path("/spk.csv"), destination=Path("/out"),
        exclude_overlaps=True, extra_args=["--foo", "bar"],
    )
    assert cmd[:3] == ["fave-extract", "subcorpora", "/stage"]
    assert "--destination" in cmd and "/out" in cmd
    assert "--speakers" in cmd and "/spk.csv" in cmd
    assert "--exclude-overlaps" in cmd
    assert cmd[-2:] == ["--foo", "bar"]


def test_load_output_prefers_points(tmp_path):
    (tmp_path / "corpus_tracks.csv").write_text("a,b\n1,2\n")
    (tmp_path / "corpus_points.csv").write_text("speaker,vowel,F1,F2\ns,IY,300,2300\n")
    path, df = extraction._load_output(tmp_path)
    assert path.name == "corpus_points.csv"
    assert "F1" in df.columns


def test_load_existing_vowel_data(tmp_path):
    csv = tmp_path / "demo_points.csv"
    pd.DataFrame({"name": ["s"], "label": ["IY1"], "F1": [300.0], "F2": [2300.0]}).to_csv(
        csv, index=False
    )
    res = extraction.load_existing_vowel_data(csv)
    assert res.ok
    assert res.schema.speaker == "name" and res.schema.vowel == "label"


def test_stage_aligned_flat_vs_per_speaker(tmp_path):
    # build a tiny aligned corpus
    corpus = tmp_path / "corpus"
    (corpus / "spk1").mkdir(parents=True)
    (corpus / "spk1" / "r1.wav").write_bytes(b"RIFF")
    (corpus / "spk1" / "r1.TextGrid").write_text(
        'item [1]:\n class = "IntervalTier"\n name = "phones"\n'
    )
    inv = discover_corpus(corpus, aligned_dir=corpus)
    flat = tmp_path / "flat"
    n = extraction._stage_aligned(inv, flat, link=False, per_speaker=False)
    assert n == 1
    assert (flat / "r1.wav").exists() and (flat / "r1.TextGrid").exists()

    nested = tmp_path / "nested"
    extraction._stage_aligned(inv, nested, link=False, per_speaker=True)
    assert (nested / "spk1" / "r1.wav").exists()
    assert (nested / "spk1" / "r1.TextGrid").exists()
