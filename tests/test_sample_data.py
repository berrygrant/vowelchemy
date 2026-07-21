from vowelchemy import sample_data
from vowelchemy.schema import ColumnSchema


def test_demo_dataset_shapes_and_determinism():
    t1, s1 = sample_data.make_demo_dataset()
    t2, s2 = sample_data.make_demo_dataset()
    assert t1.equals(t2)  # deterministic
    assert len(s1) == 18  # 2 sexes x 3 age groups x 3 speakers
    assert set(s1["Age Group"]) == {"Older", "Middle", "Young"}
    schema = ColumnSchema.detect(t1)
    assert schema.is_valid


def test_demo_writer(tmp_path):
    paths = sample_data.write_demo_dataset(tmp_path)
    assert paths["vowels"].exists() and paths["speakers"].exists()


def test_sex_scales_formants():
    tokens, speakers = sample_data.make_demo_dataset()
    merged = tokens.merge(speakers, on="speaker")
    iy = merged[merged.vowel == "IY1"]
    # female speakers have higher formants on average
    assert iy[iy.Sex == "F"]["F1"].mean() > iy[iy.Sex == "M"]["F1"].mean()
