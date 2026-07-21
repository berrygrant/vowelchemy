"""Vowelchemy — an interactive Streamlit app for conversational vowel analysis.

Run with::

    vowelchemy app
    # or:  streamlit run vowelchemy/app.py

The app walks students through the pipeline in stages, each of which detects
whether its work is already done and lets you skip ahead:

    1. Corpus     — point at audio + transcripts (same or separate folders)
    2. Align      — force-align with MFA (or detect existing alignments)
    3. Extract    — measure vowels with new-fave (or load existing vowel data)
    4. Dataset    — normalize, join demographics, pick vowels, filter, download
    5. Visualize  — build distribution-revealing "cross" plots
    6. Separation — JSD/Pillai/Bhattacharyya separation metrics (phonJSD)
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from vowelchemy import (
    alignment,
    analysis,
    extraction,
    metrics,
    normalization,
    phonjsd,
    sample_data,
    visualization as viz,
)
from vowelchemy.constants import vowel_display_label
from vowelchemy.corpus import discover_corpus, find_vowel_data, validate_location
from vowelchemy.schema import ColumnSchema

st.set_page_config(page_title="Vowelchemy", page_icon="🧪", layout="wide")

STAGES = [
    "1 · Corpus",
    "2 · Align",
    "3 · Extract",
    "4 · Dataset",
    "5 · Visualize",
    "6 · Separation",
]

_DEFAULTS = {
    "audio_dir": "",
    "transcript_dir": "",
    "aligned_dir": "",
    "output_dir": "",
    "speakers_path": "",
    "inventory": None,
    "vowel_df": None,        # raw extracted formants
    "schema": None,          # ColumnSchema
    "schema_overrides": {},
    "demographics": None,
    "norm_method": "lobanov",
    "selected_vowels": [],
    "filters": {},
    "stage": STAGES[0],
    "align_log": "",
    "extract_log": "",
}


def _init_state() -> None:
    for k, v in _DEFAULTS.items():
        st.session_state.setdefault(k, v)


def _is_dark() -> bool:
    try:
        return st.get_option("theme.base") == "dark"
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# Derived data
# --------------------------------------------------------------------------- #
def prepared_dataframe():
    """Join demographics, add labels, and normalize the loaded vowel data."""
    df = st.session_state.vowel_df
    schema = st.session_state.schema
    if df is None or schema is None:
        return None, None, None
    out = df
    if st.session_state.demographics is not None:
        try:
            out = analysis.join_demographics(out, st.session_state.demographics, schema)
        except KeyError as exc:
            st.warning(f"Could not join demographics: {exc}")
    out = analysis.add_vowel_labels(out, schema)
    result = normalization.normalize(out, schema, st.session_state.norm_method)
    return result.data, schema, result


def filtered_dataframe():
    df, schema, result = prepared_dataframe()
    if df is None:
        return None, None, None
    if st.session_state.selected_vowels:
        df = analysis.select_vowels(df, schema, st.session_state.selected_vowels)
    df = analysis.apply_filters(df, st.session_state.filters)
    return df, schema, result


# --------------------------------------------------------------------------- #
# Sidebar
# --------------------------------------------------------------------------- #
def sidebar() -> None:
    st.sidebar.title("🧪 Vowelchemy")
    st.sidebar.caption("Corpus → alignment → vowels → analysis")
    st.session_state.stage = st.sidebar.radio("Pipeline stage", STAGES,
                                               index=STAGES.index(st.session_state.stage))

    st.sidebar.divider()
    st.sidebar.subheader("Tool status")
    mfa = alignment.mfa_status()
    nf = extraction.newfave_status()
    st.sidebar.write(
        f"{'🟢' if mfa.available else '⚪'} **MFA** "
        + (f"`{mfa.version}`" if mfa.available else "not detected")
    )
    st.sidebar.write(
        f"{'🟢' if nf.available else '⚪'} **new-fave** "
        + (f"`{nf.version}`" if nf.available else "not detected")
    )
    pj = phonjsd.phonjsd_status()
    st.sidebar.write(
        f"{'🟢' if pj.available else '⚪'} **phonJSD** "
        + (f"`{pj.version}`" if pj.available else "not detected (built-in JSD used)")
    )

    st.sidebar.divider()
    st.sidebar.subheader("Data loaded")
    df = st.session_state.vowel_df
    if df is not None:
        st.sidebar.write(f"🟢 {len(df):,} vowel tokens")
        if st.session_state.demographics is not None:
            st.sidebar.write(f"🟢 {len(st.session_state.demographics)} speakers (demographics)")
        st.sidebar.write(f"Normalization: **{st.session_state.norm_method}**")
    else:
        st.sidebar.write("⚪ No vowel data yet")

    st.sidebar.divider()
    if st.sidebar.button("✨ Load demo dataset", width="stretch"):
        _load_demo()
        st.rerun()
    st.sidebar.caption("Demo mode loads a synthetic corpus so you can explore "
                       "stages 4–6 without MFA/new-fave.")


def _load_demo() -> None:
    tokens, speakers = sample_data.make_demo_dataset()
    st.session_state.vowel_df = tokens
    st.session_state.demographics = speakers
    st.session_state.schema = ColumnSchema.detect(tokens)
    st.session_state.selected_vowels = []
    st.session_state.filters = {}
    st.session_state.stage = "4 · Dataset"
    st.toast("Loaded synthetic demo corpus (18 speakers, low-back merger by age).")


# --------------------------------------------------------------------------- #
# Stage 1 — Corpus
# --------------------------------------------------------------------------- #
def stage_corpus() -> None:
    st.header("1 · Locate the corpus")
    st.write(
        "Point vowelchemy at your recordings and transcripts. They can live in "
        "the same folder or separate folders, and the paths may be on a mounted "
        "remote filesystem — just give the mounted path."
    )
    c1, c2 = st.columns(2)
    st.session_state.audio_dir = c1.text_input("Audio folder (.wav)",
                                                st.session_state.audio_dir)
    st.session_state.transcript_dir = c2.text_input(
        "Transcript folder (leave blank if same as audio)", st.session_state.transcript_dir
    )
    c3, c4 = st.columns(2)
    st.session_state.aligned_dir = c3.text_input(
        "Aligned TextGrid folder (optional)", st.session_state.aligned_dir
    )
    st.session_state.speakers_path = c4.text_input(
        "Speaker demographics CSV (optional)", st.session_state.speakers_path
    )

    if st.button("🔍 Scan corpus", type="primary"):
        _scan_corpus()

    inv = st.session_state.inventory
    if inv is not None:
        st.subheader("What we found")
        cols = st.columns(4)
        s = inv.summary()
        cols[0].metric("Recordings", s["recordings"])
        cols[1].metric("Paired", s["paired"])
        cols[2].metric("Aligned", s["aligned"])
        cols[3].metric("Speakers", s["speakers"])
        if s["needs_alignment"]:
            st.info(f"{s['needs_alignment']} recording(s) still need force-alignment "
                    "→ go to **stage 2**.")
        elif s["aligned"]:
            st.success("Recordings are already force-aligned → skip to **stage 3**.")
        if inv.warnings:
            with st.expander(f"{len(inv.warnings)} warning(s)"):
                for w in inv.warnings:
                    st.write("• " + w)
        _preview_inventory(inv)

    existing = _existing_vowel_csvs()
    if existing:
        st.subheader("Existing extracted-vowel files")
        st.caption("Skip straight to analysis by loading one of these.")
        choice = st.selectbox("Vowel CSV", [str(p) for p in existing])
        if st.button("Load this vowel data"):
            _load_vowel_csv(Path(choice))


def _scan_corpus() -> None:
    audio = st.session_state.audio_dir.strip()
    if not audio:
        st.error("Enter an audio folder first.")
        return
    status = validate_location(audio)
    if not status.ok:
        st.error(f"Audio folder problem: {status.message}")
        return
    inv = discover_corpus(
        audio,
        transcript_dir=st.session_state.transcript_dir.strip() or None,
        aligned_dir=st.session_state.aligned_dir.strip() or None,
    )
    st.session_state.inventory = inv
    sp = st.session_state.speakers_path.strip()
    if sp:
        try:
            st.session_state.demographics = analysis.load_demographics(sp)
            st.toast(f"Loaded demographics for {len(st.session_state.demographics)} speakers.")
        except Exception as exc:  # noqa: BLE001
            st.warning(f"Could not read demographics CSV: {exc}")


def _existing_vowel_csvs() -> list[Path]:
    dirs = [d for d in (st.session_state.aligned_dir, st.session_state.transcript_dir,
                        st.session_state.audio_dir, st.session_state.output_dir) if d]
    return find_vowel_data(*dirs) if dirs else []


def _preview_inventory(inv) -> None:
    rows = [
        {
            "stem": i.stem, "speaker": i.speaker,
            "audio": i.audio.name if i.audio else "—",
            "transcript": i.transcript.name if i.transcript else (
                i.textgrid.name if i.textgrid else "—"),
            "aligned": "✓" if i.aligned else "",
        }
        for i in inv.items[:200]
    ]
    if rows:
        with st.expander("Recording list (first 200)"):
            st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)


def _load_vowel_csv(path: Path) -> None:
    res = extraction.load_existing_vowel_data(path)
    st.session_state.vowel_df = res.data
    st.session_state.schema = res.schema
    for note in res.notes:
        st.warning(note)
    st.success(f"Loaded {len(res.data):,} tokens from {path.name}. Go to **stage 4**.")


# --------------------------------------------------------------------------- #
# Stage 2 — Align
# --------------------------------------------------------------------------- #
def stage_align() -> None:
    st.header("2 · Force-align with MFA")
    mfa = alignment.mfa_status()
    inv = st.session_state.inventory
    if inv is None:
        st.info("Scan a corpus in **stage 1** first.")
        return
    if inv.fully_aligned:
        st.success("Every pairable recording already has a phone tier — no alignment "
                   "needed. Continue to **stage 3**.")
    if not mfa.available:
        st.warning("Montreal Forced Aligner was not detected on this machine.")
        st.code(mfa.install_hint, language="text")
        return

    st.write(f"MFA detected: `{mfa.version}`")
    c1, c2, c3 = st.columns(3)
    acoustic = c1.text_input("Acoustic model", "english_us_arpa")
    dictionary = c2.text_input("Dictionary", "english_us_arpa")
    num_jobs = c3.number_input("Parallel jobs", 1, 32, 3)
    out_dir = st.text_input(
        "Output folder for TextGrids",
        st.session_state.output_dir or str(Path(inv.audio_dir).parent / "vowelchemy_aligned"),
    )
    st.session_state.output_dir = out_dir

    cola, colb = st.columns(2)
    if cola.button("⬇️ Download MFA models"):
        with st.status("Downloading acoustic model + dictionary…", expanded=True) as s:
            log: list[str] = []
            alignment.download_models(acoustic, dictionary, on_output=lambda line: log.append(line))
            st.code("\n".join(log[-40:]) or "done", language="text")
            s.update(label="Models ready", state="complete")

    if colb.button("▶️ Run alignment", type="primary"):
        with st.status("Aligning… this can take a while for large corpora.",
                       expanded=True) as s:
            log: list[str] = []
            res = alignment.align_inventory(
                inv, out_dir, dictionary=dictionary, acoustic_model=acoustic,
                num_jobs=int(num_jobs), on_output=lambda line: log.append(line),
            )
            st.session_state.align_log = "\n".join(log)
            st.code("\n".join(log[-60:]), language="text")
            if res.ok:
                st.session_state.aligned_dir = str(res.output_dir)
                s.update(label=f"Aligned — {len(res.textgrids)} TextGrids", state="complete")
                st.success("Alignment complete. Continue to **stage 3**.")
                # refresh inventory so it now sees the alignments
                st.session_state.inventory = discover_corpus(
                    inv.audio_dir, transcript_dir=st.session_state.transcript_dir or None,
                    aligned_dir=str(res.output_dir),
                )
            else:
                s.update(label="Alignment failed", state="error")
                st.error("MFA did not produce TextGrids. See the log above.")


# --------------------------------------------------------------------------- #
# Stage 3 — Extract
# --------------------------------------------------------------------------- #
def stage_extract() -> None:
    st.header("3 · Extract vowels with new-fave")
    nf = extraction.newfave_status()
    inv = st.session_state.inventory

    existing = _existing_vowel_csvs()
    if existing:
        st.subheader("Existing vowel data")
        choice = st.selectbox("Load an existing CSV instead of re-extracting",
                              ["—"] + [str(p) for p in existing])
        if choice != "—" and st.button("Load selected CSV"):
            _load_vowel_csv(Path(choice))

    if not nf.available:
        st.warning("new-fave (`fave-extract`) was not detected.")
        st.code(nf.install_hint, language="text")
        return
    if inv is None:
        st.info("Scan a corpus in **stage 1** first (or load an existing CSV above).")
        return

    st.write(f"new-fave detected: `{nf.version}`")
    aligned_dir = st.text_input(
        "Aligned TextGrid folder", st.session_state.aligned_dir or st.session_state.output_dir
    )
    out_dir = st.text_input(
        "Output folder for vowel measurements",
        st.session_state.output_dir or str(Path(inv.audio_dir).parent / "vowelchemy_vowels"),
    )
    exclude = st.checkbox("Exclude overlapping speech", value=True)
    if st.button("▶️ Extract vowels", type="primary"):
        with st.status("Measuring vowels…", expanded=True) as s:
            log: list[str] = []
            res = extraction.extract_vowels(
                inv.audio_dir, aligned_dir, out_dir,
                speakers_file=st.session_state.speakers_path or None,
                exclude_overlaps=exclude, on_output=lambda line: log.append(line),
            )
            st.session_state.extract_log = "\n".join(log)
            st.code("\n".join(log[-60:]) or "(no output)", language="text")
            for note in res.notes:
                st.warning(note)
            if res.ok:
                st.session_state.vowel_df = res.data
                st.session_state.schema = res.schema
                s.update(label=f"Extracted {len(res.data):,} tokens", state="complete")
                st.success("Extraction complete. Continue to **stage 4**.")
            else:
                s.update(label="Extraction produced no usable data", state="error")


# --------------------------------------------------------------------------- #
# Stage 4 — Dataset
# --------------------------------------------------------------------------- #
def stage_dataset() -> None:
    st.header("4 · Build & download the dataset")
    if st.session_state.vowel_df is None:
        st.info("Load or extract vowel data first (stages 1–3), or click "
                "**Load demo dataset** in the sidebar.")
        return

    _schema_editor()
    _demographics_loader()
    _normalization_picker()

    df, schema, result = prepared_dataframe()
    if df is None:
        return
    if result and result.notes:
        with st.expander("Normalization notes"):
            for n in result.notes:
                st.write("• " + n)

    # Vowel selection
    st.subheader("Choose vowels & filters")
    vtable = analysis.list_vowels(df, schema)
    options = list(vtable["vowel"])
    labels = {row.vowel: f"{row.label}  (n={row.n})" for row in vtable.itertuples()}
    st.session_state.selected_vowels = st.multiselect(
        "Vowels to keep (blank = all)", options,
        default=st.session_state.selected_vowels,
        format_func=lambda v: labels.get(v, v),
    )

    group_cols = analysis.candidate_grouping_columns(df, schema)
    filter_cols = st.multiselect("Filter by columns", group_cols)
    filters: dict = {}
    for col in filter_cols:
        vals = sorted(df[col].dropna().astype(str).unique())
        chosen = st.multiselect(f"Keep {col}", vals, default=vals, key=f"filter_{col}")
        filters[col] = chosen
    st.session_state.filters = filters

    fdf, _, _ = filtered_dataframe()
    st.subheader("Result")
    st.write(f"**{len(fdf):,}** tokens × {fdf.shape[1]} columns")
    st.dataframe(fdf.head(300), width="stretch", hide_index=True)
    st.download_button(
        "⬇️ Download dataset as CSV",
        fdf.to_csv(index=False).encode("utf-8"),
        file_name="vowelchemy_dataset.csv",
        mime="text/csv",
        type="primary",
    )


def _schema_editor() -> None:
    df = st.session_state.vowel_df
    schema = st.session_state.schema or ColumnSchema.detect(df)
    with st.expander("Column mapping (auto-detected — edit if needed)"):
        cols = ["— none —"] + list(df.columns)
        overrides = {}
        grid = st.columns(3)
        fields = ["speaker", "vowel", "f1", "f2", "f3", "duration", "word", "stress"]
        for i, field_name in enumerate(fields):
            current = getattr(schema, field_name, None)
            idx = cols.index(current) if current in cols else 0
            sel = grid[i % 3].selectbox(field_name, cols, index=idx, key=f"schema_{field_name}")
            if sel != "— none —":
                overrides[field_name] = sel
        if st.button("Apply mapping"):
            st.session_state.schema = ColumnSchema.detect(df, overrides)
            st.session_state.schema_overrides = overrides
            st.toast("Schema updated.")
    if st.session_state.schema is None:
        st.session_state.schema = schema
    missing = st.session_state.schema.missing_required()
    if missing:
        st.error(f"Required columns not mapped: {missing}. Set them above.")


def _demographics_loader() -> None:
    if st.session_state.demographics is not None:
        return
    up = st.file_uploader("Optional: upload speaker demographics CSV (Sex, Age Group, …)",
                         type=["csv", "tsv"])
    if up is not None:
        st.session_state.demographics = pd.read_csv(up)
        st.toast(f"Loaded demographics for {len(st.session_state.demographics)} speakers.")
        st.rerun()


def _normalization_picker() -> None:
    methods = normalization.available_methods()
    keys = [m.key for m in methods]
    labels = {m.key: m.label for m in methods}
    descs = {m.key: m.description for m in methods}
    current = st.session_state.norm_method
    sel = st.selectbox(
        "Normalization method", keys,
        index=keys.index(current) if current in keys else 0,
        format_func=lambda k: labels[k],
    )
    st.caption(descs[sel])
    st.session_state.norm_method = sel


# --------------------------------------------------------------------------- #
# Stage 5 — Visualize
# --------------------------------------------------------------------------- #
def stage_visualize() -> None:
    st.header("5 · Visualize")
    fdf, schema, result = filtered_dataframe()
    if fdf is None or fdf.empty:
        st.info("Build a dataset in **stage 4** first.")
        return
    dark = _is_dark()
    group_cols = [c for c in analysis.candidate_grouping_columns(fdf, schema)
                  if c not in ("vowel_canon",)]
    norm_formants = [c for c in ("F1_norm", "F2_norm", "F3_norm") if c in fdf.columns]

    tab_cross, tab_space, tab_ridge = st.tabs(
        ["Cross (distribution)", "Vowel space", "Ridgeline"]
    )

    with tab_cross:
        st.caption("Distribution of a formant across a factor — e.g. BET/BEET F1 by Age Group.")
        c1, c2, c3, c4 = st.columns(4)
        formant = c1.selectbox("Formant", norm_formants or schema.formant_columns(), key="cross_f")
        xcol = c2.selectbox("X axis (group)", group_cols, key="cross_x")
        split_opts = ["vowel_label"] + [c for c in group_cols if c != xcol]
        split = c3.selectbox("Split / colour", split_opts, key="cross_split")
        kind = c4.selectbox("Style", ["violin", "box", "strip"], key="cross_kind")
        x_order = _natural_order(fdf, xcol)
        fig = viz.formant_cross(fdf, formant=formant, x=xcol, color=split, kind=kind,
                                dark=dark, x_order=x_order)
        st.plotly_chart(fig, width="stretch")

    with tab_space:
        st.caption("F2×F1 vowel space with 2-SD confidence ellipses and centroid labels.")
        c1, c2 = st.columns(2)
        color = c1.selectbox("Colour by", ["vowel_canon"] + group_cols, key="space_color")
        show_tokens = c2.checkbox("Show individual tokens", value=True)
        xdim = "F2_norm" if "F2_norm" in fdf.columns else schema.f2
        ydim = "F1_norm" if "F1_norm" in fdf.columns else schema.f1
        fig = viz.vowel_space(fdf, x=xdim, y=ydim, color=color,
                              show_tokens=show_tokens, dark=dark)
        st.plotly_chart(fig, width="stretch")

    with tab_ridge:
        st.caption("Density curves per group level — reveals modality and shift.")
        c1, c2 = st.columns(2)
        val = c1.selectbox("Formant", norm_formants or schema.formant_columns(), key="ridge_f")
        grp = c2.selectbox("Group", group_cols, key="ridge_g")
        fig = viz.ridgeline(fdf, value=val, group=grp, dark=dark,
                            group_order=_natural_order(fdf, grp))
        st.plotly_chart(fig, width="stretch")


def _natural_order(df: pd.DataFrame, col: str):
    """Order Age-Group-like columns sensibly; else sorted uniques."""
    known = ["Older", "Middle", "Young", "Old", "Adult", "Child",
             "Low", "Medium", "High"]
    vals = list(df[col].dropna().astype(str).unique())
    ordered = [k for k in known if k in vals] + [v for v in sorted(vals) if v not in known]
    return ordered


# --------------------------------------------------------------------------- #
# Stage 6 — Separation
# --------------------------------------------------------------------------- #
def stage_separation() -> None:
    st.header("6 · Separation metrics (phonJSD)")
    st.write(
        "Jensen-Shannon Divergence quantifies how distinguishable two vowels are "
        "in normalized formant space: **1 = fully separated, 0 = merged**. "
        "Pillai and Bhattacharyya overlap are shown alongside for triangulation."
    )
    fdf, schema, result = filtered_dataframe()
    if fdf is None or fdf.empty:
        st.info("Build a dataset in **stage 4** first.")
        return

    vtable = analysis.list_vowels(fdf, schema)
    options = list(vtable["vowel"])
    c1, c2, c3 = st.columns(3)
    chosen = c1.multiselect("Vowels to compare (blank = all)", options,
                           default=st.session_state.selected_vowels or options[:4],
                           format_func=vowel_display_label)
    group_cols = [None] + [c for c in analysis.candidate_grouping_columns(fdf, schema)
                           if c != "vowel_canon"]
    group_by = c2.selectbox("Compute within each level of", group_cols,
                           format_func=lambda c: c or "— whole dataset —")
    dims_opt = c3.selectbox("Space", ["F1 × F2", "F1 only", "F2 only"])
    dims = {"F1 × F2": None, "F1 only": ["F1_norm"], "F2 only": ["F2_norm"]}[dims_opt]

    pj = phonjsd.phonjsd_status()
    engines = (["phonJSD (R)", "Built-in (Python)"] if pj.available
               else ["Built-in (Python)"])
    engine = st.radio(
        "Engine", engines, horizontal=True,
        help="phonJSD (R) runs your lab's canonical package (compare_overlap_metrics); "
             "the built-in engine is a native KDE-based equivalent needing no R.",
    )
    if not pj.available:
        st.caption("Install R + phonJSD to run the canonical engine: "
                   "`remotes::install_github('berrygrant/phonJSD')`.")

    if st.button("Compute separation", type="primary"):
        # Always compute the built-in metrics (they drive the charts and work
        # everywhere); additionally call phonJSD when that engine is selected.
        sep = metrics.pairwise_separation(
            fdf, schema, vowels=chosen or None, group_by=group_by, dimensions=dims,
        )
        st.session_state["_sep"] = sep if not sep.empty else None
        st.session_state["_sep_phonjsd"] = None
        if sep.empty:
            st.warning("No vowel pairs met the minimum token threshold (5 per cell).")
        if engine.startswith("phonJSD"):
            feats = dims or [c for c in ("F1_norm", "F2_norm") if c in fdf.columns]
            subset = analysis.select_vowels(fdf, schema, chosen) if chosen else fdf
            with st.status("Running phonJSD (R)…", expanded=True) as s:
                log: list[str] = []
                res = phonjsd.compare_overlap_metrics(
                    subset, features=feats, category_col="vowel_canon",
                    group_col=group_by, on_output=lambda line: log.append(line),
                )
                st.code("\n".join(log[-40:]) or "(no output)", language="text")
                for n in res.notes:
                    st.warning(n)
                if res.ok:
                    st.session_state["_sep_phonjsd"] = res.data
                    s.update(label="phonJSD complete", state="complete")
                else:
                    s.update(label="phonJSD did not return results — see log", state="error")

    pjdata = st.session_state.get("_sep_phonjsd")
    if pjdata is not None:
        st.subheader("phonJSD results (canonical)")
        st.dataframe(pjdata, width="stretch", hide_index=True)
        st.download_button("⬇️ Download phonJSD metrics CSV",
                           pjdata.to_csv(index=False).encode("utf-8"),
                           file_name="vowelchemy_phonjsd.csv", mime="text/csv")

    sep = st.session_state.get("_sep")
    if sep is not None and not sep.empty:
        st.subheader("Built-in metrics" if pjdata is not None else "Results")
        show_cols = [c for c in ["group_value", "vowel_a_label", "vowel_b_label",
                                 "n_a", "n_b", "JSD", "Pillai", "Bhattacharyya_overlap"]
                     if c in sep.columns]
        st.dataframe(sep[show_cols], width="stretch", hide_index=True)
        st.download_button("⬇️ Download metrics CSV",
                          sep.to_csv(index=False).encode("utf-8"),
                          file_name="vowelchemy_separation.csv", mime="text/csv")

        dark = _is_dark()
        order = _natural_order(fdf, group_by) if group_by else None
        st.plotly_chart(viz.separation_bar(sep, group_order=order, dark=dark),
                       width="stretch")
        if group_by and sep["group_value"].notna().any():
            lvl = st.selectbox("Separation matrix for level", order or
                              sorted(sep["group_value"].dropna().unique()))
            st.plotly_chart(viz.separation_matrix(sep, group_value=lvl, dark=dark),
                           width="stretch")


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
_STAGE_FUNCS = {
    STAGES[0]: stage_corpus,
    STAGES[1]: stage_align,
    STAGES[2]: stage_extract,
    STAGES[3]: stage_dataset,
    STAGES[4]: stage_visualize,
    STAGES[5]: stage_separation,
}


def main() -> None:
    _init_state()
    sidebar()
    _STAGE_FUNCS[st.session_state.stage]()


main()
