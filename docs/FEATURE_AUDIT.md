# Vowelchemy Feature Audit

*A complete inventory of what the tool does today, where each feature lives,
what is tested, and the limitations visible in the code. Compiled from a
full-code review (2026-08-20), reconciled after the repository-wide cleanup in
the same change-set. Companion documents: `docs/QOL_AUDIT.md` (usability
audit & shipped roadmap), `docs/UNDERGRAD_RESEARCH_PLAN.md` (next
improvements), `docs/REFERENCES.md` (methods literature).*

**Pipeline:** corpus discovery → MFA force-alignment → new-fave formant
extraction → normalization → dataset build (filter/outliers) → visualization →
separation metrics (built-in JSD/Pillai/Bhattacharyya, optional phontrast-R
engine).

---

## 1. Library (`vowelchemy/`)

### constants.py — vowel identity
- `ARPABET_VOWELS`: 16 bare-ARPABET vowels ↔ (Wells lexical set, teaching keyword), e.g. `IY ↔ (FLEECE, BEET)`.
- `canonical_vowel` (strip stress digits, upper-case), `resolve_vowel` (ARPABET/lexical-set/keyword → ARPABET), `vowel_display_label` (`"EH (DRESS / BET)"`).
- Discovery file types (`.wav`; `.lab`/`.txt`; `.TextGrid`), phone-tier name set (MFA/FAVE/MAUS variants), MFA defaults (`english_us_arpa`), `DEFAULT_NORMALIZATION="lobanov"`.

### schema.py — column auto-detection
- `ColumnSchema.detect(df, overrides)`: ordered case-insensitive aliases for 12 logical fields (speaker, vowel, f1–f3, duration, word, stress, preseg, folseg, time, token_id) covering new-fave (`F1_50`), FAVE (`plt_vclass`), NORM, and Praat spellings; user overrides win. Required: speaker, vowel, f1, f2.

### corpus.py — discovery, autodetect, browsing
- `sniff_textgrid_tiers` / `is_aligned_textgrid`: tolerant long+short TextGrid tier sniffer; phone tier ⇒ "aligned".
- `discover_corpus(audio, transcripts?, aligned?)`: recursive scan, basename-stem pairing across separate folders, per-speaker sub-folder speaker inference, duplicate-stem warnings; `CorpusInventory` views (`paired`, `needs_alignment`, `fully_aligned`, …).
- `validate_location`: exists/dir/readable check tolerant of stale network mounts.
- `find_vowel_data` + `suggest_corpus_layout`: shared `VOWEL_CSV_HINTS` (includes new-fave's `*_points.csv`); fuzzy root-folder layout autodetect via common-ancestor folders, speaker-CSV regex (budget: 60k files / 300 sniffed TextGrids).
- `list_directory` + `is_within_root`: server-side folder browser with `has_wav`/`has_transcript` badges (depth-2 probe), confinable to `VOWELCHEMY_BROWSE_ROOT` (escapes clamp back; no browsing above the root).

### alignment.py — MFA (McAuliffe et al. 2017)
- `mfa_status`, `download_models`, `validate_corpus` (exposed via `vowelchemy validate`), `align_corpus` (`--output_format long_textgrid`, beam/single-speaker/extra-args escape hatches), `stage_corpus`/`align_inventory` (symlink staging with copy fallback; reports symlinked vs copied).

### extraction.py — new-fave (Fruehwald 2024)
- `newfave_status`; command builder for `fave-extract corpus|subcorpora` with `--destination/--speakers/--exclude-overlaps` + `extra_args`; staging of wav+TextGrid pairs; heuristic output discovery ranking `*_points.csv` first; `load_existing_vowel_data` for pre-extracted tables (CSV or TSV via the shared `read_table`).

### normalization.py — 7 methods (see docs/REFERENCES.md)
- `lobanov` (default; per-speaker z-score), `labov_anae` (log-mean scaling to G; Telsur G = 6.896874; custom G supported), `nearey` / `nearey1` (shared / per-formant log-mean), `bark` (Traunmüller), `watt_fabricius` (modified S-centroid; configurable corner vowels; missing-corner speakers → NaN + note), `none`.
- Applied post-hoc over raw Hz → `F1_norm/F2_norm/F3_norm`; per-method notes (e.g. <2-token speakers → NaN z-scores) surface through the API.

### analysis.py — dataset assembly
- `read_table` (the one CSV/TSV loader, delimiter-sniffing), `join_demographics` (auto-detected speaker key, string-normalized, `_spk` collision suffix), `add_vowel_labels` (+ custom IPA/non-English `label_map`), `canonical_vowel_series` (the shared "which vowel is this row" definition), `list_vowels`, `select_vowels` (ARPABET/lexical-set/keyword), `candidate_grouping_columns`, `apply_filters`, `summarize`, `flag_outliers` (n-SD from speaker×vowel centroid).

### metrics.py — built-in separation engine
- `jensen_shannon_divergence`: base-2 JSD ∈ [0,1] via KDE on a shared padded grid; fitted-Gaussian fallback for sparse cells; `detail=True` reports the estimator actually used (`kde` / `gaussian` / `kde+gaussian`), which is what the `method` column records.
- `pillai_score` (two-group MANOVA trace) + `pillai_p` (permutation test); `bhattacharyya_overlap` (analytic Gaussian coefficient); `jsd_ci` (percentile bootstrap).
- `pairwise_separation`: all pairs × group levels, `min_tokens` floor (default 5), optional bootstrap/permutations, sorted by JSD.

### phontrast.py — canonical R engine (Berry 2026)
- Detects `Rscript` plus the **phontrast** package, falling back to a legacy **phonJSD** install (the package was renamed; `compare_overlap_metrics()` is unchanged). Generates and runs an R driver over an exported CSV subset; graceful notes when R or output is missing.

### visualization.py — server-side Plotly (all figures theme-aware light/dark)
- `vowel_space` (reversed F2×F1; ellipses + centroid labels; modes `scatter`/`contour`/`ellipse`; token thinning with per-category floor, thinned count in title), `formant_cross` (violin/box/strip with overlaid jittered tokens; 8k-row display thinning), `ridgeline`, `separation_bar` (bootstrap CIs as error bars), `separation_matrix`, `trajectory_space`/`trajectory_time`.
- Colourblind-safe categorical palette with fixed reference-order colour assignment (colour follows the vowel, not the filtered subset).

### trajectories.py — formant tracks
- `TrackSchema.detect` (token_id + time, >1 row per token), `normalized_time` (per-token 0–1), `mean_trajectories` (mean formants per vowel × optional group per time bin).

### jobs.py, projects.py, sample_data.py, glossary.py
- `ProgressTracker` (ANSI-stripped phase keywords + `%`/`i/N` parsing) + `JobManager` (daemon threads, capped log, snapshots) for align/extract progress bars.
- Named on-disk projects (`~/.vowelchemy/projects` or `$VOWELCHEMY_PROJECTS_DIR`): recipe + vowels/speakers/tracks CSVs; sanitized names.
- Seeded synthetic data: 18-speaker point corpus with a stable BEET/BET contrast and an age-graded LOT~THOUGHT merger, plus trajectory tracks with real diphthongs.
- 16-term student glossary, key-readings list (served in-app), `jsd_verdict` plain-language thresholds.

---

## 2. HTTP API (`api.py`) — 37 routes

Per-session state keyed by the `X-Vowelchemy-Session` header; derived views:
`prepared` (join → labels → outlier removal → normalize) → `explore_base`
(+demographic filters; feeds Visualize/Separation) → `filtered` (+vowel
selection; the downloadable dataset). Previews capped at 500 rows.

| Area | Routes |
|---|---|
| Status & health | `GET /api/status` (tools incl. phontrast, data state, confinement), `GET /api/health` |
| Corpus | `POST /api/corpus/validate`, `POST /api/corpus/scan`, `POST /api/corpus/autodetect` (confinement-403), `GET /api/browse` (confinable picker) |
| Data in | `POST /api/demo`, `POST /api/voweldata/load` (400 on unreadable), `POST /api/voweldata/upload`, `POST /api/demographics/upload` (uploads sniff CSV/TSV), `POST /api/vowelmap/upload` |
| Jobs | `POST /api/align`, `POST /api/extract` (both → `{job_id}`), `GET /api/jobs/{id}` |
| Dataset | `GET/POST /api/schema`, `GET /api/normalization/methods`, `POST /api/normalization` (method + G / corner params), `GET /api/vowels` (keyword+lexset+counts), `GET /api/grouping-columns` (+ schema-detected `context_columns`), `POST /api/dataset` (vowels/filters/outliers), `GET /api/dataset/csv` |
| Figures | `POST /api/figure/{vowel-space,cross,ridgeline,trajectory}` (Plotly JSON) |
| Separation | `POST /api/separation` (built-in table + verdicts + bar/matrix figures + full CSV; optional phontrast run with R log), `GET /api/separation/csv` |
| Reproducibility | `GET/POST /api/recipe`, `GET /api/projects`, `POST /api/projects/{save,load}` |
| Trajectories | `POST /api/tracks/{demo,load}`, `GET /api/tracks/vowels` |
| Reference | `GET /api/glossary` (terms + key readings) |
| Static | `/` serves the packaged UI (`vowelchemy/webui`, wheel-shipped; dev fallback `frontend/dist`) |

---

## 3. React UI (`frontend/src/`)

Six-stage wizard; offline banner; dark mode follows `prefers-color-scheme`
(passed through to server-rendered figures). Sidebar: stage nav, tool status
(MFA / new-fave / phontrast), data summary, demo loader, Session panel
(recipe download/upload; save/load named projects), glossary drawer (terms +
key readings).

| Stage | Highlights |
|---|---|
| 1 Corpus | Root-folder auto-detect; Browse… pickers on every path field; scan summary metrics + warnings + recording table; one-click load of discovered vowel CSVs (from autodetect or scan) |
| 2 Align | Model/dictionary/jobs/output controls, model download, live phase+percent progress, tail log; job survives page reloads |
| 3 Extract | Existing-CSV load (server path or browser upload) or new-fave run with progress; auto-advance to Dataset |
| 4 Dataset | Schema editor with friendly missing-column help; normalization picker with per-method params (WF corners, ANAE G); demographics upload; outlier toggle + SD; custom vowel-map upload; keyword vowel chips; per-column value filters; preview + CSV download |
| 5 Visualize | Tabs: Cross (violin/box/strip), Vowel space (scatter/contour/ellipse modes), Ridgeline, Trajectories (demo or CSV tracks; F2×F1 path / formant-over-time); schema-driven default-group ranking (sociodemographic over phonetic context) |
| 6 Separation | Vowel chips, group-by, F1×F2/F1/F2 space, engine select (built-in / phontrast when detected), bootstrap-CI + permutation-p toggles, verdict column, downloads, bar + matrix charts |

Shared: `PlotlyChart` (PNG/SVG export at 1–4×), `FolderPicker`/`PathInput`,
`DataTable`, `ProgressBar`, chip `MultiSelect`; hooks `useJob`
(poll + localStorage reconnect + one-shot `onDone`) and `useBusy` (the single
busy/error wrapper); `lib.ts` (blob/CSV/grouping utilities).

---

## 4. CLI (`vowelchemy …`)

`app` (uvicorn, serves packaged UI) · `setup` (rebuild UI → `vowelchemy/webui`;
needs Node) · `demo` · `discover` · `validate` (mfa validate) · `align` ·
`extract` · `normalize` · `separation`. Full headless pipeline:
`align → extract → normalize → separation`. Defaults come from
`constants.DEFAULT_*`.

Not exposed via CLI: bootstrap CIs / permutation p / dimensions choice /
phontrast engine; MFA `beam`/`single_speaker`; new-fave `subcommand`/`extra_args`
(library-level escape hatches only).

---

## 5. Infra & packaging

- **Wheel ships the UI**: the production build lands in `vowelchemy/webui/`
  (committed + `package-data`), so `pip install vowelchemy && vowelchemy app`
  serves it from anywhere; `webui_dir()` also accepts a legacy `frontend/dist`.
- **CI** (GitHub Actions): ruff (rule set pinned in pyproject so results don't
  drift with ruff releases) + pytest + opt-in tool smoke (auto-skips) +
  frontend type-check/build on Node 20.
- **Docker**: multi-stage (Node builds `webui` → copied into the package before
  `pip install`); `VOWELCHEMY_BROWSE_ROOT=/data` set by default.
- **Env vars**: `VOWELCHEMY_BROWSE_ROOT` (browser/autodetect confinement),
  `VOWELCHEMY_PROJECTS_DIR` (project storage).
- **Citing**: `CITATION.cff` at the repo root; methods literature in
  `docs/REFERENCES.md`.

---

## 6. Test coverage map (13 test files, 85 tests; 3 tool-smoke skips without MFA/new-fave/R)

**Covered:** constants/schema; corpus discovery + TextGrid sniffing;
extraction command-builder/staging/output-ranking; all 7 normalization methods
with math assertions; analysis (join/labels/select/filters/summarize);
metrics (JSD bounds/symmetry/1-D/sparse-NaN, Pillai & Bhattacharyya extremes,
bootstrap-CI bracketing, permutation-p ordering, merger ordering on demo
data); phontrast bridge (R-script generation, graceful no-R paths); jobs
(progress parsing, success/error); projects round-trip; sample-data
determinism; trajectories (detection, mean paths, diphthong movement);
**every FastAPI route** (test_api.py + test_api_coverage.py — including TSV
uploads, vowel-map upload, projects endpoints, tracks load/vowels, ridgeline,
separation CSV, friendly 400s); opt-in real-tool smoke tests.

**Known gaps (deliberate, documented):**
- `cli.py` — no subcommand/parser tests.
- `visualization.py` — exercised only through the figure endpoints; no direct
  unit tests of ellipse math, thinning counts, or dark theming.
- `alignment.py` — orchestration (stage/align/download/validate) runs only in
  the opt-in smoke suite; unit tests cover staging indirectly via extraction.
- `runners.run_streaming` timeout / missing-executable paths untested directly.
- Frontend — type-checked and built in CI, but no unit tests (`useJob`
  polling/reconnect, `preferredGroup`, `toCsv`).
- `BROWSE_ROOT` 403 path and `list_directory` clamping untested.

---

## 7. Known limitations (visible in code; candidates for the roadmap)

1. **In-memory sessions**: DataFrames live in a module dict keyed by a
   client-supplied header — lost on restart, unbounded across session ids,
   headerless requests share `"default"`. Projects are the persistence story.
2. **Single-process JobManager**: daemon threads + in-process registry; do not
   run uvicorn with multiple workers. Finished jobs are never pruned; no
   cancel endpoint; API align/extract set no timeout (phontrast defaults 1800 s).
3. **English-only defaults**: ARPABET/lexical-set/keyword maps, MFA models,
   and the `NATURAL_ORDER` group ordering are English; the custom vowel map
   fixes display labels only.
4. **Path confinement is partial**: `VOWELCHEMY_BROWSE_ROOT` guards browse +
   autodetect, but scan/load/tracks/output paths accept arbitrary server
   paths, and CORS is `*` — safe only under the stated single-user local-tool
   assumption.
5. **Display caps** (each noted in-UI where it bites): vowel-space thinning
   4k tokens (per-category floor 200), cross 8k rows, previews 500 (server) /
   200 (UI) rows, scan items 500/200, 50 values per filter column, 3000
   browser entries, autodetect budgets 60k files / 300 sniffed TextGrids.
6. **Separation matrix** renders only the first group level; no level picker.
7. **Recipes restore configuration, not data** — no corpus re-scan/reload on
   apply; schema column overrides and the tracks source aren't captured, so a
   manual column mapping isn't reproducible via recipe/project.
8. **Corpus pairing is basename-only** (duplicate stems collide with a
   warning; `.wav` only; root-level files → speaker `"unknown"`).
9. **new-fave CLI drift risk**: documented subcommands targeted; flags vary by
   release; output CSV discovery is heuristic (a stray CSV can be mis-picked).
10. **Uploads buffer fully in memory**; `prepared()` re-joins/re-normalizes on
    every request with no caching — fine at lab scale, a cost at 100k+ tokens.
11. **NaN-with-note edge cases**: Watt–Fabricius speakers missing corner
    vowels; Lobanov speakers with <2 tokens.
12. **No manual dark-mode toggle** (follows the OS); figures re-render
    server-side per theme.
