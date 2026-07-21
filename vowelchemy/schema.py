"""Column-schema detection for extracted vowel data.

Students may bring vowel CSVs from ``new-fave``, legacy FAVE-extract, the NORM
suite, or a hand-rolled Praat script — each spells its columns differently.
Rather than hard-code one tool's names, every analysis function in vowelchemy
takes a :class:`ColumnSchema` that maps *logical* fields (speaker, vowel, F1…)
to the *actual* columns in a given dataframe.  :meth:`ColumnSchema.detect`
auto-discovers them from a set of known aliases; the UI lets the user override
any guess.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional

import pandas as pd

# Ordered alias lists (matched case-insensitively).  Earlier entries win.
# The formant aliases include new-fave / FAVE point-measurement spellings such
# as ``F1_50`` (the value at 50% of vowel duration).
_ALIASES: dict[str, list[str]] = {
    "speaker": [
        "speaker", "name", "talker", "spkr", "speaker_id", "subject",
        "file_speaker", "participant", "id_speaker",
    ],
    "vowel": [
        "vowel", "label", "plt_vclass", "vclass", "arpabet", "arpa",
        "phoneme", "phone_label", "ipa", "stress_vowel",
    ],
    "f1": ["f1", "f1_50", "f1hz", "f1_hz", "f1_mean", "first_formant", "f1_median"],
    "f2": ["f2", "f2_50", "f2hz", "f2_hz", "f2_mean", "second_formant", "f2_median"],
    "f3": ["f3", "f3_50", "f3hz", "f3_hz", "f3_mean", "third_formant", "f3_median"],
    "duration": ["duration", "dur", "vowel_duration", "dur_ms", "length"],
    "word": ["word", "word_label", "orthography", "ort", "token_word"],
    "stress": ["stress", "stress_level", "lexical_stress"],
    "preseg": ["pre_seg", "abs_pre_seg", "preceding", "prev_phone", "pre_segment",
               "previous_segment", "pre_word"],
    "folseg": ["fol_seg", "abs_fol_seg", "following", "next_phone", "fol_segment",
               "following_segment", "fol_word"],
    "time": ["prop_time", "rel_time", "norm_time", "time", "timepoint", "midpoint",
             "t_mid", "t", "frame"],
    "token_id": ["id", "token_id", "uid", "token", "token_num", "segment_id"],
}

# Logical fields that must be present for any quantitative analysis.
REQUIRED_FIELDS = ("speaker", "vowel", "f1", "f2")


@dataclass
class ColumnSchema:
    """Mapping from logical field names to real dataframe column names."""

    speaker: Optional[str] = None
    vowel: Optional[str] = None
    f1: Optional[str] = None
    f2: Optional[str] = None
    f3: Optional[str] = None
    duration: Optional[str] = None
    word: Optional[str] = None
    stress: Optional[str] = None
    preseg: Optional[str] = None
    folseg: Optional[str] = None
    time: Optional[str] = None
    token_id: Optional[str] = None

    @classmethod
    def detect(cls, df: pd.DataFrame, overrides: Optional[dict] = None) -> "ColumnSchema":
        """Guess the schema for ``df`` from known aliases, then apply overrides."""
        lower_to_actual: dict[str, str] = {}
        for col in df.columns:
            lower_to_actual.setdefault(str(col).strip().lower(), col)

        resolved: dict[str, Optional[str]] = {}
        for field_name, aliases in _ALIASES.items():
            resolved[field_name] = next(
                (lower_to_actual[a] for a in aliases if a in lower_to_actual), None
            )

        if overrides:
            for k, v in overrides.items():
                if k in resolved and v:
                    resolved[k] = v
        return cls(**resolved)

    # -- helpers ----------------------------------------------------------- #
    def missing_required(self) -> list[str]:
        return [f for f in REQUIRED_FIELDS if getattr(self, f) is None]

    @property
    def is_valid(self) -> bool:
        return not self.missing_required()

    def require(self, field_name: str) -> str:
        col = getattr(self, field_name, None)
        if col is None:
            raise KeyError(
                f"Required column for '{field_name}' was not found in the vowel data. "
                f"Set it explicitly (detected schema: {self.as_dict()})."
            )
        return col

    def formant_columns(self) -> list[str]:
        return [c for c in (self.f1, self.f2, self.f3) if c is not None]

    def as_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}
