# Vowelchemy — Quality-of-Life Audit & Improvement Plan

This audit walks the app end-to-end from two perspectives — an **undergraduate
student** using it for a class assignment, and a **researcher** (grad student /
PI) using it for publishable work — then turns the findings into a prioritized
plan. It is grounded in the current codebase (`vowelchemy/*.py`, `frontend/src/*`).

Priority: **P0** = blocks or badly frustrates basic use · **P1** = important ·
**P2** = polish. Effort: **S** ≈ hours · **M** ≈ a day · **L** ≈ multi-day.

---

## Shipped in this PR

- ✅ **Points overlaid on violins** (`visualization.formant_cross`, `pointpos=0`).
- ✅ **Root-folder auto-detect** — give one root, we fuzzy-match the audio /
  transcript / aligned sub-folders (`corpus.suggest_corpus_layout`,
  `POST /api/corpus/autodetect`).
- ✅ **Click-to-select directory picker** — a server-side folder browser
  (`corpus.list_directory`, `GET /api/browse`, `FolderPicker`/`PathInput`).
- ✅ **Live progress bars** for MFA/new-fave — background jobs with phase +
  percent parsed from tool output (`jobs.py`, `POST /api/align|extract` →
  `GET /api/jobs/{id}`, `ProgressBar`/`useJob`).

---

## 👩‍🎓 Undergraduate student

> *Goal: follow a lab handout, get a vowel plot and a merger number, hand it in.
> Limited comfort with the command line, normalization theory, or statistics.*

| # | Finding | Priority | Effort |
|---|---------|----------|--------|
| U1 | **Install is three steps across two ecosystems** (`pip install`, `npm install`, `npm run build`). A student without Node will stall. | P0 | S–M |
| U2 | **No in-app explanation of the concepts.** "Lobanov", "Pillai", "JSD", "phone tier" appear with no plain-language help. A student can't tell which normalization to pick or what JSD = 0.46 *means*. | P0 | M |
| U3 | **Vowel chips show ARPABET (`IY`, `EH`), not the keywords** the rest of the app teaches (`BEET`, `BET`). Students think in keywords. | P1 | S |
| U4 | **Separation table is a wall of numbers** with no interpretation. No "these two vowels are strongly overlapping (likely merged)" plain-language read-out. | P1 | S–M |
| U5 | **Errors are developer-worded** ("Required columns not mapped: ['f1']"). Needs a friendlier nudge with an example. | P1 | S |
| U6 | **No guided "happy path."** The six stages assume the student knows the order and that they can skip 1–3 in demo mode. A short first-run checklist / callouts would help. | P1 | M |
| U7 | **Losing work is easy to fear.** State lives in a server session keyed by a browser id, so a reload is safe *while the server runs* — but nothing tells the student that, and a server restart silently drops everything. | P2 | M |
| U8 | **Keyboard/screen-reader support unverified.** Chips and the folder modal need focus states and `aria` labels. | P2 | M |

---

## 🔬 Researcher

> *Goal: process real corpora reproducibly, defend the method, and get
> publication-ready output and numbers with uncertainty.*

| # | Finding | Priority | Effort |
|---|---------|----------|--------|
| R1 | **No reproducible recipe.** There's no way to export/import the full run config (paths, normalization + params, vowel selection, filters) as JSON, so an analysis can't be re-run or shared verbatim. Provenance for a paper is manual. | P0 | M |
| R2 | **Built-in separation has no uncertainty.** JSD/Pillai/Bhattacharyya are point estimates; no bootstrap CIs or significance. phonJSD provides bootstrap CIs — the native engine should at least offer bootstrapped JSD CIs and Pillai *p*. | P0 | M |
| R3 | **Headless pipeline is partial.** The CLI covers discover/normalize/separation but **not** align/extract, so a researcher can't script the whole pipeline over many corpora. | P1 | M |
| R4 | **Point measurements only.** new-fave emits formant *tracks* (DCT); Vowelchemy uses a single point per vowel, so diphthong/VISC dynamics can't be studied. | P1 | L |
| R5 | **No outlier handling in the UI.** `analysis.flag_outliers` exists but isn't exposed; automatically-tracked formants need review/exclusion before analysis. | P1 | S–M |
| R6 | **Normalization knobs hidden.** Watt–Fabricius corner vowels and the ANAE `G` constant are library params but not surfaced; non-English/IPA vowel coding isn't configurable (keyword/lexset maps are English-only). | P1 | M |
| R7 | **Scale limits on plots.** Every token is sent to Plotly; a 100k-token corpus will make the vowel-space scatter sluggish. Need sampling / density (hexbin/contour) modes and server-side thinning. | P1 | M |
| R8 | **Publication export is thin.** Interactive Plotly only; no vector (SVG/PDF) export preset, no control of font size / DPI / title for figures destined for a manuscript. | P2 | M |
| R9 | **`/api/browse` exposes the whole filesystem.** Correct for a local single-user tool, but risky if the server is ever shared. Needs a documented `--root`/confinement option and an off switch. | P1 | S |
| R10 | **In-memory, single-process state.** No persistence (server restart loses sessions), no named projects, no side-by-side corpus comparison, and a running job's id isn't stored client-side to reconnect after a reload. | P2 | M–L |
| R11 | **External tools aren't CI-verified.** MFA/new-fave/phonJSD integrations are structurally tested but never exercised against the real tools; version drift can break them silently. | P1 | M |

---

## Cross-cutting themes

1. **Meet the two audiences where they are.** Students need *explanation and
   guardrails*; researchers need *control, reproducibility, and scale*. Most
   items below serve one primary audience — tag decisions accordingly.
2. **Reproducibility is the highest-leverage researcher feature** (R1) and also
   helps students hand in a "recipe" (U6).
3. **A little pedagogy goes a long way** (U2/U4) and is cheap relative to impact.

---

## Prioritized improvement plan

### Milestone 1 — "First run just works" (mostly students)
- **U1** Ship a Node-free path: either commit a prebuilt `frontend/dist`, or add
  a `make setup` / `vowelchemy setup` that runs the npm build, plus a Docker
  image. *(S–M)*
- **U2/U4** Add an in-app **Help/Glossary** drawer and inline `(?)` tooltips for
  normalization methods and each metric, plus a one-line plain-language verdict
  under the separation table ("JSD 0.46 — substantial overlap; likely merging").
  *(M)*
- **U3** Show keyword labels (`BEET`, `BET`) on vowel chips, with ARPABET as a
  secondary line. *(S)*
- **U5** Wrap the common backend errors in friendlier copy with an example fix. *(S)*

### Milestone 2 — "Reproducible & rigorous" (mostly researchers)
- **R1** **Save/Load analysis recipe** (JSON): endpoints `GET/POST /api/recipe`
  capturing paths, `norm_method` (+ params), `selected_vowels`, `filters`, engine
  choice; a sidebar "Save recipe / Load recipe" control. Stamp exports with it. *(M)*
- **R2** Add **bootstrap CIs** to the built-in JSD and a Pillai *p*-value; show
  CI columns and error bars on the separation chart. *(M)*
- **R5** Surface **outlier flagging/removal** (Dataset stage toggle over
  `flag_outliers`, with a count and a review table). *(S–M)*
- **R9** Add a `--root <dir>` confinement flag for `/api/browse` and document the
  local-tool security model. *(S)*

### Milestone 3 — "Headless & scale" (researchers)
- **R3** Extend the CLI with `align` and `extract` subcommands (reusing the
  library) for full scripted pipelines. *(M)*
- **R7** Server-side **thinning + density modes** (hexbin / 2-D KDE contour) for
  large corpora; cap scatter tokens with a documented sample. *(M)*
- **R11** A CI job (or a documented `make smoke-tools`) that runs MFA/new-fave/
  phonJSD on a tiny fixture corpus. *(M)*

### Milestone 4 — "Depth & polish"
- **R4** Formant-**trajectory** support (ingest new-fave tracks; trajectory and
  DCT-based plots). *(L)*
- **R6** Configurable normalization params + **custom vowel-coding maps** (IPA /
  non-English) via an uploadable mapping. *(M)*
- **R8** Publication **export presets** (SVG/PDF, font/DPI/title controls). *(M)*
- **R10** Optional **persistent projects** (named, on-disk) and reconnect-to-job
  after reload; **U7/U8** state-safety messaging and an a11y pass. *(M–L)*

---

## Suggested next 3 things to build

1. **Save/Load recipe (R1)** — unlocks reproducibility for researchers and a
   "hand-in recipe" for students; small surface area, high value.
2. **Glossary + inline metric verdicts (U2/U4)** — biggest student-experience
   win for the least code.
3. **Bootstrap CIs on built-in JSD/Pillai (R2)** — makes the default engine
   defensible in a write-up without requiring R.
