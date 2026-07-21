"""Interactive Plotly figures for vowel data.

The house style favours **distribution-revealing** forms over
means-only summaries, because the interesting sociolinguistic facts live in the
spread and shape of the data:

* :func:`vowel_space` — the canonical F2×F1 vowel plot with per-category
  confidence ellipses and direct centroid labels (identity by position+label,
  not colour alone).
* :func:`formant_cross` — the "cross" builder (e.g. *BET/BEET F1 by Age Group*):
  grouped violins with an inner box and the raw jittered tokens.
* :func:`ridgeline` — stacked density curves to compare a formant's
  distribution across the levels of one factor.
* :func:`separation_bar` / :func:`separation_matrix` — visualise JSD separation
  across groups or as a vowel×vowel matrix.

Colours come from the data-viz reference palette (validated colourblind-safe).
This module never imports Streamlit, so the figures are reusable from notebooks.
"""

from __future__ import annotations

from typing import Optional, Sequence

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from .constants import ARPABET_VOWELS, vowel_display_label

# Validated colourblind-safe categorical palette (data-viz reference instance).
CATEGORICAL_LIGHT = [
    "#2a78d6", "#eb6834", "#1baf7a", "#eda100",
    "#e87ba4", "#008300", "#4a3aa7", "#e34948",
]
CATEGORICAL_DARK = [
    "#3987e5", "#d95926", "#199e70", "#c98500",
    "#d55181", "#008300", "#9085e9", "#e66767",
]
_INK = {"light": "#0b0b0b", "dark": "#ffffff"}
_MUTED = "#898781"
_GRID = {"light": "#e1e0d9", "dark": "#2c2c2a"}
_SURFACE = {"light": "#fcfcfb", "dark": "#1a1a19"}
# Single-hue blue sequential ramp (data-viz reference) for ordered levels.
_BLUE_SEQUENTIAL = [
    "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b",
]

# Canonical left→right / high→low order so a vowel keeps its colour regardless
# of which subset is plotted ("colour follows the entity, never its rank").
_VOWEL_ORDER = list(ARPABET_VOWELS.keys())


def _mode(dark: bool) -> str:
    return "dark" if dark else "light"


def palette(dark: bool = False) -> list[str]:
    return CATEGORICAL_DARK if dark else CATEGORICAL_LIGHT


def stable_color_map(
    categories: Sequence[str],
    dark: bool = False,
    order: Optional[Sequence[str]] = None,
) -> dict[str, str]:
    """Assign each category a fixed palette colour by position in ``order``.

    Using a fixed reference order (not appearance order) keeps a category's
    colour stable when filters change which categories are on screen.
    """
    colours = palette(dark)
    ref = list(order) if order else sorted({str(c) for c in categories})
    mapping: dict[str, str] = {}
    for cat in categories:
        key = str(cat)
        idx = ref.index(key) if key in ref else len(mapping)
        mapping[key] = colours[idx % len(colours)]
    return mapping


def _apply_theme(fig: go.Figure, dark: bool, height: int = 520) -> go.Figure:
    mode = _mode(dark)
    fig.update_layout(
        template="plotly_dark" if dark else "plotly_white",
        paper_bgcolor=_SURFACE[mode],
        plot_bgcolor=_SURFACE[mode],
        font=dict(
            family='system-ui, -apple-system, "Segoe UI", sans-serif',
            color=_INK[mode],
            size=13,
        ),
        height=height,
        margin=dict(l=60, r=30, t=60, b=55),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
    )
    fig.update_xaxes(gridcolor=_GRID[mode], zeroline=False)
    fig.update_yaxes(gridcolor=_GRID[mode], zeroline=False)
    return fig


# --------------------------------------------------------------------------- #
# Confidence ellipse
# --------------------------------------------------------------------------- #
def confidence_ellipse(
    x: np.ndarray, y: np.ndarray, n_std: float = 2.0, n_points: int = 72
) -> Optional[tuple[np.ndarray, np.ndarray]]:
    """Return (xs, ys) tracing an ``n_std`` covariance ellipse, or None."""
    pts = np.column_stack([np.asarray(x, float), np.asarray(y, float)])
    pts = pts[~np.isnan(pts).any(axis=1)]
    if len(pts) < 3:
        return None
    mu = pts.mean(axis=0)
    cov = np.cov(pts.T)
    vals, vecs = np.linalg.eigh(cov)
    order = vals.argsort()[::-1]
    vals, vecs = np.clip(vals[order], 0, None), vecs[:, order]
    theta = np.linspace(0, 2 * np.pi, n_points)
    circle = np.column_stack([np.cos(theta), np.sin(theta)])
    transform = vecs @ np.diag(np.sqrt(vals) * n_std)
    ellipse = circle @ transform.T + mu
    return ellipse[:, 0], ellipse[:, 1]


# --------------------------------------------------------------------------- #
# Vowel space
# --------------------------------------------------------------------------- #
def vowel_space(
    df: pd.DataFrame,
    x: str = "F2_norm",
    y: str = "F1_norm",
    color: str = "vowel_canon",
    label_by: str = "vowel_canon",
    show_tokens: bool = True,
    ellipses: bool = True,
    n_std: float = 2.0,
    dark: bool = False,
    title: Optional[str] = None,
    category_order: Optional[Sequence[str]] = None,
) -> go.Figure:
    """Canonical vowel plot: F2 on x (reversed), F1 on y (reversed).

    Tokens are drawn faintly; each category gets a covariance ellipse and a
    bold centroid label so identity reads from position + label, with colour as
    a supporting cue.
    """
    fig = go.Figure()
    cats = list(dict.fromkeys(df[color].dropna().astype(str)))
    order = category_order or (
        [v for v in _VOWEL_ORDER if v in cats] + [c for c in cats if c not in _VOWEL_ORDER]
        if color in ("vowel_canon", "vowel")
        else sorted(cats)
    )
    cmap = stable_color_map(cats, dark=dark, order=order)

    for cat in order:
        sub = df[df[color].astype(str) == cat]
        if sub.empty:
            continue
        col = cmap[cat]
        label = (
            vowel_display_label(cat).split(" ")[0]
            if color in ("vowel_canon", "vowel")
            else cat
        )
        if show_tokens:
            fig.add_trace(
                go.Scattergl(
                    x=sub[x], y=sub[y], mode="markers",
                    marker=dict(size=5, color=col, opacity=0.28,
                                line=dict(width=0)),
                    name=str(cat), legendgroup=str(cat),
                    hovertemplate=f"{label}<br>{x}: %{{x:.3f}}<br>{y}: %{{y:.3f}}<extra></extra>",
                )
            )
        if ellipses:
            ell = confidence_ellipse(sub[x].to_numpy(), sub[y].to_numpy(), n_std=n_std)
            if ell is not None:
                fig.add_trace(
                    go.Scatter(
                        x=ell[0], y=ell[1], mode="lines",
                        line=dict(color=col, width=2),
                        fill="toself", fillcolor=_rgba(col, 0.08),
                        name=str(cat), legendgroup=str(cat), showlegend=not show_tokens,
                        hoverinfo="skip",
                    )
                )
        mx, my = sub[x].mean(), sub[y].mean()
        fig.add_trace(
            go.Scatter(
                x=[mx], y=[my], mode="markers+text",
                marker=dict(size=11, color=col, line=dict(width=1.5, color=_SURFACE[_mode(dark)])),
                text=[label], textposition="top center",
                textfont=dict(size=14, color=_INK[_mode(dark)]),
                name=str(cat), legendgroup=str(cat), showlegend=False,
                hovertemplate=f"{label} centroid<br>{x}: {mx:.3f}<br>{y}: {my:.3f}<extra></extra>",
            )
        )

    fig.update_xaxes(autorange="reversed", title=_axis_title(x))
    fig.update_yaxes(autorange="reversed", title=_axis_title(y))
    fig.update_layout(
        title=title or "Vowel space",
        legend_title_text="Vowel",
        showlegend=show_tokens,
    )
    return _apply_theme(fig, dark)


# --------------------------------------------------------------------------- #
# The "cross" builder: distribution of a formant by group
# --------------------------------------------------------------------------- #
def formant_cross(
    df: pd.DataFrame,
    formant: str = "F1_norm",
    x: str = "Age Group",
    color: Optional[str] = "vowel_label",
    kind: str = "violin",
    points: str = "all",
    dark: bool = False,
    x_order: Optional[Sequence[str]] = None,
    color_order: Optional[Sequence[str]] = None,
    title: Optional[str] = None,
) -> go.Figure:
    """Distribution of ``formant`` across ``x`` (optionally split by ``color``).

    This is the user's *BET/BEET F1 by Age Group* view.  ``kind`` is
    ``"violin"`` (default; box + all points inside), ``"box"``, or ``"strip"``.
    Violins expose modality and skew that a bar-of-means would hide.
    """
    plot_df = df.copy()
    cat_orders: dict[str, Sequence[str]] = {}
    if x_order:
        cat_orders[x] = list(x_order)
    color_map = None
    if color and color in plot_df.columns:
        cats = list(dict.fromkeys(plot_df[color].dropna().astype(str)))
        order = color_order or sorted(cats)
        cat_orders[color] = order
        color_map = stable_color_map(cats, dark=dark, order=order)

    common = dict(
        x=x, y=formant, color=color if color in plot_df.columns else None,
        category_orders=cat_orders, color_discrete_map=color_map,
    )
    if kind == "box":
        fig = px.box(plot_df, points="outliers", **common)
    elif kind == "strip":
        fig = px.strip(plot_df, **common)
    else:
        fig = px.violin(plot_df, box=True, points=points, **common)
        # Overlay the raw tokens *on* the violin body (pointpos=0 centres them;
        # jitter spreads them across the width) rather than off to one side.
        fig.update_traces(
            meanline_visible=True, scalemode="width", width=0.85, opacity=0.82,
            points=points, pointpos=0, jitter=0.5,
            marker=dict(size=3, opacity=0.45),
        )
        fig.update_layout(violinmode="group")

    fig.update_yaxes(title=_axis_title(formant))
    fig.update_xaxes(title=x)
    fig.update_layout(
        title=title or f"{_axis_title(formant)} by {x}",
        legend_title_text=color if color else "",
    )
    return _apply_theme(fig, dark)


# --------------------------------------------------------------------------- #
# Ridgeline
# --------------------------------------------------------------------------- #
def ridgeline(
    df: pd.DataFrame,
    value: str = "F1_norm",
    group: str = "Age Group",
    dark: bool = False,
    group_order: Optional[Sequence[str]] = None,
    overlap: float = 1.5,
    title: Optional[str] = None,
) -> go.Figure:
    """Stacked density curves (one per level of ``group``) sharing an x-axis."""
    from scipy.stats import gaussian_kde

    levels = list(group_order) if group_order else sorted(
        df[group].dropna().astype(str).unique()
    )
    mode = _mode(dark)
    colours = _sequential_colours(len(levels))
    vals_all = df[value].astype(float).dropna()
    if vals_all.empty:
        return _apply_theme(go.Figure(), dark)
    grid = np.linspace(vals_all.min(), vals_all.max(), 256)

    fig = go.Figure()
    for i, lvl in enumerate(levels):
        sub = df.loc[df[group].astype(str) == lvl, value].astype(float).dropna()
        if len(sub) < 3:
            continue
        kde = gaussian_kde(sub)
        dens = kde(grid)
        dens = dens / dens.max() * overlap
        offset = (len(levels) - 1 - i) * 1.0
        fig.add_trace(
            go.Scatter(
                x=grid, y=dens + offset, mode="lines",
                line=dict(color=colours[i], width=1.5),
                fill="tonexty" if i > 0 else "tozeroy",
                fillcolor=_rgba(colours[i], 0.35),
                name=str(lvl), hovertemplate=f"{lvl}<br>{value}: %{{x:.3f}}<extra></extra>",
            )
        )
        fig.add_annotation(
            x=grid[0], y=offset, text=str(lvl), showarrow=False,
            xanchor="right", font=dict(color=_INK[mode], size=12),
        )
    fig.update_yaxes(showticklabels=False, title="", showgrid=False)
    fig.update_xaxes(title=_axis_title(value))
    fig.update_layout(title=title or f"Distribution of {_axis_title(value)} by {group}",
                      showlegend=False)
    return _apply_theme(fig, dark)


# --------------------------------------------------------------------------- #
# Separation visualisations
# --------------------------------------------------------------------------- #
def separation_bar(
    sep_df: pd.DataFrame,
    metric: str = "JSD",
    dark: bool = False,
    group_order: Optional[Sequence[str]] = None,
    title: Optional[str] = None,
) -> go.Figure:
    """Grouped bars of a separation metric across group levels, one bar per pair.

    Ideal for showing a merger trajectory (e.g. LOT~THOUGHT JSD dropping across
    Age Group).
    """
    plot_df = sep_df.copy()
    if "group_value" in plot_df.columns and plot_df["group_value"].notna().any():
        x = "group_value"
    else:
        x = "pair"
    cats = list(dict.fromkeys(plot_df["pair"].astype(str)))
    cmap = stable_color_map(cats, dark=dark, order=sorted(cats))
    cat_orders = {}
    if group_order and x == "group_value":
        cat_orders[x] = list(group_order)
    fig = px.bar(
        plot_df, x=x, y=metric, color="pair", barmode="group",
        category_orders=cat_orders, color_discrete_map=cmap,
        hover_data=["n_a", "n_b", "Pillai", "Bhattacharyya_overlap"],
    )
    fig.update_layout(title=title or f"{metric} separation", legend_title_text="Vowel pair")
    fig.update_yaxes(title=metric, range=[0, 1] if metric in ("JSD", "Pillai") else None)
    fig.update_xaxes(title=x.replace("group_value", "group"))
    return _apply_theme(fig, dark)


def separation_matrix(
    sep_df: pd.DataFrame,
    metric: str = "JSD",
    group_value: Optional[object] = None,
    dark: bool = False,
    title: Optional[str] = None,
) -> go.Figure:
    """Vowel×vowel heatmap of a separation metric (one group level)."""
    plot_df = sep_df.copy()
    if group_value is not None and "group_value" in plot_df.columns:
        plot_df = plot_df[plot_df["group_value"] == group_value]
    vowels = sorted(set(plot_df["vowel_a"]) | set(plot_df["vowel_b"]))
    mat = pd.DataFrame(np.nan, index=vowels, columns=vowels, dtype=float)
    for _, r in plot_df.iterrows():
        mat.loc[r["vowel_a"], r["vowel_b"]] = r[metric]
        mat.loc[r["vowel_b"], r["vowel_a"]] = r[metric]
    fig = go.Figure(
        go.Heatmap(
            z=mat.values, x=mat.columns, y=mat.index,
            colorscale="Blues", zmin=0, zmax=1 if metric in ("JSD", "Pillai") else None,
            colorbar=dict(title=metric),
            hovertemplate="%{y} ~ %{x}<br>" + metric + ": %{z:.3f}<extra></extra>",
        )
    )
    suffix = f" — {group_value}" if group_value is not None else ""
    fig.update_layout(title=title or f"{metric} separation matrix{suffix}")
    return _apply_theme(fig, dark, height=480)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _axis_title(col: str) -> str:
    pretty = {
        "F1_norm": "F1 (normalized)", "F2_norm": "F2 (normalized)",
        "F3_norm": "F3 (normalized)", "F1": "F1 (Hz)", "F2": "F2 (Hz)", "F3": "F3 (Hz)",
    }
    return pretty.get(col, col)


def _sequential_colours(n: int) -> list[str]:
    """Evenly sample ``n`` hex colours from the blue sequential ramp."""
    if n <= 1:
        return [_BLUE_SEQUENTIAL[3]]
    idx = np.linspace(0, len(_BLUE_SEQUENTIAL) - 1, n).round().astype(int)
    return [_BLUE_SEQUENTIAL[i] for i in idx]


def _rgba(color: str, alpha: float) -> str:
    """Convert a ``#rrggbb`` or ``rgb(r,g,b)`` colour to an ``rgba(...)`` string."""
    color = color.strip()
    if color.startswith("#"):
        h = color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    elif color.startswith("rgb"):
        nums = color[color.index("(") + 1 : color.index(")")].split(",")
        r, g, b = (int(float(n)) for n in nums[:3])
    else:
        return color
    return f"rgba({r},{g},{b},{alpha})"
