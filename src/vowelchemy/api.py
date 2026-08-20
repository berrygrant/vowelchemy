"""FastAPI backend for the Vowelchemy React app.

This exposes the Vowelchemy *library* (corpus discovery, MFA/new-fave
orchestration, normalization, analysis, metrics, phontrast, visualization) over
a small JSON API that the React front-end drives.  All the real work lives in the
library modules; this file is glue plus a light per-session state store.

Charts are produced by :mod:`vowelchemy.visualization` (Plotly) on the server
and returned as Plotly JSON, so the front-end renders them with plotly.js
without re-implementing any chart logic.

Run with ``vowelchemy app`` (which launches uvicorn) or::

    uvicorn vowelchemy.api:app --reload
"""

from __future__ import annotations

import io
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import (
    alignment,
    analysis,
    extraction,
    metrics,
    normalization,
    phontrast,
    projects,
    sample_data,
    trajectories,
    visualization as viz,
)
from .constants import (
    ARPABET_VOWELS,
    DEFAULT_ACOUSTIC_MODEL,
    DEFAULT_DICTIONARY,
    canonical_vowel,
)
from .corpus import (
    discover_corpus,
    find_vowel_data,
    is_within_root,
    list_directory,
    suggest_corpus_layout,
    validate_location,
)
from .glossary import GLOSSARY, REFERENCES, jsd_verdict
from .jobs import JobManager
from .schema import ColumnSchema

app = FastAPI(title="Vowelchemy API", version="0.1.0")
JOBS = JobManager()

# Optional confinement root for the folder browser (local-tool security).
BROWSE_ROOT: Optional[str] = os.environ.get("VOWELCHEMY_BROWSE_ROOT") or None

# The app is a single-user local tool; allow the Vite dev server to call it.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------- #
# Per-session state
# --------------------------------------------------------------------------- #
@dataclass
class Session:
    audio_dir: str = ""
    transcript_dir: str = ""
    aligned_dir: str = ""
    output_dir: str = ""
    speakers_path: str = ""
    inventory: object = None
    vowel_df: Optional[pd.DataFrame] = None
    schema: Optional[ColumnSchema] = None
    demographics: Optional[pd.DataFrame] = None
    norm_method: str = "lobanov"
    norm_params: dict = field(default_factory=dict)
    remove_outliers: bool = False
    outlier_sd: float = 2.5
    vowel_label_map: Optional[dict] = None
    selected_vowels: list = field(default_factory=list)
    filters: dict = field(default_factory=dict)
    tracks_df: Optional[pd.DataFrame] = None
    tracks_schema: Optional[ColumnSchema] = None


_SESSIONS: dict[str, Session] = {}


def session_for(session_id: Optional[str]) -> Session:
    sid = session_id or "default"
    return _SESSIONS.setdefault(sid, Session())


# --------------------------------------------------------------------------- #
# Derived-data helpers (mirror the old Streamlit prepared/filtered views)
# --------------------------------------------------------------------------- #
def prepared(session: Session):
    if session.vowel_df is None or session.schema is None:
        return None, None, None
    out = session.vowel_df
    if session.demographics is not None:
        try:
            out = analysis.join_demographics(out, session.demographics, session.schema)
        except KeyError:
            pass
    out = analysis.add_vowel_labels(out, session.schema, label_map=session.vowel_label_map)
    if session.remove_outliers:
        flagged = analysis.flag_outliers(out, session.schema, n_sd=session.outlier_sd)
        out = flagged[~flagged["is_outlier"]].drop(columns=["is_outlier"])
    result = normalization.normalize(
        out, session.schema, session.norm_method, **(session.norm_params or {})
    )
    return result.data, session.schema, result


def filtered(session: Session):
    """The downloadable dataset: demographic filters + the vowel selection."""
    df, schema, result = explore_base(session)
    if df is None:
        return None, None, None
    if session.selected_vowels:
        df = analysis.select_vowels(df, schema, session.selected_vowels)
    return df, schema, result


def explore_base(session: Session):
    """Demographic-filtered data (all vowels) for the Visualize/Separation stages.

    Vowel selection there is per-stage, so it is *not* baked in here.
    """
    df, schema, result = prepared(session)
    if df is None:
        return None, None, None
    df = analysis.apply_filters(df, session.filters)
    return df, schema, result


def _require_explore(session: Session):
    df, schema, result = explore_base(session)
    if df is None or df.empty:
        raise HTTPException(status_code=400, detail="No vowel data loaded. Load or extract data first.")
    return df, schema, result


NATURAL_ORDER = ["Older", "Middle", "Young", "Old", "Adult", "Child", "Low", "Medium", "High"]


def natural_order(df: pd.DataFrame, col: Optional[str]):
    if not col or col not in df.columns:
        return None
    vals = list(df[col].dropna().astype(str).unique())
    return [k for k in NATURAL_ORDER if k in vals] + [v for v in sorted(vals) if v not in NATURAL_ORDER]


def df_payload(df: pd.DataFrame, limit: int = 500) -> dict:
    preview = df.head(limit)
    return {
        "columns": [str(c) for c in df.columns],
        "records": json.loads(preview.to_json(orient="records", date_format="iso")),
        "n_total": int(len(df)),
        "n_shown": int(len(preview)),
    }


def fig_json(fig) -> dict:
    return json.loads(fig.to_json())


# --------------------------------------------------------------------------- #
# Request models
# --------------------------------------------------------------------------- #
class ScanRequest(BaseModel):
    audio_dir: str
    transcript_dir: Optional[str] = None
    aligned_dir: Optional[str] = None
    speakers_path: Optional[str] = None


class ValidateRequest(BaseModel):
    path: str


class AutodetectRequest(BaseModel):
    root_dir: str


class LoadCsvRequest(BaseModel):
    csv_path: str


class AlignRequest(BaseModel):
    acoustic_model: str = DEFAULT_ACOUSTIC_MODEL
    dictionary: str = DEFAULT_DICTIONARY
    num_jobs: int = 3
    output_dir: Optional[str] = None
    download_models: bool = False


class ExtractRequest(BaseModel):
    aligned_dir: Optional[str] = None
    output_dir: Optional[str] = None
    exclude_overlaps: bool = True


class SchemaRequest(BaseModel):
    overrides: dict = {}


class NormalizationRequest(BaseModel):
    method: str
    g_value: Optional[float] = None
    corner_high: Optional[str] = None
    corner_low: Optional[str] = None


class DatasetRequest(BaseModel):
    selected_vowels: list[str] = []
    filters: dict[str, list] = {}
    remove_outliers: bool = False
    outlier_sd: float = 2.5


class FigureCrossRequest(BaseModel):
    formant: str = "F1_norm"
    x: str = "Age Group"
    split: Optional[str] = "vowel_label"
    kind: str = "violin"
    vowels: Optional[list[str]] = None
    dark: bool = False


class FigureSpaceRequest(BaseModel):
    color: str = "vowel_canon"
    show_tokens: bool = True
    vowels: Optional[list[str]] = None
    mode: str = "scatter"  # scatter | contour | ellipse
    max_points: int = 4000
    dark: bool = False


class FigureRidgeRequest(BaseModel):
    value: str = "F1_norm"
    group: str = "Age Group"
    vowels: Optional[list[str]] = None
    dark: bool = False


class SeparationRequest(BaseModel):
    vowels: list[str] = []
    group_by: Optional[str] = None
    dims: Optional[list[str]] = None
    engine: str = "builtin"  # "builtin" | "phontrast"
    bootstrap: int = 0  # >0 → JSD confidence intervals
    permutations: int = 0  # >0 → Pillai permutation p-value
    dark: bool = False


class TracksLoadRequest(BaseModel):
    csv_path: str


class TrajectoryFigureRequest(BaseModel):
    kind: str = "space"  # "space" | "time"
    value: str = "F1_norm"
    group_by: Optional[str] = None
    vowels: Optional[list[str]] = None
    n_steps: int = 10
    dark: bool = False


class RecipeRequest(BaseModel):
    recipe: dict


class ProjectRequest(BaseModel):
    name: str


# --------------------------------------------------------------------------- #
# Status
# --------------------------------------------------------------------------- #
@app.get("/api/status")
def status(x_vowelchemy_session: Optional[str] = Header(default=None)):
    s = session_for(x_vowelchemy_session)
    mfa = alignment.mfa_status()
    nf = extraction.newfave_status()
    pj = phontrast.phontrast_status()
    return {
        "tools": {
            "mfa": {"available": mfa.available, "version": mfa.version, "hint": mfa.install_hint},
            "newfave": {"available": nf.available, "version": nf.version, "hint": nf.install_hint},
            "phontrast": {"available": pj.available, "version": pj.version, "hint": pj.install_hint},
        },
        "data": {
            "loaded": s.vowel_df is not None,
            "n_tokens": int(len(s.vowel_df)) if s.vowel_df is not None else 0,
            "n_speakers": int(len(s.demographics)) if s.demographics is not None else 0,
            "norm_method": s.norm_method,
            "schema": s.schema.as_dict() if s.schema else {},
            "tracks_loaded": s.tracks_df is not None,
            "remove_outliers": s.remove_outliers,
        },
        "browse_confined": BROWSE_ROOT is not None,
    }


# --------------------------------------------------------------------------- #
# Corpus
# --------------------------------------------------------------------------- #
@app.post("/api/corpus/validate")
def corpus_validate(req: ValidateRequest):
    st = validate_location(req.path)
    return {"ok": st.ok, "message": st.message}


@app.post("/api/corpus/scan")
def corpus_scan(req: ScanRequest, x_vowelchemy_session: Optional[str] = Header(default=None)):
    s = session_for(x_vowelchemy_session)
    st = validate_location(req.audio_dir)
    if not st.ok:
        raise HTTPException(status_code=400, detail=f"Audio folder problem: {st.message}")
    inv = discover_corpus(req.audio_dir, transcript_dir=req.transcript_dir or None,
                          aligned_dir=req.aligned_dir or None)
    s.audio_dir = req.audio_dir
    s.transcript_dir = req.transcript_dir or ""
    s.aligned_dir = req.aligned_dir or ""
    s.inventory = inv
    if req.speakers_path:
        try:
            s.demographics = analysis.load_demographics(req.speakers_path)
            s.speakers_path = req.speakers_path
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=f"Could not read demographics: {exc}")
    items = [
        {
            "stem": i.stem, "speaker": i.speaker,
            "audio": i.audio.name if i.audio else None,
            "transcript": (i.transcript.name if i.transcript else
                           (i.textgrid.name if i.textgrid else None)),
            "aligned": i.aligned,
        }
        for i in inv.items[:500]
    ]
    dirs = [d for d in (s.aligned_dir, s.transcript_dir, s.audio_dir, s.output_dir) if d]
    existing = [str(p) for p in (find_vowel_data(*dirs) if dirs else [])]
    return {
        "summary": inv.summary(),
        "fully_aligned": inv.fully_aligned,
        "warnings": inv.warnings,
        "items": items,
        "existing_vowel_csvs": existing,
    }


@app.post("/api/corpus/autodetect")
def corpus_autodetect(req: AutodetectRequest):
    """Given a root directory, fuzzy-detect the audio/transcript/aligned folders."""
    if not is_within_root(req.root_dir, BROWSE_ROOT):
        raise HTTPException(status_code=403, detail="Path is outside the allowed root.")
    st = validate_location(req.root_dir)
    if not st.ok:
        raise HTTPException(status_code=400, detail=f"Root folder problem: {st.message}")
    return suggest_corpus_layout(req.root_dir).to_dict()


@app.get("/api/browse")
def browse(path: Optional[str] = None, exts: Optional[str] = None):
    """List sub-directories (and optional files) for the folder picker."""
    ext_list = [e for e in exts.split(",") if e] if exts else None
    try:
        return list_directory(path, exts=ext_list, root=BROWSE_ROOT)
    except (NotADirectoryError, FileNotFoundError, PermissionError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# --------------------------------------------------------------------------- #
# Data loading
# --------------------------------------------------------------------------- #
def _set_vowel_data(s: Session, df: pd.DataFrame, schema: Optional[ColumnSchema] = None):
    s.vowel_df = df
    s.schema = schema or ColumnSchema.detect(df)
    s.selected_vowels = []
    s.filters = {}


@app.post("/api/demo")
def load_demo(x_vowelchemy_session: Optional[str] = Header(default=None)):
    s = session_for(x_vowelchemy_session)
    tokens, speakers = sample_data.make_demo_dataset()
    _set_vowel_data(s, tokens)
    s.demographics = speakers
    return {"n_tokens": int(len(tokens)), "n_speakers": int(len(speakers)),
            "schema": s.schema.as_dict()}


@app.post("/api/voweldata/load")
def load_voweldata(req: LoadCsvRequest, x_vowelchemy_session: Optional[str] = Header(default=None)):
    s = session_for(x_vowelchemy_session)
    try:
        res = extraction.load_existing_vowel_data(req.csv_path)
    except (OSError, pd.errors.ParserError) as exc:
        raise HTTPException(status_code=400, detail=f"Could not read vowel CSV: {exc}")
    _set_vowel_data(s, res.data, res.schema)
    return {"n_tokens": int(len(res.data)), "schema": s.schema.as_dict(), "notes": res.notes}


@app.post("/api/voweldata/upload")
async def upload_voweldata(file: UploadFile = File(...),
                           x_vowelchemy_session: Optional[str] = Header(default=None)):
    s = session_for(x_vowelchemy_session)
    raw = await file.read()
    df = pd.read_csv(io.BytesIO(raw), sep=None, engine="python")  # sniff , vs tab
    _set_vowel_data(s, df)
    return {"n_tokens": int(len(df)), "schema": s.schema.as_dict()}


@app.post("/api/demographics/upload")
async def upload_demographics(file: UploadFile = File(...),
                              x_vowelchemy_session: Optional[str] = Header(default=None)):
    s = session_for(x_vowelchemy_session)
    raw = await file.read()
    s.demographics = pd.read_csv(io.BytesIO(raw), sep=None, engine="python")
    return {"n_speakers": int(len(s.demographics)),
            "columns": [str(c) for c in s.demographics.columns]}


# --------------------------------------------------------------------------- #
# Alignment / extraction (run on a worker thread; poll /api/jobs/{id})
# --------------------------------------------------------------------------- #
@app.post("/api/align")
def align(req: AlignRequest, x_vowelchemy_session: Optional[str] = Header(default=None)):
    s = session_for(x_vowelchemy_session)
    if s.inventory is None:
        raise HTTPException(status_code=400, detail="Scan a corpus first.")
    if not alignment.mfa_status().available:
        raise HTTPException(status_code=400, detail="MFA not detected. " + alignment.MFA_INSTALL_HINT)
    out_dir = req.output_dir or str(Path(s.inventory.audio_dir).parent / "vowelchemy_aligned")

    def target(emit):
        if req.download_models:
            alignment.download_models(req.acoustic_model, req.dictionary, on_output=emit)
        res = alignment.align_inventory(
            s.inventory, out_dir, dictionary=req.dictionary, acoustic_model=req.acoustic_model,
            num_jobs=req.num_jobs, on_output=emit,
        )
        if res.ok:
            s.aligned_dir = str(res.output_dir)
            s.output_dir = out_dir
            s.inventory = discover_corpus(s.inventory.audio_dir,
                                          transcript_dir=s.transcript_dir or None,
                                          aligned_dir=str(res.output_dir))
        return {"ok": res.ok, "n_textgrids": len(res.textgrids), "aligned_dir": str(res.output_dir)}

    return {"job_id": JOBS.start("align", target).id}


@app.post("/api/extract")
def extract(req: ExtractRequest, x_vowelchemy_session: Optional[str] = Header(default=None)):
    s = session_for(x_vowelchemy_session)
    if s.inventory is None:
        raise HTTPException(status_code=400, detail="Scan a corpus first.")
    if not extraction.newfave_status().available:
        raise HTTPException(status_code=400, detail="new-fave not detected. " + extraction.NEWFAVE_INSTALL_HINT)
    aligned_dir = req.aligned_dir or s.aligned_dir or s.output_dir
    out_dir = req.output_dir or str(Path(s.inventory.audio_dir).parent / "vowelchemy_vowels")

    def target(emit):
        res = extraction.extract_vowels(
            s.inventory.audio_dir, aligned_dir, out_dir,
            speakers_file=s.speakers_path or None, exclude_overlaps=req.exclude_overlaps,
            on_output=emit,
        )
        if res.ok:
            _set_vowel_data(s, res.data, res.schema)
        return {"ok": res.ok,
                "n_tokens": int(len(res.data)) if res.data is not None else 0,
                "csv_path": str(res.csv_path) if res.csv_path else None, "notes": res.notes}

    return {"job_id": JOBS.start("extract", target).id}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    snap = JOBS.snapshot(job_id)
    if snap is None:
        raise HTTPException(status_code=404, detail="Unknown job id.")
    return snap


# --------------------------------------------------------------------------- #
# Dataset build
# --------------------------------------------------------------------------- #
@app.get("/api/normalization/methods")
def norm_methods():
    return [{"key": m.key, "label": m.label, "description": m.description, "units": m.units}
            for m in normalization.available_methods()]


@app.post("/api/normalization")
def set_normalization(req: NormalizationRequest, x_vowelchemy_session: Optional[str] = Header(default=None)):
    s = session_for(x_vowelchemy_session)
    if req.method not in {m.key for m in normalization.available_methods()}:
        raise HTTPException(status_code=400, detail=f"Unknown method '{req.method}'.")
    s.norm_method = req.method
    params: dict = {}
    if req.g_value is not None:
        params["g_value"] = req.g_value
    if req.corner_high:
        params["corner_high"] = req.corner_high
    if req.corner_low:
        params["corner_low"] = req.corner_low
    s.norm_params = params
    _, _, result = prepared(s)
    return {"method": req.method, "params": params,
            "units": result.units if result else "",
            "notes": result.notes if result else []}


@app.get("/api/schema")
def get_schema(x_vowelchemy_session: Optional[str] = Header(default=None)):
    s = session_for(x_vowelchemy_session)
    if s.vowel_df is None:
        raise HTTPException(status_code=400, detail="No data loaded.")
    return {"schema": s.schema.as_dict(),
            "columns": [str(c) for c in s.vowel_df.columns],
            "missing_required": s.schema.missing_required()}


@app.post("/api/schema")
def set_schema(req: SchemaRequest, x_vowelchemy_session: Optional[str] = Header(default=None)):
    s = session_for(x_vowelchemy_session)
    if s.vowel_df is None:
        raise HTTPException(status_code=400, detail="No data loaded.")
    s.schema = ColumnSchema.detect(s.vowel_df, req.overrides)
    return {"schema": s.schema.as_dict(), "missing_required": s.schema.missing_required()}


@app.get("/api/vowels")
def list_vowels(x_vowelchemy_session: Optional[str] = Header(default=None)):
    s = session_for(x_vowelchemy_session)
    df, schema, _ = prepared(s)
    if df is None:
        raise HTTPException(status_code=400, detail="No data loaded.")
    vt = analysis.list_vowels(df, schema)
    out = []
    for r in vt.itertuples():
        lexset, keyword = ARPABET_VOWELS.get(r.vowel, ("", ""))
        out.append({"vowel": r.vowel, "label": r.label, "keyword": keyword or r.vowel,
                    "lexset": lexset, "n": int(r.n)})
    return out


@app.get("/api/grouping-columns")
def grouping_columns(x_vowelchemy_session: Optional[str] = Header(default=None)):
    s = session_for(x_vowelchemy_session)
    df, schema, _ = prepared(s)
    if df is None:
        raise HTTPException(status_code=400, detail="No data loaded.")
    cols = analysis.candidate_grouping_columns(df, schema)
    values = {c: sorted(df[c].dropna().astype(str).unique().tolist())[:50] for c in cols}
    # Phonetic-context columns (detected via the schema) so the UI can rank
    # sociodemographic factors above pre/fol segment when picking defaults.
    context = [c for c in (schema.preseg, schema.folseg, schema.stress, schema.word) if c]
    return {"columns": cols, "values": values, "context_columns": context,
            "norm_formants": [c for c in ("F1_norm", "F2_norm", "F3_norm") if c in df.columns]}


@app.post("/api/dataset")
def build_dataset(req: DatasetRequest, x_vowelchemy_session: Optional[str] = Header(default=None)):
    s = session_for(x_vowelchemy_session)
    s.selected_vowels = req.selected_vowels
    s.filters = req.filters
    s.remove_outliers = req.remove_outliers
    s.outlier_sd = req.outlier_sd
    df, _, result = filtered(s)
    if df is None:
        raise HTTPException(status_code=400, detail="No data loaded.")
    payload = df_payload(df)
    payload["norm_notes"] = result.notes if result else []
    return payload


@app.get("/api/dataset/csv")
def dataset_csv(x_vowelchemy_session: Optional[str] = Header(default=None)):
    s = session_for(x_vowelchemy_session)
    df, _, _ = filtered(s)
    if df is None:
        raise HTTPException(status_code=400, detail="No data loaded.")
    return Response(
        content=df.to_csv(index=False),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=vowelchemy_dataset.csv"},
    )


# --------------------------------------------------------------------------- #
# Figures (Plotly JSON)
# --------------------------------------------------------------------------- #
def _apply_vowels(df, schema, vowels):
    if vowels:
        return analysis.select_vowels(df, schema, vowels)
    return df


@app.post("/api/figure/vowel-space")
def figure_vowel_space(req: FigureSpaceRequest, x_vowelchemy_session: Optional[str] = Header(default=None)):
    df, schema, _ = _require_explore(session_for(x_vowelchemy_session))
    df = _apply_vowels(df, schema, req.vowels)
    x = "F2_norm" if "F2_norm" in df.columns else schema.f2
    y = "F1_norm" if "F1_norm" in df.columns else schema.f1
    fig = viz.vowel_space(df, x=x, y=y, color=req.color, show_tokens=req.show_tokens,
                          mode=req.mode, max_points=req.max_points, dark=req.dark)
    return fig_json(fig)


@app.post("/api/figure/cross")
def figure_cross(req: FigureCrossRequest, x_vowelchemy_session: Optional[str] = Header(default=None)):
    df, schema, _ = _require_explore(session_for(x_vowelchemy_session))
    df = _apply_vowels(df, schema, req.vowels)
    fig = viz.formant_cross(df, formant=req.formant, x=req.x, color=req.split, kind=req.kind,
                            dark=req.dark, x_order=natural_order(df, req.x))
    return fig_json(fig)


@app.post("/api/figure/ridgeline")
def figure_ridgeline(req: FigureRidgeRequest, x_vowelchemy_session: Optional[str] = Header(default=None)):
    df, schema, _ = _require_explore(session_for(x_vowelchemy_session))
    df = _apply_vowels(df, schema, req.vowels)
    fig = viz.ridgeline(df, value=req.value, group=req.group, dark=req.dark,
                        group_order=natural_order(df, req.group))
    return fig_json(fig)


# --------------------------------------------------------------------------- #
# Separation
# --------------------------------------------------------------------------- #
@app.post("/api/separation")
def separation(req: SeparationRequest, x_vowelchemy_session: Optional[str] = Header(default=None)):
    df, schema, _ = _require_explore(session_for(x_vowelchemy_session))
    sep = metrics.pairwise_separation(df, schema, vowels=req.vowels or None,
                                      group_by=req.group_by, dimensions=req.dims,
                                      bootstrap=req.bootstrap, permutations=req.permutations)
    out: dict = {"builtin": None, "figure_bar": None, "figure_matrix": None, "phontrast": None}
    if not sep.empty:
        sep = sep.copy()
        sep["verdict"] = sep["JSD"].map(jsd_verdict)
        show = [c for c in ["group_value", "vowel_a_label", "vowel_b_label", "n_a", "n_b",
                            "JSD", "JSD_lo", "JSD_hi", "Pillai", "Pillai_p",
                            "Bhattacharyya_overlap", "verdict"]
                if c in sep.columns and sep[c].notna().any()]
        out["builtin"] = df_payload(sep[show], limit=1000)
        order = natural_order(df, req.group_by)
        out["figure_bar"] = fig_json(viz.separation_bar(sep, group_order=order, dark=req.dark))
        if req.group_by and sep["group_value"].notna().any():
            lvl = (order or sorted(sep["group_value"].dropna().unique()))[0]
            out["figure_matrix"] = fig_json(viz.separation_matrix(sep, group_value=lvl, dark=req.dark))
        out["full_csv"] = sep.to_csv(index=False)

    if req.engine == "phontrast":
        pj = phontrast.phontrast_status()
        if not pj.available:
            out["phontrast"] = {"error": "phontrast/R not available. " + phontrast.PHONTRAST_INSTALL_HINT}
        else:
            feats = req.dims or [c for c in ("F1_norm", "F2_norm") if c in df.columns]
            subset = analysis.select_vowels(df, schema, req.vowels) if req.vowels else df
            log: list[str] = []
            res = phontrast.compare_overlap_metrics(subset, features=feats,
                                                  category_col="vowel_canon",
                                                  group_col=req.group_by, on_output=log.append)
            out["phontrast"] = {
                "ok": res.ok, "log": "\n".join(log), "notes": res.notes,
                "table": df_payload(res.data, limit=1000) if res.data is not None else None,
            }
    return out


@app.get("/api/separation/csv")
def separation_csv(x_vowelchemy_session: Optional[str] = Header(default=None)):
    s = session_for(x_vowelchemy_session)
    df, schema, _ = _require_explore(s)
    sep = metrics.pairwise_separation(df, schema, vowels=s.selected_vowels or None)
    return Response(content=sep.to_csv(index=False), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=vowelchemy_separation.csv"})


# --------------------------------------------------------------------------- #
# Reproducible analysis recipe (R1)
# --------------------------------------------------------------------------- #
def build_recipe(s: Session) -> dict:
    return {
        "version": 1,
        "corpus": {"audio_dir": s.audio_dir, "transcript_dir": s.transcript_dir,
                   "aligned_dir": s.aligned_dir, "speakers_path": s.speakers_path},
        "normalization": {"method": s.norm_method, "params": s.norm_params},
        "outliers": {"remove": s.remove_outliers, "sd": s.outlier_sd},
        "selected_vowels": s.selected_vowels,
        "filters": s.filters,
        "vowel_label_map": s.vowel_label_map,
    }


def apply_recipe(s: Session, r: dict) -> None:
    c = r.get("corpus", {})
    s.audio_dir = c.get("audio_dir", s.audio_dir) or ""
    s.transcript_dir = c.get("transcript_dir", s.transcript_dir) or ""
    s.aligned_dir = c.get("aligned_dir", s.aligned_dir) or ""
    s.speakers_path = c.get("speakers_path", s.speakers_path) or ""
    n = r.get("normalization", {})
    if n.get("method"):
        s.norm_method = n["method"]
    s.norm_params = n.get("params") or {}
    o = r.get("outliers", {})
    s.remove_outliers = bool(o.get("remove", s.remove_outliers))
    s.outlier_sd = float(o.get("sd", s.outlier_sd))
    s.selected_vowels = r.get("selected_vowels", s.selected_vowels)
    s.filters = r.get("filters", s.filters)
    s.vowel_label_map = r.get("vowel_label_map", s.vowel_label_map)


@app.get("/api/recipe")
def get_recipe(x_vowelchemy_session: Optional[str] = Header(default=None)):
    return build_recipe(session_for(x_vowelchemy_session))


@app.post("/api/recipe")
def post_recipe(req: RecipeRequest, x_vowelchemy_session: Optional[str] = Header(default=None)):
    s = session_for(x_vowelchemy_session)
    apply_recipe(s, req.recipe or {})
    return {"applied": True, "recipe": build_recipe(s)}


# --------------------------------------------------------------------------- #
# Custom vowel-label map (R6) and glossary (U2)
# --------------------------------------------------------------------------- #
@app.post("/api/vowelmap/upload")
async def upload_vowelmap(file: UploadFile = File(...),
                          x_vowelchemy_session: Optional[str] = Header(default=None)):
    s = session_for(x_vowelchemy_session)
    m = pd.read_csv(io.BytesIO(await file.read()), sep=None, engine="python")
    if m.shape[1] < 2:
        raise HTTPException(status_code=400, detail="Vowel map needs two columns: code,label.")
    code_col, label_col = m.columns[0], m.columns[1]
    s.vowel_label_map = {canonical_vowel(str(k)): str(v) for k, v in zip(m[code_col], m[label_col])}
    return {"n": len(s.vowel_label_map)}


@app.get("/api/glossary")
def glossary():
    return {"terms": GLOSSARY, "references": REFERENCES}


# --------------------------------------------------------------------------- #
# Persistent named projects (R10)
# --------------------------------------------------------------------------- #
@app.get("/api/projects")
def api_list_projects():
    return {"projects": projects.list_projects()}


@app.post("/api/projects/save")
def api_save_project(req: ProjectRequest, x_vowelchemy_session: Optional[str] = Header(default=None)):
    s = session_for(x_vowelchemy_session)
    path = projects.save_project(req.name, build_recipe(s), s.vowel_df, s.demographics, s.tracks_df)
    return {"saved": str(path), "projects": projects.list_projects()}


@app.post("/api/projects/load")
def api_load_project(req: ProjectRequest, x_vowelchemy_session: Optional[str] = Header(default=None)):
    s = session_for(x_vowelchemy_session)
    try:
        data = projects.load_project(req.name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    if data["vowel_df"] is not None:
        s.vowel_df = data["vowel_df"]
        s.schema = ColumnSchema.detect(data["vowel_df"])
    if data["demographics"] is not None:
        s.demographics = data["demographics"]
    if data["tracks_df"] is not None:
        s.tracks_df = data["tracks_df"]
        s.tracks_schema = ColumnSchema.detect(data["tracks_df"])
    apply_recipe(s, data["recipe"])  # applied last so vowels/filters/norm win
    return {"loaded": req.name, "recipe": build_recipe(s),
            "n_tokens": int(len(s.vowel_df)) if s.vowel_df is not None else 0}


# --------------------------------------------------------------------------- #
# Formant trajectories (R4)
# --------------------------------------------------------------------------- #
def tracks_prepared(s: Session):
    if s.tracks_df is None or s.tracks_schema is None:
        return None, None
    out = s.tracks_df
    if s.demographics is not None:
        try:
            out = analysis.join_demographics(out, s.demographics, s.tracks_schema)
        except KeyError:
            pass
    out = analysis.add_vowel_labels(out, s.tracks_schema, label_map=s.vowel_label_map)
    out = normalization.normalize(out, s.tracks_schema, s.norm_method, **(s.norm_params or {})).data
    return out, s.tracks_schema


@app.post("/api/tracks/demo")
def load_tracks_demo(x_vowelchemy_session: Optional[str] = Header(default=None)):
    s = session_for(x_vowelchemy_session)
    tracks, speakers = sample_data.make_demo_tracks()
    s.tracks_df = tracks
    s.tracks_schema = ColumnSchema.detect(tracks)
    if s.demographics is None:
        s.demographics = speakers
    return {"n_rows": int(len(tracks)),
            "n_tokens": int(tracks[s.tracks_schema.token_id].nunique())}


@app.post("/api/tracks/load")
def load_tracks(req: TracksLoadRequest, x_vowelchemy_session: Optional[str] = Header(default=None)):
    s = session_for(x_vowelchemy_session)
    try:
        df = analysis.read_table(Path(req.csv_path).expanduser())
    except (OSError, pd.errors.ParserError) as exc:
        raise HTTPException(status_code=400, detail=f"Could not read tracks CSV: {exc}")
    schema = ColumnSchema.detect(df)
    if not trajectories.is_trajectory_data(df, schema):
        raise HTTPException(
            status_code=400,
            detail="That CSV doesn't look like formant tracks — it needs a token-id column "
                   "and a time column with multiple rows per token.",
        )
    s.tracks_df = df
    s.tracks_schema = schema
    return {"n_rows": int(len(df)), "n_tokens": int(df[schema.token_id].nunique())}


@app.get("/api/tracks/vowels")
def tracks_vowels(x_vowelchemy_session: Optional[str] = Header(default=None)):
    s = session_for(x_vowelchemy_session)
    if s.tracks_df is None or s.tracks_schema is None:
        return []
    vcol = s.tracks_schema.require("vowel")
    canon = s.tracks_df[vcol].map(canonical_vowel)
    out = []
    for v, n in canon.value_counts().items():
        _lex, kw = ARPABET_VOWELS.get(v, ("", ""))
        out.append({"vowel": v, "keyword": kw or v, "n": int(n)})
    return out


@app.post("/api/figure/trajectory")
def figure_trajectory(req: TrajectoryFigureRequest, x_vowelchemy_session: Optional[str] = Header(default=None)):
    s = session_for(x_vowelchemy_session)
    df, schema = tracks_prepared(s)
    if df is None:
        raise HTTPException(status_code=400, detail="No trajectory (tracks) data loaded.")
    track = trajectories.TrackSchema.detect(df, schema)
    if track is None:
        raise HTTPException(status_code=400, detail="Loaded data has no usable token/time columns.")
    if req.vowels:
        df = analysis.select_vowels(df, schema, req.vowels)
    f1 = "F1_norm" if "F1_norm" in df.columns else schema.require("f1")
    f2 = "F2_norm" if "F2_norm" in df.columns else schema.require("f2")
    mean_df = trajectories.mean_trajectories(
        df, schema, track, group_by=req.group_by, n_steps=req.n_steps, formants=[f1, f2]
    )
    if req.kind == "time":
        val = req.value if req.value in mean_df.columns else f1
        fig = viz.trajectory_time(mean_df, value=val, dark=req.dark)
    else:
        fig = viz.trajectory_space(mean_df, f1=f1, f2=f2, dark=req.dark)
    return fig_json(fig)


@app.get("/api/health")
def health():
    return {"status": "ok"}


# --------------------------------------------------------------------------- #
# Serve the built React front-end (frontend/dist) when present. This mount must
# be registered LAST so it only catches paths the API routes did not handle.
# --------------------------------------------------------------------------- #
def _mount_frontend() -> None:
    from . import webui_dir

    ui = webui_dir()
    if ui is not None:
        app.mount("/", StaticFiles(directory=str(ui), html=True), name="frontend")


_mount_frontend()
