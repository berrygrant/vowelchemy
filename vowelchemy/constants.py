"""Canonical vowel identifiers and shared constants.

Different tools in the sociophonetics stack label vowels differently:

* **ARPABET / CMU** — what MFA's ``english_us_arpa`` dictionary and ``new-fave``
  emit, optionally carrying a lexical-stress digit: ``IY``, ``IY1``, ``EH0`` …
* **Wells lexical sets** — ``FLEECE``, ``DRESS`` … common in sociophonetic writing.
* **Pedagogical keywords** — ``BEET``, ``BET`` … handy when teaching.

Vowelchemy canonicalizes everything to *bare* ARPABET (no stress digit)
internally and offers the friendlier labels for the UI.  The user's example
"BET/BEET F1 by Age Group" maps to ``EH`` (DRESS) and ``IY`` (FLEECE).
"""

from __future__ import annotations

_STRESS_DIGITS = "012"

# bare ARPABET vowel -> (Wells lexical set keyword, pedagogical keyword)
ARPABET_VOWELS: dict[str, tuple[str, str]] = {
    "IY": ("FLEECE", "BEET"),
    "IH": ("KIT", "BIT"),
    "EY": ("FACE", "BAIT"),
    "EH": ("DRESS", "BET"),
    "AE": ("TRAP", "BAT"),
    "AA": ("LOT", "BOT"),
    "AO": ("THOUGHT", "BOUGHT"),
    "OW": ("GOAT", "BOAT"),
    "UH": ("FOOT", "PUT"),
    "UW": ("GOOSE", "BOOT"),
    "AH": ("STRUT", "BUT"),
    "ER": ("NURSE", "BIRD"),
    "AY": ("PRICE", "BITE"),
    "AW": ("MOUTH", "BOUT"),
    "OY": ("CHOICE", "BOY"),
    "AX": ("commA", "aboutA"),  # schwa (also spelled AH0)
}

# Reverse lookups (case-insensitive keys handled by the helpers below).
_KEYWORD_TO_ARPABET = {kw.upper(): arpa for arpa, (_, kw) in ARPABET_VOWELS.items()}
_LEXSET_TO_ARPABET = {ls.upper(): arpa for arpa, (ls, _) in ARPABET_VOWELS.items()}


def canonical_vowel(label: str) -> str:
    """Return bare, upper-cased ARPABET for a vowel label.

    Strips a trailing lexical-stress digit and surrounding whitespace, so
    ``"iy1"`` and ``" IY "`` both become ``"IY"``.  Non-ARPABET labels
    (e.g. FAVE/Plotnik codes) are upper-cased and returned unchanged so callers
    can still group by them.
    """
    if not isinstance(label, str):
        return label
    v = label.strip().upper()
    while v and v[-1] in _STRESS_DIGITS:
        v = v[:-1]
    return v


def resolve_vowel(name: str) -> str | None:
    """Resolve an ARPABET code, Wells lexical set, or keyword to bare ARPABET.

    Returns ``None`` if the name is not recognised.
    """
    if not isinstance(name, str):
        return None
    key = name.strip().upper()
    canon = canonical_vowel(key)
    if canon in ARPABET_VOWELS:
        return canon
    if key in _KEYWORD_TO_ARPABET:
        return _KEYWORD_TO_ARPABET[key]
    if key in _LEXSET_TO_ARPABET:
        return _LEXSET_TO_ARPABET[key]
    return None


def vowel_display_label(arpabet: str) -> str:
    """Human-friendly label for a vowel, e.g. ``"EH (DRESS / BET)"``."""
    canon = canonical_vowel(arpabet)
    meta = ARPABET_VOWELS.get(canon)
    if not meta:
        return arpabet
    lexset, keyword = meta
    return f"{canon} ({lexset} / {keyword})"


# File-type constants used by corpus discovery.
AUDIO_EXTENSIONS = {".wav"}
TRANSCRIPT_TEXT_EXTENSIONS = {".lab", ".txt"}
TEXTGRID_EXTENSIONS = {".textgrid"}  # compared against suffix.lower()

# Tier names (lower-cased) that indicate a *phone*-level alignment exists.
# MFA emits "words" + "phones"; FAVE alignments use "phone"; other aligners vary.
PHONE_TIER_NAMES = {"phones", "phone", "phon", "segment", "segments", "seg", "mau"}
WORD_TIER_NAMES = {"words", "word", "ort", "ortho", "orthography"}

# Default MFA English models (ARPABET). Users can override in the UI.
DEFAULT_ACOUSTIC_MODEL = "english_us_arpa"
DEFAULT_DICTIONARY = "english_us_arpa"

# Normalization method identifiers. Lobanov is the ANAE/Labov default.
NORMALIZATION_METHODS = (
    "lobanov",
    "labov_anae",
    "nearey",
    "nearey1",
    "bark",
    "watt_fabricius",
    "none",
)
DEFAULT_NORMALIZATION = "lobanov"
