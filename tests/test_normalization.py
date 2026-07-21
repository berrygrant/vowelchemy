import numpy as np
import pandas as pd
import pytest

from vowelchemy import normalization as norm
from vowelchemy.normalization import ANAE_TELSUR_G, hz_to_bark
from vowelchemy.schema import ColumnSchema


@pytest.fixture
def frame():
    rng = np.random.RandomState(0)
    rows = []
    for spk, scale in [("A", 1.0), ("B", 1.2)]:
        for vowel, (t1, t2) in [("IY", (300, 2300)), ("AE", (750, 1750)), ("AA", (760, 1150))]:
            for _ in range(40):
                rows.append(
                    {
                        "speaker": spk,
                        "vowel": vowel,
                        "F1": (t1 * scale) * rng.normal(1, 0.05),
                        "F2": (t2 * scale) * rng.normal(1, 0.05),
                    }
                )
    return pd.DataFrame(rows)


@pytest.fixture
def schema(frame):
    return ColumnSchema.detect(frame)


def test_lobanov_zscore_per_speaker(frame, schema):
    res = norm.normalize(frame, schema, "lobanov")
    for spk in ("A", "B"):
        assert res.data[res.data.speaker == spk]["F1_norm"].mean() == pytest.approx(0, abs=1e-9)
        assert res.data[res.data.speaker == spk]["F1_norm"].std() == pytest.approx(1, abs=1e-9)


def test_none_is_identity(frame, schema):
    res = norm.normalize(frame, schema, "none")
    assert np.allclose(res.data["F1_norm"], frame["F1"])


def test_bark_known_value():
    # 26.81/(1 + 1960/500) - 0.53
    assert hz_to_bark(np.array([500.0]))[0] == pytest.approx(26.81 / (1 + 1960 / 500) - 0.53)


def test_labov_anae_uniform_scaling_preserves_ratio(frame, schema):
    res = norm.normalize(frame, schema, "labov_anae")
    # A uniform per-speaker scaling must preserve F1/F2 within each token.
    ratio_raw = frame["F1"] / frame["F2"]
    ratio_norm = res.data["F1_norm"] / res.data["F2_norm"]
    assert np.allclose(ratio_raw.values, ratio_norm.values)


def test_labov_anae_maps_speaker_logmean_to_G(frame, schema):
    res = norm.normalize(frame, schema, "labov_anae")
    # After scaling, each speaker's pooled log-mean of F1,F2 should equal G.
    for spk, sub in res.data.groupby("speaker"):
        pooled = np.concatenate([np.log(sub["F1_norm"]), np.log(sub["F2_norm"])])
        assert pooled.mean() == pytest.approx(ANAE_TELSUR_G, abs=1e-6)


def test_nearey_shared_zero_pooled_logmean(frame, schema):
    res = norm.normalize(frame, schema, "nearey")
    for spk, sub in res.data.groupby("speaker"):
        pooled = np.concatenate([sub["F1_norm"], sub["F2_norm"]])
        assert pooled.mean() == pytest.approx(0, abs=1e-9)


def test_nearey1_zero_per_formant(frame, schema):
    res = norm.normalize(frame, schema, "nearey1")
    for spk, sub in res.data.groupby("speaker"):
        assert sub["F1_norm"].mean() == pytest.approx(0, abs=1e-9)
        assert sub["F2_norm"].mean() == pytest.approx(0, abs=1e-9)


def test_watt_fabricius_centroid_math():
    df = pd.DataFrame(
        {
            "speaker": ["A"] * 4,
            "vowel": ["IY", "IY", "AE", "AE"],
            "F1": [300.0, 300.0, 700.0, 700.0],
            "F2": [2300.0, 2300.0, 1700.0, 1700.0],
        }
    )
    schema = ColumnSchema.detect(df)
    res = norm.normalize(df, schema, "watt_fabricius")
    # S(F1) = (2*F1[i] + F1[a]) / 3 = (600 + 700)/3 = 433.33
    # S(F2) = (F2[i] + F1[i]) / 2 = (2300 + 300)/2 = 1300
    s_f1 = (2 * 300 + 700) / 3
    s_f2 = (2300 + 300) / 2
    iy = res.data[res.data.vowel == "IY"].iloc[0]
    assert iy["F1_norm"] == pytest.approx(300 / s_f1)
    assert iy["F2_norm"] == pytest.approx(2300 / s_f2)


def test_unknown_method_raises(frame, schema):
    with pytest.raises(ValueError):
        norm.normalize(frame, schema, "banana")
