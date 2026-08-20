"""Plain-language help content and metric interpretation for the UI.

Serves the student-facing glossary (U2) and the one-line verdict shown under
the separation table (U4).
"""

from __future__ import annotations

from typing import Optional

GLOSSARY: list[dict] = [
    {"term": "Force alignment",
     "definition": "Automatically lining up a transcript with the audio so we know "
                   "the start/end time of every word and speech sound (phone)."},
    {"term": "Phone tier",
     "definition": "A layer in a TextGrid marking individual speech sounds. Its "
                   "presence is how Vowelchemy knows a recording is already aligned."},
    {"term": "Formant (F1, F2, F3)",
     "definition": "Resonant frequencies of the vocal tract. F1 tracks vowel height "
                   "(low F1 = high vowel), F2 tracks front/back (high F2 = front)."},
    {"term": "Normalization",
     "definition": "Removing anatomy-driven differences between speakers so their "
                   "vowels can be compared on one scale."},
    {"term": "Lobanov",
     "definition": "The default: turns each speaker's formants into z-scores "
                   "(how many SDs from that speaker's mean). The ANAE standard."},
    {"term": "Labov ANAE",
     "definition": "A single per-speaker scaling factor that rescales the whole vowel "
                   "space to a shared grand mean; returns interpretable Hz-like values."},
    {"term": "Nearey",
     "definition": "Log-mean centering — subtract a speaker's average log-formant. "
                   "‘Shared’ uses one value for all formants; ‘individual’ is per-formant."},
    {"term": "Bark",
     "definition": "A psychoacoustic frequency scale that better matches how the ear "
                   "spaces pitches (not a speaker normalization)."},
    {"term": "Watt–Fabricius",
     "definition": "Divides each formant by a per-speaker centroid built from corner "
                   "vowels (FLEECE and TRAP). Needs those vowels present."},
    {"term": "JSD (Jensen-Shannon Divergence)",
     "definition": "How distinguishable two vowels are in formant space. 1 = fully "
                   "separated, 0 = indistinguishable (merged)."},
    {"term": "Pillai score",
     "definition": "A MANOVA-based overlap measure (0 = complete overlap → 1 = fully "
                   "separated). A low permutation p-value means the separation is "
                   "unlikely to be chance."},
    {"term": "Bhattacharyya overlap",
     "definition": "Overlap of two fitted Gaussians: 1 = identical, 0 = disjoint — the "
                   "mirror image of JSD."},
    {"term": "Lexical set / keyword",
     "definition": "Standard names for vowel classes (FLEECE, DRESS…) or teaching "
                   "keywords (BEET, BET…). BEET = FLEECE = the ARPABET code IY."},
    {"term": "Trajectory / VISC",
     "definition": "How a vowel's formants move over its duration. Diphthongs (PRICE, "
                   "MOUTH) move a lot; monophthongs stay roughly put."},
    {"term": "Confidence interval (CI)",
     "definition": "A range the true value is likely to fall in. Vowelchemy bootstraps "
                   "JSD by resampling tokens to show how stable the estimate is."},
    {"term": "Outlier",
     "definition": "A token whose formants sit far (e.g. > 2.5 SD) from its own "
                   "speaker×vowel average — often a tracking error worth excluding."},
]


# Key readings behind the tool, shown in the in-app glossary drawer.
# Full APA entries + feature mapping live in docs/REFERENCES.md.
REFERENCES: list[dict] = [
    {"work": "Lobanov (1971), JASA 49", "why": "The z-score normalization (the default)."},
    {"work": "Labov, Ash & Boberg (2006), The Atlas of North American English",
     "why": "The ANAE log-mean scaling method and the Telsur G constant."},
    {"work": "Nearey (1978), Phonetic feature systems for vowels",
     "why": "Log-mean normalization (shared and per-formant variants)."},
    {"work": "Watt & Fabricius (2002); Fabricius, Watt & Johnson (2009)",
     "why": "The modified S-centroid normalization."},
    {"work": "Traunmüller (1990), JASA 88", "why": "The Hz→Bark formula."},
    {"work": "Thomas & Kendall (2007), NORM suite",
     "why": "The normalization-method family this tool mirrors."},
    {"work": "Lin (1991), IEEE Trans. Inf. Theory 37",
     "why": "Jensen-Shannon Divergence — the separation metric."},
    {"work": "Pillai (1955); Nycz & Hall-Lew (2013); Hay, Warren & Drager (2006)",
     "why": "The Pillai score and how vowel mergers are measured in practice."},
    {"work": "Bhattacharyya (1943); Johnson (2015, NWAV 44)",
     "why": "The Bhattacharyya overlap coefficient for vowel categories."},
    {"work": "McAuliffe et al. (2017), Interspeech", "why": "The Montreal Forced Aligner."},
    {"work": "Fruehwald (2024), new-fave; Rosenfelder et al. (2022), FAVE",
     "why": "Formant extraction (and its predecessor)."},
    {"work": "Berry (2026), phontrast", "why": "The canonical R separation engine."},
    {"work": "Wells (1982), Accents of English", "why": "The lexical sets (FLEECE, LOT…)."},
]


def jsd_verdict(jsd: Optional[float]) -> str:
    """One-line plain-language reading of a JSD value."""
    if jsd is None:
        return ""
    try:
        v = float(jsd)
    except (TypeError, ValueError):
        return ""
    if v != v:  # NaN
        return ""
    if v >= 0.85:
        return "strongly separated (clearly distinct vowels)"
    if v >= 0.60:
        return "moderately separated"
    if v >= 0.35:
        return "substantial overlap (possibly merging)"
    return "very high overlap (likely merged)"
