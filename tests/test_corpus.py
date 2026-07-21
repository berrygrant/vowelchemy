
from vowelchemy.corpus import (
    discover_corpus,
    is_aligned_textgrid,
    sniff_textgrid_tiers,
    validate_location,
)

LONG_ALIGNED = """File type = "ooTextFile"
Object class = "TextGrid"
xmin = 0
xmax = 1
tiers? <exists>
size = 2
item []:
    item [1]:
        class = "IntervalTier"
        name = "words"
        xmin = 0
        xmax = 1
    item [2]:
        class = "IntervalTier"
        name = "phones"
        xmin = 0
        xmax = 1
"""

LONG_WORDS_ONLY = """File type = "ooTextFile"
Object class = "TextGrid"
item []:
    item [1]:
        class = "IntervalTier"
        name = "words"
"""

SHORT_ALIGNED = '''File type = "ooTextFile"
Object class = "TextGrid"
0
1
<exists>
2
"IntervalTier"
"words"
0
1
0
"IntervalTier"
"phones"
0
1
0
'''


def test_sniff_and_alignment_detection(tmp_path):
    aligned = tmp_path / "a.TextGrid"
    aligned.write_text(LONG_ALIGNED)
    assert set(t.lower() for t in sniff_textgrid_tiers(aligned)) == {"words", "phones"}
    assert is_aligned_textgrid(aligned)

    words = tmp_path / "b.TextGrid"
    words.write_text(LONG_WORDS_ONLY)
    assert not is_aligned_textgrid(words)

    short = tmp_path / "c.TextGrid"
    short.write_text(SHORT_ALIGNED)
    assert is_aligned_textgrid(short)


def test_validate_location(tmp_path):
    ok = validate_location(tmp_path)
    assert ok.ok
    missing = validate_location(tmp_path / "nope")
    assert not missing.ok and not missing.exists


def test_discover_same_folder(tmp_path):
    (tmp_path / "s1.wav").write_bytes(b"RIFF")
    (tmp_path / "s1.lab").write_text("hello world")
    (tmp_path / "s2.wav").write_bytes(b"RIFF")  # unpaired audio
    inv = discover_corpus(tmp_path)
    assert inv.summary()["recordings"] == 2
    assert len(inv.paired) == 1
    assert len(inv.audio_without_transcript) == 1
    assert inv.needs_alignment  # paired but no phone tier


def test_discover_separate_folders_and_speakers(tmp_path):
    audio = tmp_path / "audio"
    texts = tmp_path / "texts"
    audio.mkdir()
    texts.mkdir()
    # per-speaker sub-folders
    (audio / "spk1").mkdir()
    (texts / "spk1").mkdir()
    (audio / "spk1" / "rec.wav").write_bytes(b"RIFF")
    (texts / "spk1" / "rec.lab").write_text("word")
    inv = discover_corpus(audio, transcript_dir=texts)
    assert len(inv.paired) == 1
    assert inv.paired[0].speaker == "spk1"
