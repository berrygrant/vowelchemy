import pandas as pd

from vowelchemy.constants import canonical_vowel, resolve_vowel, vowel_display_label
from vowelchemy.schema import ColumnSchema


def test_canonical_vowel_strips_stress():
    assert canonical_vowel("iy1") == "IY"
    assert canonical_vowel(" EH0 ") == "EH"
    assert canonical_vowel("AA") == "AA"
    assert canonical_vowel("plt_i") == "PLT_I"  # unknown codes pass through upper-cased


def test_resolve_vowel_by_keyword_lexset_arpabet():
    assert resolve_vowel("BEET") == "IY"
    assert resolve_vowel("fleece") == "IY"
    assert resolve_vowel("IY1") == "IY"
    assert resolve_vowel("BET") == "EH"
    assert resolve_vowel("nonsense") is None


def test_vowel_display_label():
    assert vowel_display_label("IY").startswith("IY")
    assert "FLEECE" in vowel_display_label("IY")


def test_schema_detects_common_aliases():
    df = pd.DataFrame(
        {"name": ["a"], "plt_vclass": ["IY1"], "F1_50": [300.0], "F2_50": [2300.0]}
    )
    schema = ColumnSchema.detect(df)
    assert schema.speaker == "name"
    assert schema.vowel == "plt_vclass"
    assert schema.f1 == "F1_50"
    assert schema.f2 == "F2_50"
    assert schema.is_valid


def test_schema_overrides_and_missing():
    df = pd.DataFrame({"spk": ["a"], "v": ["IY"], "x1": [1.0], "x2": [2.0]})
    schema = ColumnSchema.detect(df)
    assert not schema.is_valid  # f1/f2 not auto-detected
    schema = ColumnSchema.detect(df, {"speaker": "spk", "vowel": "v", "f1": "x1", "f2": "x2"})
    assert schema.is_valid
    assert schema.require("f1") == "x1"
