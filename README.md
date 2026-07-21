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
    E --> H[Separation metrics<br/>phonJSD / built-in JSD]
```

Each stage **detects whether its work is already done** — if your TextGrids are
already aligned, or you already have an extracted-vowel CSV, Vowelchemy lets you
skip straight ahead.

---

## Install

### 1. The app (Python/FastAPI backend + React front-end)

Vowelchemy is a **FastAPI** backend that exposes the analysis library, plus a
**React** (Vite + TypeScript) front-end that renders server-produced Plotly
charts. Install the backend, build the UI once, then launch:

```bash
git clone https://github.com/berrygrant/vowelchemy
cd vowelchemy
pip install -e .                                     # backend (pandas, scipy, plotly, fastapi)
cd frontend && npm install && npm run build && cd ..  # build the UI (needs Node ≥ 18)
vowelchemy app                                       # serves API + UI at http://127.0.0.1:8000
```

The backend pulls in only lightweight scientific-Python packages plus FastAPI.
You can explore the entire analysis, visualization, and separation-metrics
workflow immediately using **Demo mode** (a button in the sidebar) — no corpus,
aligner, or R required.

> **Developing the UI?** Run the backend with `vowelchemy app` and, in another
> terminal, `cd frontend && npm run dev` for a hot-reloading dev server at
> `http://localhost:5173` that proxies `/api` to the backend.

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

### 3. phonJSD (optional — canonical separation metrics)

Vowelchemy has a built-in Python implementation of JSD-based separation, so
`6 · Separation` works out of the box. To use the **canonical** engine — the
[phonJSD](https://github.com/berrygrant/phonJSD) R package — install R (≥ 4.1)
and:

```r
install.packages("remotes")
remotes::install_github("berrygrant/phonJSD")
```

Make sure `Rscript` is on your `PATH`. Vowelchemy will then offer phonJSD as an
engine in the separation stage and call `compare_overlap_metrics()` directly.

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

---

## The pipeline, stage by stage

| Stage | What it does |
|-------|--------------|
| **1 · Corpus** | Give a single **root folder** and let Vowelchemy **auto-detect** the audio / transcript / aligned sub-folders (fuzzy, content-based), or set each path yourself with a **click-to-browse folder picker**. Folders can be the **same, separate, or per-speaker sub-folders**, and may be on a **mounted remote filesystem**. It pairs files by name, detects which recordings are already force-aligned, and finds existing vowel CSVs. |
| **2 · Align** | If recordings lack a phone tier, force-align them with MFA. Vowelchemy stages the corpus (even across separate folders), downloads models, and runs `mfa align` on a background job with a **live progress bar** (phase + percent). |
| **3 · Extract** | Measure vowel formants with new-fave's `fave-extract` (`corpus` / `subcorpora` mode) — again on a background job with a **live progress bar** — or load/upload an existing measurement CSV. Raw Hz formants are kept so you can re-normalize freely. |
| **4 · Dataset** | Auto-detect the column schema (override if needed), join speaker demographics, pick a normalization method, select vowels, filter/group by any sociodemographic column, preview, and **download the tidy dataset as CSV**. |
| **5 · Visualize** | Build interactive, **distribution-revealing** plots (see below). |
| **6 · Separation** | Compute JSD / Pillai / Bhattacharyya separation between vowel categories, optionally within each level of a factor (e.g. Age Group). Uses phonJSD when available, the built-in engine otherwise. |

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

## Separation metrics & phonJSD

The **Jensen-Shannon Divergence (JSD)** between two vowels' distributions in
(normalized) formant space measures how distinguishable they are:

- **1** — fully separated,
- **0** — indistinguishable (merged).

Vowelchemy reports JSD alongside **Pillai's trace** and **Bhattacharyya
overlap** for triangulation, and can compute all of them **within each level of
a factor** (e.g. per Age Group) to reveal mergers in apparent time.

Two engines:

- **phonJSD (R)** — your lab's canonical package. When R + phonJSD are
  installed, Vowelchemy calls
  `compare_overlap_metrics(data, features, category_col, group_col)` and returns
  its full table (JSD, Pillai, Bhattacharyya, Mahalanobis, percent overlap, CIs).
- **Built-in (Python)** — a methodologically aligned KDE-based implementation
  (base-2 JSD in `[0, 1]`) that needs no R, so the app always works.

---

## Command line

```bash
vowelchemy app                                    # launch the app
vowelchemy demo ./demo                             # write a synthetic dataset
vowelchemy discover ./audio --transcripts ./texts  # scan a corpus
vowelchemy normalize vowels.csv -m lobanov -s speakers.csv -o out.csv
vowelchemy separation vowels.csv --vowels BEET,BET,LOT,THOUGHT --group-by "Age Group" -s speakers.csv
```

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
vowelchemy/           # Python library + API (pip installable)
  api.py              # FastAPI backend — exposes the library over JSON
  cli.py              # command-line entry point (`vowelchemy …`)
  corpus.py           # discovery, pairing, alignment detection, autodetect + browse
  alignment.py        # MFA orchestration + corpus staging
  extraction.py       # new-fave orchestration
  jobs.py             # background jobs + progress parsing (align/extract)
  normalization.py    # Lobanov, Labov-ANAE, Nearey, Bark, Watt–Fabricius, …
  schema.py           # column auto-detection
  analysis.py         # join / select / filter / group / summarize
  metrics.py          # built-in JSD, Pillai, Bhattacharyya
  phonjsd.py          # bridge to the phonJSD R package
  visualization.py    # Plotly figures (distribution-first)
  sample_data.py      # synthetic demo corpus
  constants.py        # vowel identifiers (ARPABET ↔ lexical set ↔ keyword)
frontend/             # React + Vite + TypeScript single-page app
  src/App.tsx         # shell + stage routing
  src/stages/*.tsx    # the six pipeline stages
  src/components/*    # sidebar, PlotlyChart, DataTable, form controls
  src/api.ts          # typed fetch client (session-aware)
examples/             # ready-to-use demo CSVs
docs/QOL_AUDIT.md     # usability audit (student + researcher) & roadmap
tests/                # pytest suite (library + API)
```

> **Local-tool security note.** The folder picker lets the UI browse the
> *server's* filesystem (the machine running `vowelchemy app`) — intended for
> local single-user use. Don't expose the server to an untrusted network as-is;
> a `--root` confinement flag is on the roadmap (see `docs/QOL_AUDIT.md`).

## Development

```bash
pip install -e ".[dev]"      # backend + test deps
pytest                        # library + API tests

cd frontend
npm install
npm run dev                   # hot-reloading UI at http://localhost:5173
npm run build                 # production build served by `vowelchemy app`
```

The Python tests cover the schema, normalization math (Lobanov, Labov-ANAE,
Nearey, Bark, Watt–Fabricius), analysis, the built-in separation metrics, corpus
discovery, the phonJSD bridge, the extraction command builder, and every FastAPI
endpoint (`fastapi.testclient`). The React app type-checks with `tsc` on each
build.

> **Note on tool CLIs.** MFA and new-fave evolve their command-line flags
> between releases. Vowelchemy targets current MFA 3.x and new-fave interfaces
> and passes anything nonstandard through an `extra_args` escape hatch; if a run
> fails, check the streamed log against `mfa align --help` / `fave-extract
> --help` for your installed versions.

## Credits

- **Montreal Forced Aligner** — McAuliffe et al.
- **new-fave** — Josef Fruehwald.
- **phonJSD** — Grant M. Berry.

Vowelchemy is released under the MIT License (see `LICENSE`).
