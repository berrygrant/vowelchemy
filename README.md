# 🧪 Vowelchemy

**Turn conversational speech corpora into normalized, analyzable vowel data — in one app.**

Vowelchemy is a lab-friendly tool for students and researchers doing
sociophonetic vowel analysis. Point it at a corpus of recordings and
transcripts and it walks you through the whole pipeline: force-alignment,
formant extraction, normalization, filtering, interactive visualization, and
category-separation metrics — with sensible defaults at every step and a demo
mode so you can learn the workflow before touching real data.

```mermaid
flowchart LR
    A[Corpus<br/>wav + transcripts] --> B[Force-align<br/>Montreal Forced Aligner]
    B --> C[Extract vowels<br/>new-fave]
    C --> D[Normalize<br/>Lobanov / Labov-ANAE / …]
    D --> E[Filter & group<br/>by vowel + demographics]
    E --> F[Download CSV]
    E --> G[Interactive plots<br/>distribution-first]
    E --> H[Separation metrics<br/>phontrast / built-in JSD]
```

Each stage **detects whether its work is already done** — if your TextGrids are
already aligned, or you already have an extracted-vowel CSV, Vowelchemy lets you
skip straight ahead.

---

## Install

### The no-terminal way (for students)

Two options that never open a command line:

- **The desktop app.** Download `Vowelchemy-macOS.zip` or
  `Vowelchemy-Windows.zip` from the
  [Releases page](https://github.com/berrygrant/vowelchemy/releases), unzip,
  and double-click the app. Your browser opens with Vowelchemy running —
  Python not required. (Maintainers: the Actions workflow **Build desktop
  app** produces these; run it manually or push a `v*` tag.)
- **The one-click launcher.** Use **Code ▸ Download ZIP** on this page,
  unzip, and double-click **`Start Vowelchemy (Mac).command`** or
  **`Start Vowelchemy (Windows).bat`**. The first run installs everything
  into a private environment inside the folder (a few minutes; needs
  [Python 3](https://www.python.org/downloads/) installed); every later run
  starts straight away.

First-open warnings are normal for unsigned downloads: on macOS,
**right-click the file → Open** the first time; on Windows SmartScreen,
**More info → Run anyway**.

Both cover the *analysis* half of the pipeline (demo mode, loading extracted
CSVs, normalization, plots, separation metrics). Aligning and extracting from
raw audio still needs MFA / new-fave on your PATH (below) — many students
never need them, because the lab provides pre-extracted CSVs.

### 1. The app (Python/FastAPI backend + React front-end)

Vowelchemy is a **FastAPI** backend that exposes the analysis library, plus a
**React** (Vite + TypeScript) front-end that renders server-produced Plotly
charts. Install the backend, build the UI once, then launch:

```bash
git clone https://github.com/berrygrant/vowelchemy
cd vowelchemy
python3 -m venv .venv          # private environment for Vowelchemy
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install .                  # backend (pandas, scipy, plotly, fastapi) + the prebuilt UI
vowelchemy app                 # serves API + UI at http://127.0.0.1:8000 and opens your browser
```

> **Don't skip the venv lines.** A bare `pip install .` fails on modern
> Python setups (Homebrew, current Linux distros) with an
> `externally-managed-environment` error, and a system-wide `pip` often
> belongs to a different Python than the one that would run `vowelchemy`.
> The virtual environment sidesteps both. Re-run `source .venv/bin/activate`
> in every new terminal — or skip all of this with the double-click
> launchers above, which create and reuse their own environment
> (`.venv-app/`) automatically.

(`--no-browser` suppresses the auto-open; `--port` changes the port.)

The backend pulls in only lightweight scientific-Python packages plus FastAPI.
You can explore the entire analysis, visualization, and separation-metrics
workflow immediately using **Demo mode** (a button in the sidebar) — no corpus,
aligner, or R required.

> **No Node needed.** The built UI is committed inside the package
> (`vowelchemy/webui/`) and ships in the wheel, so `pip install .` then
> `vowelchemy app` serves it from any directory. After changing frontend
> source, rebuild with `vowelchemy setup` (needs Node ≥ 18).
>
> **Deploying to a lab server?** A Dockerfile ships for that:
>
> ```bash
> docker build -t vowelchemy .
> docker run -p 8000:8000 -v /path/to/corpora:/data vowelchemy
> ```
>
> This needs Docker installed *and its daemon running* (on macOS/Windows
> that means Docker Desktop is open), plus network access to Docker Hub for
> the base images. It's the right tool for a shared lab machine, not a
> student laptop — students should use the launchers or desktop app above.
>
> **Developing the UI?** Run the backend with `vowelchemy app` and, in another
> terminal, `cd frontend && npm run dev` for a hot-reloading dev server at
> `http://localhost:5173` that proxies `/api` to the backend.

### Advanced / researcher features

Save & reload a **reproducible recipe** (config as JSON) and **named projects**
(sidebar); **bootstrap JSD confidence intervals** and a **Pillai permutation
p-value**; **outlier removal**; **formant-trajectory** plots for diphthongs
(Visualize → Trajectories); **density/contour** vowel-space modes and token
thinning for large corpora; **PNG/SVG export**; configurable normalization
parameters and **custom (IPA/non-English) vowel-label maps**; an in-app
**glossary**. The folder browser can be confined with
`VOWELCHEMY_BROWSE_ROOT=/data` when the server isn't purely local.

### 2. The aligner and extractor (acquisition half)

Force-alignment and formant extraction are heavy, specialized tools that live
in their own environments. Vowelchemy *orchestrates* them — it does not bundle
them.

**Montreal Forced Aligner** (for `2 · Align`):

```bash
conda create -n aligner -c conda-forge montreal-forced-aligner
conda activate aligner
mfa model download acoustic english_us_arpa
mfa model download dictionary english_us_arpa
```

**new-fave** (for `3 · Extract`):

```bash
pip install new-fave        # provides the `fave-extract` command
```

Launch Vowelchemy from an environment where `mfa` and/or `fave-extract` are on
your `PATH`; the sidebar shows a 🟢 when each tool is detected.

### 3. phontrast (optional — canonical separation metrics)

Vowelchemy has a built-in Python implementation of JSD-based separation, so
`6 · Separation` works out of the box. To use the **canonical** engine — the
[phontrast](https://github.com/berrygrant/phontrast) R package (formerly
*phonJSD*; legacy installs still work) — install R (≥ 4.1) and:

```r
install.packages("remotes")
remotes::install_github("berrygrant/phontrast")
```

Make sure `Rscript` is on your `PATH`. Vowelchemy will then offer phontrast as
an engine in the separation stage and call `compare_overlap_metrics()` directly.

---

## Quickstart

```bash
vowelchemy app
```

Then click **✨ Load demo dataset** in the sidebar. This loads a synthetic
18-speaker corpus that contains a deliberately planted **age-graded low-back
merger** (LOT ~ THOUGHT overlap increases across apparent time) and a stable,
well-separated **BET vs BEET** contrast — so the plots and metrics have
something real to show.

Jump to **5 · Visualize** to build *BET/BEET F1 by Age Group*, or **6 ·
Separation** to watch the LOT~THOUGHT JSD fall from ~0.96 (older) to ~0.10
(younger).

**New to research?** [`docs/TUTORIAL.md`](docs/TUTORIAL.md) is a guided
walkthrough for undergraduate researchers — a demo warm-up, then a complete
real-corpus study (question → hypothesis → analysis → interpretation →
write-up), using the lab's PREP corpus as the worked example.

---

## The pipeline, stage by stage

| Stage | What it does |
|-------|--------------|
| **1 · Corpus** | Give a single **root folder** and let Vowelchemy **auto-detect** the audio / transcript / aligned sub-folders (fuzzy, content-based), or set each path yourself with a **click-to-browse folder picker**. Folders can be the **same, separate, or per-speaker sub-folders**, and may be on a **mounted remote filesystem**. It pairs files by name, detects which recordings are already force-aligned, and finds existing vowel CSVs. |
| **2 · Align** | If recordings lack a phone tier, force-align them with MFA. Vowelchemy stages the corpus (even across separate folders), downloads models, and runs `mfa align` on a background job with a **live progress bar** (phase + percent). |
| **3 · Extract** | Measure vowel formants with new-fave's `fave-extract` (`corpus` / `subcorpora` mode) — again on a background job with a **live progress bar** — or load/upload an existing measurement CSV. Raw Hz formants are kept so you can re-normalize freely. |
| **4 · Dataset** | Auto-detect the column schema (override if needed), join speaker demographics, pick a normalization method, select vowels, filter/group by any sociodemographic column, preview, and **download the tidy dataset as CSV**. |
| **5 · Visualize** | Build interactive, **distribution-revealing** plots (see below). |
| **6 · Separation** | Compute JSD / Pillai / Bhattacharyya separation between vowel categories, optionally within each level of a factor (e.g. Age Group). Uses the phontrast R package when available, the built-in engine otherwise. |

---

## Normalization methods

Normalization is applied **post-hoc and transparently** — raw formants are
extracted once, and switching methods re-normalizes instantly (great for
teaching the difference). The default is **Lobanov**, the ANAE standard.

| Method | Key | What it does | Units |
|--------|-----|--------------|-------|
| **Lobanov** (default) | `lobanov` | Per-speaker z-score of each formant `(F − mean)/sd` | z-score |
| **Labov ANAE** | `labov_anae` | Log-mean scaling to a shared grand mean *G* (Telsur 6.896874); a uniform per-speaker rescaling | scaled Hz |
| **Nearey (shared)** | `nearey` | Subtract one per-speaker log-mean from every formant | log-Hz |
| **Nearey1** | `nearey1` | Subtract a per-speaker, per-formant log-mean | log-Hz |
| **Bark** | `bark` | Traunmüller Hz→Bark transform (psychoacoustic) | Bark |
| **Watt–Fabricius** | `watt_fabricius` | Divide by a per-speaker S-centroid from corner vowels (FLEECE/TRAP) | ratio |
| **None** | `none` | Raw Hz | Hz |

References: Lobanov (1971); Labov, Ash & Boberg (2006, *ANAE*); Nearey (1978);
Watt & Fabricius (2002); Fabricius, Watt & Johnson (2009); Traunmüller (1990).

---

## Visualizations

The house style favors forms that reveal the **distribution**, not just the mean:

- **Vowel space** — the canonical F2×F1 plot with 2-SD confidence ellipses and
  direct centroid labels.
- **Cross builder** — grouped **violins with an inner box and raw jittered
  tokens** (e.g. *BET/BEET F1 by Age Group*); also box and strip styles.
- **Ridgeline** — stacked density curves across a factor's levels, exposing
  modality and shift.
- **Separation charts** — a metric-by-group bar (merger trajectories) and a
  vowel×vowel heatmap.

Colors come from a validated colorblind-safe categorical palette.

---

## Separation metrics & phontrast

The **Jensen-Shannon Divergence (JSD)** between two vowels' distributions in
(normalized) formant space measures how distinguishable they are:

- **1** — fully separated,
- **0** — indistinguishable (merged).

Vowelchemy reports JSD alongside **Pillai's trace** and **Bhattacharyya
overlap** for triangulation, and can compute all of them **within each level of
a factor** (e.g. per Age Group) to reveal mergers in apparent time.

Two engines:

- **phontrast (R)** — your lab's canonical package. When R + phontrast (or a
  legacy phonJSD install) are present, Vowelchemy calls
  `compare_overlap_metrics(data, features, category_col, group_col)` and returns
  its full table (JSD, Pillai, Bhattacharyya, Mahalanobis, percent overlap, CIs).
- **Built-in (Python)** — a methodologically aligned KDE-based implementation
  (base-2 JSD in `[0, 1]`) that needs no R, so the app always works.

---

## Command line

```bash
vowelchemy app                                    # launch the app
vowelchemy setup                                   # build the UI (needs Node)
vowelchemy demo ./demo                             # write a synthetic dataset
vowelchemy discover ./audio --transcripts ./texts  # scan a corpus
vowelchemy align ./audio --transcripts ./texts -o ./aligned    # MFA (scripted)
vowelchemy extract ./audio --aligned ./aligned -o ./vowels     # new-fave (scripted)
vowelchemy normalize vowels.csv -m lobanov -s speakers.csv -o out.csv
vowelchemy separation vowels.csv --vowels BEET,BET,LOT,THOUGHT --group-by "Age Group" -s speakers.csv
```

The full pipeline is scriptable headlessly with `align` + `extract`, so many
corpora can be batch-processed without the UI.

Vowels can be given as ARPABET (`IY`), Wells lexical sets (`FLEECE`), or
keywords (`BEET`) — all resolve to the same category.

---

## Python API

Everything the app does is available as a library (no web server required):

```python
from vowelchemy import analysis, normalization, metrics
from vowelchemy.schema import ColumnSchema

df = analysis.load_vowel_data("vowels.csv")
schema = ColumnSchema.detect(df)                       # auto-detect columns
df = analysis.join_demographics(df, analysis.load_demographics("speakers.csv"), schema)
df = analysis.add_vowel_labels(df, schema)

df = normalization.normalize(df, schema, "lobanov").data
sep = metrics.pairwise_separation(df, schema,
                                  vowels=["LOT", "THOUGHT"], group_by="Age Group")
print(sep[["group_value", "vowel_a", "vowel_b", "JSD", "Pillai"]])
```

## Bring your own vowel data

Vowelchemy doesn't hard-code any one tool's column names. `ColumnSchema.detect`
recognizes common spellings from **new-fave**, legacy **FAVE-extract**, the
**NORM** suite, and hand-made CSVs (`speaker`/`name`, `vowel`/`label`/`plt_vclass`,
`F1`/`F1_50`, …). Anything it can't guess, you map with one click in the app or
by passing overrides to `ColumnSchema.detect(df, {...})`.

## Remote / mounted corpora

A remotely stored corpus (SSHFS, SMB, NFS) simply appears as a normal path once
mounted — give Vowelchemy that mounted path. It validates existence and
readability without assuming local disk. Alignment/extraction read a lot of
audio, so a fast mount (or staging locally) is recommended for large corpora.

---

## Architecture & project layout

Vowelchemy is a **Python library** wrapped by a **FastAPI** backend, driven by a
**React** front-end. The library holds all the real logic (and is fully usable on
its own); the backend is thin glue that also produces the Plotly charts as JSON;
React renders them with plotly.js and never re-implements chart logic.

```
Start Vowelchemy (Mac).command    # double-click launcher (self-installing)
Start Vowelchemy (Windows).bat    # double-click launcher (self-installing)
packaging/desktop/    # PyInstaller desktop app (entry + spec; built by CI)
vowelchemy/           # Python library + API (pip installable)
  api.py              # FastAPI backend — exposes the library over JSON
  cli.py              # command-line entry point (`vowelchemy …`)
  corpus.py           # discovery, pairing, alignment detection, autodetect + browse
  alignment.py        # MFA orchestration + corpus staging
  extraction.py       # new-fave orchestration
  jobs.py             # background jobs + progress parsing (align/extract)
  normalization.py    # Lobanov, Labov-ANAE, Nearey, Bark, Watt–Fabricius, …
  schema.py           # column auto-detection
  analysis.py         # loaders, join / select / filter / group / outliers
  metrics.py          # built-in JSD (+ bootstrap CIs), Pillai (+ permutation p), Bhattacharyya
  trajectories.py     # formant-track (diphthong) trajectories
  phontrast.py        # bridge to the phontrast R package (formerly phonJSD)
  projects.py         # persistent named projects (~/.vowelchemy/projects)
  glossary.py         # in-app glossary, key readings, metric verdicts
  runners.py          # shared subprocess / tool-detection helpers
  visualization.py    # Plotly figures (distribution-first)
  sample_data.py      # synthetic demo corpus (points + trajectory tracks)
  constants.py        # vowel identifiers (ARPABET ↔ lexical set ↔ keyword)
  webui/              # committed production build of the React UI (ships in the wheel)
frontend/             # React + Vite + TypeScript single-page app (source)
  src/App.tsx         # shell + stage routing
  src/stages/*.tsx    # the six pipeline stages
  src/components/*    # sidebar, PlotlyChart, DataTable, form controls
  src/hooks/*         # useJob (progress + reconnect), useBusy
  src/api.ts          # typed fetch client (session-aware)
  src/lib.ts          # shared utils (downloads, CSV, grouping columns)
examples/             # ready-to-use demo CSVs
docs/TUTORIAL.md      # guided first study for undergrads (demo warm-up + PREP corpus)
docs/REFERENCES.md    # the methods literature, with a feature → citation map
docs/FEATURE_AUDIT.md # detailed feature inventory & test-coverage map
docs/QOL_AUDIT.md     # usability audit (student + researcher) & roadmap
docs/UNDERGRAD_RESEARCH_PLAN.md  # improvement plan for student researchers
CITATION.cff          # how to cite Vowelchemy itself
tests/                # pytest suite (library + API)
```

> **Local-tool security note.** The folder picker lets the UI browse the
> *server's* filesystem (the machine running `vowelchemy app`) — intended for
> local single-user use. When the server isn't purely local, confine browsing
> and autodetect to one directory tree with `VOWELCHEMY_BROWSE_ROOT=/data`
> (the Docker image sets this to `/data` by default).

## Development

```bash
python3 -m venv .venv && source .venv/bin/activate   # once per checkout
pip install -e ".[dev]"      # backend + test deps
pytest                        # library + API tests

cd frontend
npm install
npm run dev                   # hot-reloading UI at http://localhost:5173
npm run build                 # production build → vowelchemy/webui (commit it)
```

The Python tests cover the schema, normalization math (Lobanov, Labov-ANAE,
Nearey, Bark, Watt–Fabricius), analysis, the built-in separation metrics, corpus
discovery, the phontrast bridge, the extraction command builder, and every FastAPI
endpoint (`fastapi.testclient`). The React app type-checks with `tsc` on each
build.

> **Note on tool CLIs.** MFA and new-fave evolve their command-line flags
> between releases. Vowelchemy targets current MFA 3.x and new-fave interfaces
> and passes anything nonstandard through an `extra_args` escape hatch; if a run
> fails, check the streamed log against `mfa align --help` / `fave-extract
> --help` for your installed versions.

## References & citing

The methods implemented here come from the sociophonetics and information-theory
literature — **`docs/REFERENCES.md`** has the full reference list plus a
feature → citation map for write-ups, and the in-app **Glossary** lists the key
readings. To cite Vowelchemy itself, use **`CITATION.cff`** (GitHub's "Cite this
repository" button).

## Credits

Vowelchemy orchestrates and builds on these tools — cite them when you use it:

- Berry, G. M. (2026). *phontrast: Contrast and separation metrics for
  phonological categories* (Version 2.4.0) [Computer software].
  https://doi.org/10.5281/zenodo.21864533 (formerly *phonJSD*)
- Fruehwald, J. (2024). *new-fave: Vowel formant extraction* [Computer
  software]. Zenodo. https://doi.org/10.5281/zenodo.14837885
- McAuliffe, M., Socolof, M., Mihuc, S., Wagner, M., & Sonderegger, M. (2017).
  Montreal Forced Aligner: Trainable text-speech alignment using Kaldi. In
  *Proceedings of Interspeech 2017* (pp. 498–502). ISCA.
  https://doi.org/10.21437/Interspeech.2017-1386
- Rosenfelder, I., Fruehwald, J., Brickhouse, C., Evanini, K., Seyfarth, S.,
  Gorman, K., Prichard, H., & Yuan, J. (2022). *FAVE (Forced Alignment and
  Vowel Extraction)* (Version 2.0.0) [Computer software]. Zenodo.
  https://doi.org/10.5281/zenodo.22281

Vowelchemy is released under the MIT License (see `LICENSE`).
