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
    {"term": "JSD (Jensen–Shannon divergence)",
     "definition": "How distinguishable two vowels' distributions are in formant space: "
                   "0 = indistinguishable (merged), 1 = no overlap at all. Estimated the "
                   "way phontrast does it (a Monte-Carlo plug-in on kernel densities with "
                   "a partial leave-one-out correction). Finite samples never reach "
                   "exactly 0: below ~25 tokens per vowel the floor sits noticeably above "
                   "0, so read small values against N. Kernel estimates also move with "
                   "the bandwidth — jsd_bw_half / jsd_bw_double in the CSV show the same "
                   "JSD at half and double bandwidth; trust orderings that survive that "
                   "bracket. No balance correction exists for JSD (only for Pillai)."},
    {"term": "Jensen–Shannon distance (√JSD, js_distance)",
     "definition": "The square root of JSD. Unlike JSD it is a true distance metric "
                   "(it obeys the triangle inequality), which makes it the better number "
                   "for comparing or averaging across pairs and groups. Report both."},
    {"term": "Pillai score",
     "definition": "The Pillai–Bartlett trace from a MANOVA of the formants on vowel "
                   "identity: 0 = complete overlap → 1 = fully separated. pillai_p_value "
                   "is the MANOVA F-test; the optional pillai_perm_p shuffles vowel "
                   "labels instead. Pillai needs many tokens to settle — two merged "
                   "vowels still score well above 0 in small samples."},
    {"term": "Pillai, balanced-design equivalent (pillai_eq)",
     "definition": "Raw Pillai depends on how unevenly the tokens split between the two "
                   "vowels (30 LOT vs 120 THOUGHT scores lower than 75 vs 75 for the same "
                   "separation). pillai_eq is the score the same underlying separation "
                   "would give in a balanced design, via the Lachenbruch–Mickey unbiased "
                   "squared Mahalanobis distance and Becker's correction. It is blank "
                   "(pillai_eq_fallback = True) when the corrected separation comes out "
                   "negative — which happens near merger — so a blank there is itself "
                   "informative. It runs slightly low in small, unbalanced, near-merged "
                   "samples (the map is concave). In the bootstrap, replicates that hit "
                   "the fallback count as 0 rather than being dropped, so the interval "
                   "isn't conditioned on the correction succeeding; "
                   "pillai_eq_fallback_rate says how many did."},
    {"term": "Pillai null threshold (pillai_null_p95)",
     "definition": "Stanley & Sneller's (2023) sample-size guide: the 95th-percentile "
                   "Pillai two *merged* vowels would produce with this many tokens "
                   "(e ÷ mean tokens per vowel). A Pillai at or below it is consistent "
                   "with merger at this N. It is a guide, not a hypothesis test, and it "
                   "runs a few percent low."},
    {"term": "Bhattacharyya distance / affinity",
     "definition": "Distance between two fitted Gaussians (bhatt_dist: 0 = identical) and "
                   "its affinity exp(−distance) (bhatt_affinity: 1 = identical, 0 = "
                   "disjoint — the mirror image of JSD)."},
    {"term": "Overlap (percent_overlap)",
     "definition": "The overlapping coefficient ∫ min(p, q): the proportion (0–1) of "
                   "probability mass the two vowel distributions share."},
    {"term": "Mahalanobis distance",
     "definition": "Distance between the two vowel means in units of the pooled "
                   "within-vowel spread. Unbounded; larger = more separated."},
    {"term": "Density: KDE vs Gaussian (mvnorm)",
     "definition": "JSD and overlap need a density for each vowel. KDE (default) smooths "
                   "the tokens with a Gaussian kernel and assumes no shape; mvnorm fits "
                   "one Gaussian per vowel — the assumption Pillai, Bhattacharyya and "
                   "Mahalanobis already make — and estimates the metrics between the "
                   "fitted Gaussians."},
    {"term": "Verdict (provisional)",
     "definition": "The one-line reading of JSD in the results table (≥ 0.85 strongly "
                   "separated · ≥ 0.60 moderately · ≥ 0.35 substantial overlap · below "
                   "that, likely merged) is a Vowelchemy house heuristic to help you "
                   "orient. There is no published cutoff for JSD; report the numbers, "
                   "their CIs and the Ns."},
    {"term": "Lexical set / keyword",
     "definition": "Standard names for vowel classes (FLEECE, DRESS…) or teaching "
                   "keywords (BEET, BET…). BEET = FLEECE = the ARPABET code IY."},
    {"term": "Trajectory / VISC",
     "definition": "How a vowel's formants move over its duration. Diphthongs (PRICE, "
                   "MOUTH) move a lot; monophthongs stay roughly put."},
    {"term": "Confidence interval (CI)",
     "definition": "A range the true value is likely to fall in. Vowelchemy bootstraps "
                   "like phontrast: it resamples tokens from the pooled pair, recomputes "
                   "every metric, and reports percentile intervals as "
                   "<metric>_ci_lower / _ci_upper."},
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
    {"work": "Endres & Schindelin (2003); Fuglede & Topsøe (2004)",
     "why": "Why √JSD (the Jensen-Shannon distance) is a proper metric."},
    {"work": "Berry (2026a), Estimand or estimator? (PsyArXiv preprint)",
     "why": "Vowel overlap measures against a known ground truth; report JSD and √JSD."},
    {"work": "Pillai (1955); Nycz & Hall-Lew (2013); Hay, Warren & Drager (2006)",
     "why": "The Pillai score and how vowel mergers are measured in practice."},
    {"work": "Stanley & Sneller (2023), JASA 153",
     "why": "Pillai and sample size; the e/m null threshold (pillai_null_p95)."},
    {"work": "Berry (2026b), Beyond the null (PsyArXiv preprint)",
     "why": "Calibration and class balance: the proportion-standardized Pillai (pillai_eq)."},
    {"work": "Becker (1986); Lachenbruch & Mickey (1968)",
     "why": "The unequal-n correction and unbiased separation estimate behind pillai_eq."},
    {"work": "Kelley & Tucker (2020), JASA 147",
     "why": "A head-to-head comparison of four vowel overlap measures."},
    {"work": "Bhattacharyya (1943); Johnson (2015, NWAV 44)",
     "why": "The Bhattacharyya distance/affinity for vowel categories."},
    {"work": "McAuliffe et al. (2017), Interspeech", "why": "The Montreal Forced Aligner."},
    {"work": "Fruehwald (2024), new-fave; Rosenfelder et al. (2022), FAVE",
     "why": "Formant extraction (and its predecessor)."},
    {"work": "Berry (2026), phontrast 2.4.1",
     "why": "The R package whose estimators the built-in engine ports (and the "
            "canonical engine when R is installed)."},
    {"work": "Wells (1982), Accents of English", "why": "The lexical sets (FLEECE, LOT…)."},
]


def jsd_verdict(jsd: Optional[float]) -> str:
    """One-line plain-language reading of a JSD value.

    The cut-offs are a Vowelchemy house heuristic for orientation — no
    published interpretation thresholds exist for JSD (Berry, 2026a) — and
    the in-app glossary says so.  Report the estimate, its CI and the Ns.
    """
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
