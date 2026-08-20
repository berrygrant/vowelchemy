# References

The methods and tools Vowelchemy builds on, with the canonical citation for
each. Cite these in any write-up that uses the corresponding feature — the
mapping table below says which reference goes with which part of the tool.
(Bibliographic details verified against publisher/Zenodo records; two entries
carry caveats, noted inline.)

## Normalization methods

- Fabricius, A. H., Watt, D., & Johnson, D. E. (2009). A comparison of three
  speaker-intrinsic vowel formant frequency normalization algorithms for
  sociophonetics. *Language Variation and Change, 21*(3), 413–435.
  https://doi.org/10.1017/S0954394509990160
- Labov, W., Ash, S., & Boberg, C. (2006). *The atlas of North American
  English: Phonetics, phonology and sound change*. Mouton de Gruyter.
  https://doi.org/10.1515/9783110167467
- Lobanov, B. M. (1971). Classification of Russian vowels spoken by different
  speakers. *The Journal of the Acoustical Society of America, 49*(2B),
  606–608. https://doi.org/10.1121/1.1912396
- Nearey, T. M. (1978). *Phonetic feature systems for vowels* [Doctoral
  dissertation, University of Alberta, 1977]. Indiana University Linguistics
  Club.
- Thomas, E. R., & Kendall, T. (2007). *NORM: The vowel normalization and
  plotting suite* [Online resource]. http://lingtools.uoregon.edu/norm/
- Traunmüller, H. (1990). Analytical expressions for the tonotopic sensory
  scale. *The Journal of the Acoustical Society of America, 88*(1), 97–100.
  https://doi.org/10.1121/1.399849
- Watt, D., & Fabricius, A. (2002). Evaluation of a technique for improving
  the mapping of multiple speakers' vowel spaces in the F1~F2 plane. *Leeds
  Working Papers in Linguistics and Phonetics, 9*, 159–173.

See also: Barreda, S. (2021). Perceptual validation of vowel normalization
methods for variationist research. *Language Variation and Change, 33*(1),
27–53 — on why the ANAE method is log-mean normalization, cited in
`normalization.py`.

## Separation / merger metrics

- Bhattacharyya, A. (1943). On a measure of divergence between two statistical
  populations defined by their probability distributions. *Bulletin of the
  Calcutta Mathematical Society, 35*, 99–109. *(pre-digital journal; no DOI)*
- Hay, J., Warren, P., & Drager, K. (2006). Factors influencing speech
  perception in the context of a merger-in-progress. *Journal of Phonetics,
  34*(4), 458–484. https://doi.org/10.1016/j.wocn.2005.10.001
- Johnson, D. E. (2015). *Quantifying overlap with Bhattacharyya's affinity*
  [Unpublished conference presentation]. New Ways of Analyzing Variation
  (NWAV) 44, Toronto, ON, Canada.
- Lin, J. (1991). Divergence measures based on the Shannon entropy. *IEEE
  Transactions on Information Theory, 37*(1), 145–151.
  https://doi.org/10.1109/18.61115
- Nycz, J., & Hall-Lew, L. (2013). Best practices in measuring vowel merger.
  *Proceedings of Meetings on Acoustics, 20*(1), 060008.
  https://doi.org/10.1121/1.4894063
- Pillai, K. C. S. (1955). Some new test criteria in multivariate analysis.
  *The Annals of Mathematical Statistics, 26*(1), 117–121.
  https://doi.org/10.1214/aoms/1177728599

## Tools / software

- Berry, G. M. (2026). *phontrast: Contrast and separation metrics for
  phonological categories* (Version 2.4.0) [Computer software].
  https://doi.org/10.5281/zenodo.21864533
  (repository: https://github.com/berrygrant/phontrast — formerly *phonJSD*)
- Fruehwald, J. (2024). *new-fave: Vowel formant extraction* [Computer
  software]. Zenodo. https://doi.org/10.5281/zenodo.14837885
  (repository: https://github.com/Forced-Alignment-and-Vowel-Extraction/new-fave)
- McAuliffe, M., Socolof, M., Mihuc, S., Wagner, M., & Sonderegger, M. (2017).
  Montreal Forced Aligner: Trainable text-speech alignment using Kaldi. In
  *Proceedings of Interspeech 2017* (pp. 498–502). ISCA.
  https://doi.org/10.21437/Interspeech.2017-1386
- Rosenfelder, I., Fruehwald, J., Brickhouse, C., Evanini, K., Seyfarth, S.,
  Gorman, K., Prichard, H., & Yuan, J. (2022). *FAVE (Forced Alignment and
  Vowel Extraction)* (Version 2.0.0) [Computer software]. Zenodo.
  https://doi.org/10.5281/zenodo.22281

## Descriptive framework

- Wells, J. C. (1982). *Accents of English* (Vols. 1–3). Cambridge University
  Press. *(lexical sets: Vol. 1)*

---

## What in Vowelchemy cites what

| Feature | Where | Cite |
|---|---|---|
| Lobanov z-score normalization (default) | `normalization.py` | Lobanov (1971); Thomas & Kendall (2007) |
| Labov ANAE log-mean scaling (Telsur G = 6.896874) | `normalization.py` | Labov, Ash & Boberg (2006); Barreda (2021) |
| Nearey shared / individual log-mean | `normalization.py` | Nearey (1978); Thomas & Kendall (2007) |
| Bark transform (26.81/(1 + 1960/f) − 0.53) | `normalization.py` | Traunmüller (1990) |
| Watt–Fabricius modified S-centroid | `normalization.py` | Watt & Fabricius (2002); Fabricius, Watt & Johnson (2009) |
| Jensen-Shannon Divergence (base-2, KDE) | `metrics.py` | Lin (1991) |
| Pillai trace + permutation test (merger work) | `metrics.py` | Pillai (1955); Hay, Warren & Drager (2006); Nycz & Hall-Lew (2013) |
| Bhattacharyya overlap coefficient | `metrics.py` | Bhattacharyya (1943); Johnson (2015) |
| Forced alignment | `alignment.py` | McAuliffe et al. (2017) |
| Formant extraction | `extraction.py` | Fruehwald (2024); Rosenfelder et al. (2022) as predecessor |
| Canonical separation engine (R) | `phontrast.py` | Berry (2026) |
| Lexical sets (FLEECE, LOT, THOUGHT…) & keywords | `constants.py` | Wells (1982) |

To cite **Vowelchemy itself**, use the repository's `CITATION.cff` (GitHub
renders a "Cite this repository" button from it).
