# Your first vowel study: Vowelchemy + the PREP corpus

*A guide for undergraduate researchers in the LUV Lab.*

This tutorial walks you from "I've never analyzed speech data" to a defensible,
citable analysis of a real research question in the **PREP corpus** (Puerto
Rican English in Philadelphia; Berry, 2022) using Vowelchemy. It has two parts:

- **Part A — Warm-up (~20 min, no corpus access needed).** You practice the
  whole pipeline on Vowelchemy's built-in demo dataset, so the concepts and
  buttons are familiar before you touch real, IRB-protected recordings.
- **Part B — The real thing (~2–4 hours the first time).** You analyze the
  COT/CAUGHT vowel pair in PREP V2, from research question to a figure, a
  separation metric with a confidence interval, and a methods paragraph.

Blocks marked **`[LAB — confirm]`** are details this document cannot pin down
(paths move, versions change, and some facts are documented only inside the
lab). Ask your supervisor for those; everything else you can do on your own.

> **Prerequisites.** One phonetics or intro-linguistics course (you know what
> F1/F2 are, roughly). No programming, no statistics beyond "what's a mean."

---

## 0 · Before you touch the data: ethics first

PREP is not a practice dataset. It is **60–90-minute sociolinguistic
interviews with real members of Philadelphia's Puerto Rican community**,
collected in 2017 under informed consent; lab access to and use of the corpus
is governed by **Villanova IRB protocol FY2021-192**. The recordings are a
contribution from a community whose information must remain protected. Before
you access anything:

1. **Complete CITI human-subjects training** (~2 hours) — the lab requires it
   before any contact with corpus material.
2. **Work in place.** The corpus lives on the lab NAS and is accessed from the
   campus network with your NAS credentials. Raw audio, transcripts, and the
   speaker-metadata file **never leave the NAS** — no copies to your laptop,
   Google Drive, or email. Derived, de-identified tables are what move — and
   only after checking what they contain (see B.7).
3. **Aggregate, don't identify.** Report speaker-level information only in
   aggregate (counts, means by group). Never put an individual speaker's
   demographics next to their speaker code in anything that leaves the lab.
4. **Expect the anonymization hums.** The distributed audio is anonymized:
   spans where a speaker said a name, address, or other identifier are
   low-pass filtered at 500 Hz, so you'll hear a muffled hum there. That's by
   design — the words are unintelligible but the timing and prosody are
   preserved. Don't try to reconstruct what was said.
5. **Ask before sharing anything publicly** (a class presentation outside the
   lab, a poster, social media). What may be said publicly about the data is
   governed by the consent forms. **`[LAB — confirm]:** current
   consent-to-share status before any external presentation.*

---

## Part A — Warm-up on the demo dataset

No corpus, no aligner, no R needed — just the app.

### A.1 Install and launch

Open a terminal (Terminal on macOS; PowerShell on Windows) and type these
lines one at a time, pressing Enter after each. You need Python 3 and git
installed — if a line answers `command not found`, install them from
python.org and git-scm.com, or ask a labmate.

```bash
git clone https://github.com/berrygrant/vowelchemy
cd vowelchemy
pip install .
vowelchemy app     # serves the app at http://127.0.0.1:8000 — open that URL in your browser
```

`vowelchemy app` doesn't open a browser window itself; success looks like the
terminal printing a running-server message and the page loading when you
visit **http://127.0.0.1:8000** yourself.

The left sidebar shows the six pipeline stages (**1 Corpus → 2 Align →
3 Extract → 4 Dataset → 5 Visualize → 6 Separation**) and a **Tools** panel
with status dots for MFA, new-fave, and phontrast. For the warm-up you don't
need any of those tools — the dots can stay grey.

### A.2 Load the demo and look at a distribution

Click **✨ Load demo dataset** in the sidebar. You land on **4 · Dataset**
with a synthetic 18-speaker corpus already normalized (Lobanov). Skim the
panels: a column mapping, a **Normalization method** selector, vowel
checkboxes, and demographic filters.

Go to **5 · Visualize → Cross (distribution)**. Set:

- **Formant**: `F1_norm`
- **X axis (group)**: `Age Group`
- **Split / colour**: `vowel_label`
- **Style**: `violin`
- **Vowels**: make sure only the `BEET` and `BET` chips are selected (they
  usually already are — chips toggle on and off when clicked)

You're looking at *BET/BEET F1 by Age Group*: two clearly separate violins in
every age group, raw tokens jittered on top. This is the house style —
**always look at the distribution, not just a mean**. Two groups can have the
same mean and completely different shapes.

> Vowel pickers throughout the app are labeled by teaching keyword (`BEET`,
> `BET`, `BOT`, `BOUGHT`, …). Results tables spell out the full identity —
> e.g. `AA (LOT / BOT)` means ARPABET `AA` = the Wells lexical set LOT = the
> keyword BOT. Same vowel, three naming traditions.

### A.3 Measure separation, don't just eyeball it

Go to **6 · Separation**. Under **Vowels to compare**, click the `BOT` and
`BOUGHT` chips (that's LOT and THOUGHT — the *cot* and *caught* vowels). Set
**Compute within each level of** to `Age Group`, leave **Space** at `F1 × F2`,
tick **bootstrap JSD confidence intervals** (off by default because it's
slower), and click **Compute separation**.

The table reports **JSD** (Jensen–Shannon Divergence): 1 = fully separated
vowels, 0 = indistinguishable (merged). The demo corpus has a deliberately
planted *age-graded merger*, so:

> **Check yourself.** Your JSD values should be approximately (±0.05):
> **Older ≈ 0.96** · **Middle ≈ 0.67** · **Young ≈ 0.10**, with verdicts
> going from "strongly separated" to "very high overlap (likely merged)".
> If you see that gradient, you've just measured a merger in apparent time —
> the core move of Part B. Don't see it? You've most likely picked the wrong
> vowel chips or the wrong grouping column — re-check those before anything
> else.

Also note the **Pillai** column (a regression-based separation measure — the
one most sociophonetics papers report) and the CI columns you enabled. Two
metrics agreeing is much stronger evidence than one.

### A.4 Two habits to take with you

- Click **Glossary & help** (sidebar) whenever a term is unfamiliar. The
  **Key readings** section at the bottom lists the paper behind each method.
- In the **Session** panel you can download a **recipe** — a JSON file
  recording every analysis choice you made. Save one at the end of every real
  session; it is the honest answer to "what exactly did you run?"

---

## Part B — A real study: COT/CAUGHT in PREP V2

### B.1 What is the PREP corpus?

**PREP — Puerto Rican English in Philadelphia** (Berry, 2022,
doi:10.17605/OSF.IO/7KM4R) — is a corpus of sociolinguistic interviews and
word-list recordings with English-dominant Puerto Rican residents of North
and Northeast Philadelphia, recorded in 2017 during NSF-funded fieldwork
(BCS-1651061) for Berry's (2018) dissertation. The anonymized release used in
current lab work (the folder named `PREP_Corpus_V2_032723`) is cited in lab
manuscripts as *"PREP, version 2; Berry 2022"*, and underlies published and
in-progress studies of TH-stopping (Patchell & Berry, 2024, *Language
Variation and Change*), EY-raising, and CAUGHT-lowering. Analyses in lab
papers typically use **38 speakers (27 women, 11 men), born 1954–1998**; each
speaker contributes roughly 10–12 minutes of transcribed conversational
speech (~4,000 words), and most also completed a word-reading task.

The corpus folder contains:

| Item | What it is | What you'll use it for |
|---|---|---|
| `Anonymized_Audio/` | One WAV per speaker interview (anonymization hums included) | Input to alignment & formant extraction |
| `Anonymized_TextGrids/` | One Praat TextGrid per recording — a TextGrid is a time-aligned annotation file whose *tiers* hold labeled *intervals*; here a single tier named for the speaker holds utterance-sized intervals of verbatim transcript | The transcripts for forced alignment |
| `MFA_Aligned_TextGrids/` | A *shipped* forced alignment (word + phone tiers) | ⚠️ **Do not use — see B.4** |
| `Elicited_Speech/` | Per-speaker folders (`S1`, `S2`, …) of word-list WAVs, one per trial | The read-speech style (advanced; skip on a first pass) |
| `prep_socio.csv` | One row per speaker: speaker ID, Sex, birth year, … | Stage 4's **Speaker demographics CSV** |

> **`[LAB — confirm]:** where `PREP_Corpus_V2_032723` is mounted on the lab
> NAS after the 2026 campus move (ask your supervisor — access details are on
> the lab Info Sheet, not in any repository), plus the full column list of
> `prep_socio.csv` and the audio sample rate.*

Two data quirks to know before you start:

- **Some `Elicited_Speech` folders carry QC flags in their names.** Skip
  flagged folders unless your supervisor says otherwise.
- **`prep_socio.csv` has more rows than any published sample.** Different
  papers use different subsets (the dissertation used 37 speakers, the 2024
  LVC paper 32, current vowel work 38 or 41). This is normal — exclusion
  criteria differ — but it means *you* must count and report the N you
  actually analyzed, not a number copied from a paper.

### B.2 From curiosity to a research question

A research question needs four decisions: **which vowels, which speakers,
which measure, and what would count as evidence.** Here is the worked
example this tutorial follows.

**Background.** In Philadelphia English, the vowel of *caught/thought*
(THOUGHT, ARPABET `AO`) was traditionally raised — one of the dialect's
most recognizable (and stigmatized) features. Recent work reports younger
White Philadelphians *lowering* it (Labov, Rosenfelder & Fruehwald, 2013) —
crucially, while keeping it distinct from the vowel of *cot/lot* (LOT,
ARPABET `AA`): White Philadelphia has not merged the two. Nationally, by
contrast, many dialects have merged them completely (the "low-back merger").
So for Puerto Rican Philadelphians the question is live:

> **Question.** Are LOT and THOUGHT more overlapped for younger PREP
> speakers than for older ones?
>
> **Hypothesis (H1).** Separation (JSD, Pillai) is lower in the younger group
> than the older group — apparent-time movement toward merger.
> **Null (H0).** Separation is comparable across age groups.
>
> **Evidence.** A JSD difference between age groups whose bootstrap
> confidence intervals don't substantially overlap, in the same direction as
> the Pillai difference, visible in the vowel-space plot — not just a point
> estimate.

*Apparent time* means using speakers' birth years as a window onto change:
if 60-year-olds separate two vowels and 25-year-olds don't, the change
plausibly happened in between. The lab's convention for PREP splits speakers
at **born ≤ 1985 (Older) vs. born after 1985 (Younger)**. If `prep_socio.csv`
has a birth-year column but no ready-made age-group column, make one before
you start — in a **copy saved alongside the original on the NAS** (e.g.
`prep_socio_agegroups.csv`; the metadata file must not be copied off the NAS —
rule 2) — and point Stage 4's **Speaker demographics CSV** at your copy.
Vowelchemy groups by whatever columns the demographics file has.

### B.3 Set up the tools

Part B needs two external tools, and the easiest reliable setup is to put
*everything* — MFA, new-fave, and Vowelchemy — in one conda environment.
(conda is a program that manages tool installations; if you don't have it,
install Miniconda from docs.conda.io first.)

```bash
# 1. Create an environment with the Montreal Forced Aligner in it
conda create -n aligner -c conda-forge montreal-forced-aligner
conda activate aligner
mfa model download acoustic english_us_arpa
mfa model download dictionary english_us_arpa

# 2. In that SAME environment, install new-fave and Vowelchemy
pip install new-fave
cd vowelchemy        # the folder you cloned in A.1
pip install .

# 3. Test, then launch
mfa version
fave-extract --version
vowelchemy app
```

If both test commands print a version number, the sidebar's **MFA** and
**new-fave** dots will be green when the app loads. If a dot is grey, you
almost certainly launched `vowelchemy app` from outside the `aligner`
environment — run `conda activate aligner` and relaunch.
**`[LAB — confirm]:** the MFA version installed on the lab machines, and
whether `english_us_arpa` remains the lab-standard model + dictionary pair.*

### B.4 Stage 1 · Corpus — point at the data, and dodge the trap

In **1 · Corpus**, paste the corpus root (the `PREP_Corpus_V2_032723`
folder) into **Auto-detect from a root folder** and click **Auto-detect
layout**. Vowelchemy will propose sub-folders for audio, transcripts, and
alignments; you can adjust each with the folder picker. Then **Scan corpus**
to see the pairing table: every recording, whether it has a transcript, and
whether it's already aligned.

Here is the trap: the scan will report that recordings are **already
aligned**, because `MFA_Aligned_TextGrids/` ships with the corpus. **That
shipped alignment is known to be bad.** Lab QC found its word tiers far too
sparse — well under 10 words per minute, against the ~120–180 of natural
conversation — and truncated partway through every interview: a prior
alignment run silently failed. Re-aligning from scratch recovered roughly an
order of magnitude more usable COT/CAUGHT tokens.

> **Check yourself — always audit an inherited alignment.** Use Praat (the
> standard free phonetics program — download it from praat.org): **Open →
> Read from file…**, select one TextGrid from `MFA_Aligned_TextGrids/` and
> its matching WAV, select both objects, and click **View & Edit** — then
> listen to the first minute and compare what you hear against the word tier.
> Better, compute words per minute: select the TextGrid object and use
> **Query ▸ Query interval tier ▸ Get number of intervals…** (choose the word
> tier's number), then divide by the recording's duration in minutes. Under
> ~100 words/min for conversation = something is wrong. This one check is the
> difference between a few hundred usable tokens and several thousand.

So for this study, set the **aligned** folder to a fresh, empty output
location (not `MFA_Aligned_TextGrids/`), point transcripts at
`Anonymized_TextGrids/`, and move to Stage 2. **Create that output folder on
the NAS, next to the corpus folder** — aligned TextGrids contain the
transcript text, so rule 2 applies to them too.
**`[LAB — confirm]:** whether the shipped alignment has since been replaced
with a QC'd one — if so, you can skip Stage 2 entirely.*

Since Part B creates several folders and files, here is the bookkeeping in
one place:

| Stage | What it writes | Where to create it | May it leave the NAS? |
|---|---|---|---|
| 2 · Align | aligned TextGrids | on the NAS, next to the corpus | **No** — they contain the transcript text |
| 3 · Extract | measurements CSV (+ a staging folder) | on the NAS | Derived table — ask your supervisor before moving it |
| 4 · Dataset | the downloaded analysis CSV | your analysis folder | **Only after dropping raw demographic columns** (see B.7) |

### B.5 Stage 2 · Align — MFA, and the transcript-cleanup caveat

One more real-world wrinkle: the PREP transcript TextGrids embed **ELAN
transcription conventions** in their labels — punctuation plus symbols such
as `=` and `!` (their exact semantics are documented inconsistently across
lab sources; ask if it matters for your analysis). Fed to MFA raw, that
markup inflates out-of-vocabulary words and degrades the alignment. The lab
has a preprocessing script that strips markup (removing
``. , ! ? ; : " ( ) [ ] =`` from labels) while preserving interval timing.
**`[LAB — confirm]:** get the current transcript-cleanup script and run it
(or confirm a pre-cleaned transcript folder exists) before aligning.*

Then, in **2 · Align**:

- **Acoustic model** / **Dictionary**: `english_us_arpa` (pre-filled).
- Check **Download the acoustic model + dictionary first** on your first run.
- **Output folder for TextGrids**: the fresh NAS folder from B.4.
- Click **Run alignment**.

Alignment runs as a background job with a live progress bar (phase +
percent). A full corpus can take a long while — the job keeps running even
if you close the tab, and the page reattaches to it when you come back.
When it finishes, re-run **Scan corpus** in Stage 1: recordings should now
pair with your new TextGrids — and repeat the B.4 Praat audit on one of
*your own* output files (words + phones tiers, sensible boundaries,
full-length coverage).

> **If it fails.** The stage streams MFA's log right in the page — read the
> last lines. The two most common causes: (1) skipped transcript cleanup, so
> MFA drowns in out-of-vocabulary "words" (go back to the cleanup step);
> (2) the tool wasn't found or died immediately — you launched the app
> outside the `aligner` environment (see B.3). If you can't diagnose it,
> copy the log to your supervisor rather than re-running blindly.

### B.6 Stage 3 · Extract — measure formants with new-fave

In **3 · Extract**, set **Aligned TextGrid folder** to your Stage-2 output
and pick an **Output folder for measurements** (on the NAS), then click
**Extract vowels** (in the "Run extraction" card — again a background job
with progress). Vowelchemy stages each WAV next to its aligned TextGrid and
runs new-fave's `fave-extract`, then loads the resulting `*_points.csv` —
one row per vowel token, with raw-Hz formants.

One methodological flag: the lab's extraction notes record that new-fave's
default formant-ceiling search, run with male and female speakers pooled,
converged on physiologically implausible ceilings for many female tokens in
this corpus — which, per those notes, distorted exactly the F1/F2
comparisons this study depends on. Lab practice is therefore to extract with
**sex-conditioned settings** (roughly 3,500–6,000 Hz ceilings for male,
4,500–7,500 Hz for female speakers). The app's Extract stage can't pass
custom `fave-extract` flags — that requires the Python library
(`vowelchemy.extraction.extract_vowels(..., extra_args=[...])`) or, more
likely, lab-provided pre-extracted CSVs.
**`[LAB — confirm]:** the current sex-conditioned extraction configs, or
whether pre-extracted vowel CSVs for PREP already exist.* If they do, Stage 3
accepts them directly — paste the path into **Vowel CSV on the server** —
and the Stage-1 scan lists any it finds.

> **If it fails.** Read the streamed log in the page. An empty or tiny
> measurements CSV usually means alignment failed upstream — redo the B.4
> audit *on your own Stage-2 output* before touching Stage 4. A crash at
> startup usually means the wrong environment (B.3).

### B.7 Stage 4 · Dataset — normalize, join demographics, select, filter

Now the acoustics meet the social data. In **4 · Dataset**:

1. **Column mapping** — auto-detected from the CSV; glance at it (speaker,
   vowel, F1, F2 should all be filled) and correct anything odd.
2. **Speaker demographics CSV** — point at your `prep_socio_agegroups.csv`
   copy from B.2. It joins on the speaker ID, and its columns (Sex, your Age
   Group column, …) become grouping options everywhere downstream.
3. **Normalization method** — keep **Lobanov** (the default; the lab's
   pipeline uses a Lobanov-based method — the ANAE/Plotnik rescaled variant,
   which differs only by a fixed rescaling). Normalization removes
   physiological differences in vocal-tract size so that speakers —
   crucially, men and women — are comparable in one plot. Because raw Hz are
   kept, switching methods later re-normalizes instantly; try it once to see
   how the plots change.
4. **Vowels to keep** — click the **BOT** and **BOUGHT** chips (= LOT and
   THOUGHT; tables downstream label them `AA (LOT / BOT)` and
   `AO (THOUGHT / BOUGHT)`). Note this selection shapes the Stage-4 preview
   and download; the Visualize and Separation stages have their own
   per-stage vowel chips.
5. **Outlier removal** — on, threshold **2.5 SD** (tokens far from their
   speaker×vowel mean are usually measurement errors). Note the N before and
   after; you will report both.
6. **Filter by columns** — one exclusion matters a lot for this pair:
   **pre-/r/ tokens**. Words like *car* and *north* don't bear on
   COT/CAUGHT — /r/ drags F1/F2 around, and pre-/r/ `AO` belongs to the
   separate NORTH–FORCE pattern. If a following-segment column is offered,
   add it under **Filter by columns** and **de-select** the `R` value in its
   keep-chips (filters keep what's selected). If the column isn't offered —
   columns with more than ~30 distinct values aren't — do this exclusion on
   the CSV outside the app, or ask your supervisor. (Also ask whether the
   lab currently excludes pre-/l/ tokens like *doll/fall* — practices
   differ.) One filter you may expect is **token duration** (the lab uses a
   50–500 ms window: shorter is unreliable, longer is usually a hesitation
   or alignment glitch) — Vowelchemy has no numeric-range filter, so that
   window is applied when preparing the token CSV, not here.
   **`[LAB — confirm]:** how the lab currently applies the duration window
   and the pre-/r/ exclusion when preparing PREP token CSVs.*
7. **Download CSV** — save the tidy dataset to your analysis folder. **Note:
   because step 2 joined the demographics, this file carries each speaker's
   demographic columns next to their speaker code on every row.** Treat it
   under the same rules as the metadata file itself — it stays on lab
   systems. If you need a portable copy, drop the raw demographic columns
   first (keep only the derived Age Group) and ask your supervisor.

> **Check yourself.** After filtering, your combined LOT+THOUGHT token count
> (shown with the preview) should be **in the thousands** for the full
> corpus. A few hundred almost always means a truncated alignment — go back
> to the B.4 audit and run it on *your* Stage-2 output.

### B.8 Stage 5 · Visualize — look before you measure

Three views, in order:

1. **Vowel space** (F2×F1, ellipses + centroids): first click the **BOT**
   and **BOUGHT** chips in this tab's own **Vowels** picker (each Visualize
   tab selects its own vowels — Stage-4 selection doesn't carry over), and
   set **Colour by** to vowel. Two clouds with 2-SD ellipses — do they
   overlap at all?
2. **Cross (distribution)**: **Formant** `F1_norm`, **X axis** `Age Group`,
   **Split / colour** `vowel_label`, **Style** `violin`, **Vowels** BOT and
   BOUGHT. For CAUGHT-lowering you expect THOUGHT's F1 to rise toward LOT's
   (higher F1 = lower vowel) in younger speakers. Then switch **Formant** to
   `F2_norm` — mergers happen in two dimensions, and F2 often carries as
   much of the story.
3. **Ridgeline**: `F1_norm` by `Age Group` — is the younger distribution
   shifted, or bimodal (some speakers merged, some not)? The Ridgeline tab
   has no vowel picker of its own and pools every vowel in the dataset, so
   to see THOUGHT alone: back in **4 · Dataset**, add `vowel_label` under
   **Filter by columns** and keep only `AO (THOUGHT / BOUGHT)` — that filter
   *does* carry into Stage 5 — then return here. **Remove the filter
   afterwards**, or Stage 6 will have nothing to compare.

Every figure exports via **Download PNG** / **Download SVG (vector)** — use
SVG for posters. If a figure surprises you, hover single tokens in the plot:
an outlier with an absurd F1 is usually a mismeasurement, not a discovery.

### B.9 Stage 6 · Separation — put a number on it

In **6 · Separation**: under **Vowels to compare**, click **BOT** and
**BOUGHT**; **Compute within each level of** `Age Group`; **Space**
`F1 × F2`; **Engine** — phontrast if the sidebar dot is green (the lab's
canonical R package), otherwise the built-in engine (methodologically
aligned; fine for coursework). Tick **both** checkboxes — **bootstrap JSD
confidence intervals** and **Pillai permutation p-value** (they're off by
default because they're slower, but Part B's evidence standard needs them) —
then click **Compute separation**.

Read the table like this:

- **JSD** with its bootstrap CI — the headline separation number per group.
- **Pillai** with its permutation p — the field-standard corroborator
  (Hay, Warren & Drager, 2006; Nycz & Hall-Lew, 2013).
- The **verdict** line translates JSD: ≥ 0.85 strongly separated · ≥ 0.60
  moderately separated · ≥ 0.35 substantial overlap (possibly merging) ·
  below that, very high overlap (likely merged).
- **N per cell.** Treat any cell under ~20 tokens per vowel as unstable —
  the CI will be wide and you should say so, not hide it.

> **What to report (all of it, every time):** the metric *and* its CI; both
> Ns per group; the normalization method; the space (F1×F2 vs. F1-only);
> the exclusion rules (outlier SD, duration window, pre-/r/); and the number
> of speakers per group. Never claim a merger from a point estimate alone.

**Download CSV** saves the full metrics table for your write-up.

### B.10 Interpret — including the ways you might be wrong

Suppose you find Older JSD ≈ 0.8 [0.7, 0.9] and Younger ≈ 0.4 [0.3, 0.5].
That supports H1 — but a results section is only as good as its limitations
paragraph. For this design, the honest caveats are:

- **Apparent time is an inference, not a time machine.** Older speakers'
  speech may itself have changed over their lifetimes (age-grading).
- **Cells are unbalanced.** PREP has far more women than men, and the male
  speakers cluster in certain birth years; a pooled age effect can smuggle
  in a sex effect. At minimum, look at the cross plot split by Sex; better,
  compute separation within Sex × Age subsets and report both.
- **Style matters.** This analysis used conversational speech. Philadelphia's
  CAUGHT is socially marked, so read speech (the `Elicited_Speech/` word
  lists) may pattern differently — a known, interesting complication in this
  community, and a natural follow-up study.
- **Two metrics, one conclusion.** If JSD and Pillai disagree, investigate
  (usually a sample-size or outlier issue) before believing either.
- **Distribution shape.** A low JSD from a *bimodal* younger group means
  "some younger speakers merge," not "younger speakers merge" — the
  ridgeline view from B.8 is your check.

### B.11 Write it up

A defensible methods paragraph, with every choice you made in this tutorial
(fill in your own Ns):

> Conversational tokens of LOT (`AA`) and THOUGHT (`AO`) were drawn from the
> Puerto Rican English in Philadelphia corpus, version 2 (PREP; Berry, 2022):
> N speakers (n women, n men), born 1954–1998, recorded in sociolinguistic
> interviews in 2017 (Berry, 2018; Patchell & Berry, 2024). Recordings were
> force-aligned with the Montreal Forced Aligner (McAuliffe et al., 2017)
> using the `english_us_arpa` model and dictionary, and formants were
> measured with new-fave (Fruehwald, 2024). Tokens shorter than 50 ms or
> longer than 500 ms were excluded when preparing the token table, along
> with pre-rhotic tokens and tokens beyond 2.5 SD of their speaker×vowel
> mean (n = … excluded), leaving N = … tokens. Formants were Lobanov (1971)
> normalized. Category separation in F1×F2 space was quantified per age
> group with Jensen–Shannon Divergence (Lin, 1991) with bootstrap 95% CIs
> and Pillai scores (Pillai, 1955; Nycz & Hall-Lew, 2013), computed with
> phontrast (Berry, 2026) via Vowelchemy.

Full citations for every *method* live in
[`docs/REFERENCES.md`](REFERENCES.md) (with a feature → citation map), and
the in-app **Glossary → Key readings** lists the same works; the
corpus-specific references are in this tutorial's own reference list below.
Cite Vowelchemy itself via the repository's `CITATION.cff`. Finish by
downloading a **recipe** from the Session panel and saving it alongside your
CSV and figures — your supervisor will ask.

---

## Where to go next

- **Unguided exercise — EY-raising.** PREP's FACE vowel (`EY`) is *changing*
  without *merging* — it raises and fronts in closed syllables, led by
  women. Repeat the pipeline, but this time separation metrics are the wrong
  instrument (nothing is merging with anything). Which stage-5 view shows a
  shift in apparent time? What do you report instead of JSD? This teaches the
  most important lesson in the tutorial: **the question picks the tool.**
- **Style comparison.** Add `Elicited_Speech/` read tokens and compare
  conversational vs. read CAUGHT — stigmatized variables are exactly where
  style effects live.
- **Read three things:** Labov, Rosenfelder & Fruehwald (2013) for the
  Philadelphia backdrop; Nycz & Hall-Lew (2013) for how mergers are measured
  defensibly; Patchell & Berry (2024) for what a finished PREP study looks
  like.

## References

The corpus and community works cited above, in APA format. (Method
references — Lobanov, Lin, Pillai, Nycz & Hall-Lew, Hay et al., McAuliffe
et al., Fruehwald, Berry's phontrast — live in
[`docs/REFERENCES.md`](REFERENCES.md).)

- Berry, G. M. (2018). *Liminal voices, central constraints: Minority
  adoption of majority sound change* [Doctoral dissertation, The
  Pennsylvania State University].
  https://etda.libraries.psu.edu/catalog/15193gmb223
- Berry, G. M. (2022). *Language variation and change in Puerto Rican
  Philadelphia*. OSF. https://doi.org/10.17605/OSF.IO/7KM4R
- Labov, W., Rosenfelder, I., & Fruehwald, J. (2013). One hundred years of
  sound change in Philadelphia: Linear incrementation, reversal, and
  reanalysis. *Language*, 89(1), 30–65. https://doi.org/10.1353/lan.2013.0015
- Patchell, A. E., & Berry, G. M. (2024). TH-stopping in Philadelphia Puerto
  Rican English. *Language Variation and Change*, 36(1), 73–93.
  https://doi.org/10.1017/S0954394524000012

## Appendix — every `[LAB — confirm]` in one place

| # | Item to confirm with your supervisor |
|---|---|
| 1 | Where `PREP_Corpus_V2_032723` is mounted on the lab NAS (post-2026-move) and the credentials process (lab Info Sheet) |
| 2 | Consent-to-share status: what may be presented outside the lab |
| 3 | Column inventory of `prep_socio.csv`; whether an age-group column exists or you derive it (1985 cutoff); where derived working copies may be saved, and whether students have write access there |
| 4 | Whether the shipped `MFA_Aligned_TextGrids/` has been replaced with a QC'd alignment |
| 5 | The transcript-cleanup (ELAN-markup-stripping) script, or a pre-cleaned transcript folder |
| 6 | Installed MFA version; `english_us_arpa` still the standard model + dictionary |
| 7 | Sex-conditioned `fave-extract` configs (formant ceilings), or pre-extracted vowel CSVs to use instead |
| 8 | How the duration window (50–500 ms) and pre-/r/ exclusion are currently applied when preparing token CSVs; current pre-/l/ practice |
| 9 | Audio sample rate / technical specs, if you need them for a write-up |
