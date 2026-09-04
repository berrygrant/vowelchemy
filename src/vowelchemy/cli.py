"""Command-line interface for vowelchemy.

Mostly a convenience layer over the library so the pipeline is scriptable and
the web app is one command away::

    vowelchemy app                       # launch the API + React app
    vowelchemy doctor                    # what's installed, where, which tools
    vowelchemy demo ./demo               # write a synthetic corpus dataset
    vowelchemy discover ./audio --transcripts ./texts
    vowelchemy validate ./audio --transcripts ./texts   # mfa validate
    vowelchemy align ./audio --transcripts ./texts -o ./aligned
    vowelchemy extract ./audio --aligned ./aligned -o ./vowels
    vowelchemy normalize vowels.csv -m lobanov -s speakers.csv -o out.csv
    vowelchemy separation vowels.csv --vowels IY,EH,AA,AO --group-by "Age Group"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .constants import DEFAULT_ACOUSTIC_MODEL, DEFAULT_DICTIONARY


def _open_when_ready(url: str, timeout: float = 60.0) -> None:
    """Poll ``url`` until the server answers, then open it in the default browser."""
    import time
    import urllib.request
    import webbrowser

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
        except OSError:
            time.sleep(0.3)
        else:
            webbrowser.open(url)
            return


def _cmd_app(args: argparse.Namespace) -> int:
    import importlib.util
    import subprocess
    import threading

    from . import webui_dir

    if importlib.util.find_spec("uvicorn") is None:
        print("uvicorn is not installed. Install with: pip install -e .", file=sys.stderr)
        return 1
    port = args.port or 8000
    if webui_dir() is None:
        print("Note: the React front-end has not been built yet. Serving the API only.\n"
              "      Build it with:  vowelchemy setup\n"
              "      or run the dev server:  cd frontend && npm run dev\n", file=sys.stderr)
    url = f"http://127.0.0.1:{port}"
    print(f"Vowelchemy running at {url}  (API under /api; Ctrl+C to stop)")
    if not args.no_browser:
        threading.Thread(target=_open_when_ready, args=(url,), daemon=True).start()
    cmd = [sys.executable, "-m", "uvicorn", "vowelchemy.api:app",
           "--host", "127.0.0.1", "--port", str(port)]
    if args.reload:
        cmd.append("--reload")
    return subprocess.call(cmd)


def _tool_detail(status) -> str:
    """One-line 'where and which version' for an external CLI tool."""
    if not status.available:
        return "not found"
    version = status.version or ""
    return f"{version} [{status.path}]" if version and version != status.path else str(status.path)


def _cmd_doctor(args: argparse.Namespace) -> int:
    """Report what is installed and where — the first thing to run when stuck."""
    from . import alignment, extraction, phontrast, toolenv

    info = toolenv.app_info()
    print("Vowelchemy")
    print(f"  version   : {info['version']}")
    print(f"  code      : {info['location']}")
    print(f"  python    : {info['python']} ({info['executable']})")
    print(f"  UI bundle : {info['webui'] or 'NOT BUILT (API only) — run: vowelchemy setup'}")

    selected = toolenv.selected_prefix()
    print(f"\nTool environment: {selected or 'none selected (using PATH)'}")
    # The CLI can afford to wait for real version strings.
    pj = phontrast.phontrast_status(wait=True)
    mfa, nf = alignment.mfa_status(wait=True), extraction.newfave_status(wait=True)
    rows = [("MFA", mfa.available, _tool_detail(mfa)),
            ("new-fave", nf.available, _tool_detail(nf)),
            ("phontrast (R)", pj.available,
             f"{pj.package} {pj.version}" if pj.available else "not found (built-in JSD used)")]
    for label, available, detail in rows:
        print(f"  {'OK ' if available else '-- '}{label:14s}: {detail}")

    envs = toolenv.discover_environments()
    if envs:
        print("\nEnvironments containing the tools:")
        for env in envs:
            print(f"  {env.name:20s} {'+'.join(sorted(env.tools)):16s} {env.path}")
        print("\nSelect one with:  vowelchemy doctor --use-env <path>")
    else:
        print("\nNo conda/mamba environment with MFA or new-fave was found.")
        print(toolenv.MFA_CONDA_HINT)
    return 0


def _cmd_use_env(args: argparse.Namespace) -> int:
    from . import toolenv

    try:
        tools = toolenv.set_selected_prefix(args.use_env)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.use_env:
        print(f"Using {args.use_env} for: {', '.join(sorted(tools))}")
    else:
        print("Cleared the tool environment; falling back to PATH.")
    return 0


def _cmd_demo(args: argparse.Namespace) -> int:
    from .sample_data import write_demo_dataset

    paths = write_demo_dataset(args.out_dir)
    print(f"Wrote demo vowel data:   {paths['vowels']}")
    print(f"Wrote demo speaker table: {paths['speakers']}")
    return 0


def _cmd_discover(args: argparse.Namespace) -> int:
    from .corpus import discover_corpus, validate_location

    status = validate_location(args.audio_dir)
    if not status.ok:
        print(f"Audio directory problem: {status.message}", file=sys.stderr)
        return 1
    inv = discover_corpus(args.audio_dir, transcript_dir=args.transcripts,
                          aligned_dir=args.aligned)
    summary = inv.summary()
    print(f"Corpus at {inv.audio_dir}")
    for k, v in summary.items():
        print(f"  {k:24s}: {v}")
    if inv.warnings:
        print("Warnings:")
        for w in inv.warnings[:10]:
            print(f"  - {w}")
    return 0


def _load_and_prepare(vowels_csv, speakers_csv):
    from . import analysis
    from .schema import ColumnSchema

    df = analysis.load_vowel_data(vowels_csv)
    schema = ColumnSchema.detect(df)
    if speakers_csv:
        demo = analysis.load_demographics(speakers_csv)
        df = analysis.join_demographics(df, demo, schema)
    df = analysis.add_vowel_labels(df, schema)
    return df, schema


def _cmd_normalize(args: argparse.Namespace) -> int:
    from . import normalization as norm

    df, schema = _load_and_prepare(args.vowels_csv, args.speakers)
    res = norm.normalize(df, schema, method=args.method)
    out = args.output or Path(args.vowels_csv).with_name(
        Path(args.vowels_csv).stem + f"_{args.method}.csv"
    )
    res.data.to_csv(out, index=False)
    print(f"Normalized with '{res.method}' ({res.units}). Wrote {out}")
    for note in res.notes:
        print(f"  note: {note}")
    return 0


def _cmd_separation(args: argparse.Namespace) -> int:
    from . import metrics, normalization as norm

    df, schema = _load_and_prepare(args.vowels_csv, args.speakers)
    if args.method != "none":
        df = norm.normalize(df, schema, method=args.method).data
    vowels = args.vowels.split(",") if args.vowels else None
    sep = metrics.pairwise_separation(df, schema, vowels=vowels, group_by=args.group_by)
    if sep.empty:
        print("No vowel pairs met the minimum token threshold.")
        return 0
    cols = ["group_value", "vowel_a", "vowel_b", "n_a", "n_b", "JSD", "Pillai",
            "Bhattacharyya_overlap"]
    print(sep[[c for c in cols if c in sep.columns]].to_string(index=False))
    if args.output:
        sep.to_csv(args.output, index=False)
        print(f"\nWrote {args.output}")
    return 0


def _cmd_setup(args: argparse.Namespace) -> int:
    """Build the React front-end so `vowelchemy app` can serve it (needs Node)."""
    import shutil
    import subprocess

    from . import webui_dir

    # src layout: package lives at <repo>/src/vowelchemy, frontend at <repo>/frontend.
    frontend = Path(__file__).resolve().parents[2] / "frontend"
    if not frontend.is_dir():
        print("frontend/ directory not found next to the package "
              "(a source checkout is required to rebuild the UI).", file=sys.stderr)
        return 1
    if webui_dir() is not None and not args.force:
        print(f"UI already built ({webui_dir()}). Use --force to rebuild.")
        return 0
    npm = shutil.which("npm")
    if not npm:
        print("npm/Node not found. Install Node >= 18 and re-run, or use the Docker image "
              "(docker build -t vowelchemy .).", file=sys.stderr)
        return 1
    print("Installing front-end dependencies…")
    if subprocess.call([npm, "install"], cwd=str(frontend)) != 0:
        return 1
    print("Building the UI…")
    if subprocess.call([npm, "run", "build"], cwd=str(frontend)) != 0:
        return 1
    print("Done. Launch with:  vowelchemy app")
    return 0


def _cmd_align(args: argparse.Namespace) -> int:
    from . import alignment
    from .corpus import discover_corpus

    if not alignment.mfa_status().available:
        print("MFA not found.\n" + alignment.MFA_INSTALL_HINT, file=sys.stderr)
        return 1
    inv = discover_corpus(args.audio_dir, transcript_dir=args.transcripts, aligned_dir=args.aligned)
    out = args.output or str(Path(args.audio_dir).parent / "vowelchemy_aligned")
    if args.download_models:
        alignment.download_models(args.acoustic, args.dictionary, on_output=print)
    res = alignment.align_inventory(
        inv, out, dictionary=args.dictionary, acoustic_model=args.acoustic,
        num_jobs=args.jobs, on_output=print,
    )
    print(f"{'OK' if res.ok else 'FAILED'}: {len(res.textgrids)} TextGrids in {res.output_dir}")
    return 0 if res.ok else 1


def _cmd_validate(args: argparse.Namespace) -> int:
    """Stage the corpus and run MFA's own validator against it."""
    import tempfile

    from . import alignment
    from .corpus import discover_corpus

    if not alignment.mfa_status().available:
        print("MFA not found.\n" + alignment.MFA_INSTALL_HINT, file=sys.stderr)
        return 1
    inv = discover_corpus(args.audio_dir, transcript_dir=args.transcripts)
    staging = tempfile.mkdtemp(prefix="vowelchemy_validate_")
    staged = alignment.stage_corpus(inv, staging)
    print(f"Staged {staged.n_staged} recording(s); running mfa validate…")
    res = alignment.validate_corpus(
        staged.corpus_dir, dictionary=args.dictionary, acoustic_model=args.acoustic,
        num_jobs=args.jobs, on_output=print,
    )
    print("OK" if res.ok else "Validation reported problems (see output above).")
    return 0 if res.ok else 1


def _cmd_extract(args: argparse.Namespace) -> int:
    from . import extraction

    if not extraction.newfave_status().available:
        print("new-fave not found.\n" + extraction.NEWFAVE_INSTALL_HINT, file=sys.stderr)
        return 1
    out = args.output or str(Path(args.audio_dir).parent / "vowelchemy_vowels")
    res = extraction.extract_vowels(
        args.audio_dir, args.aligned, out, speakers_file=args.speakers,
        exclude_overlaps=not args.no_exclude_overlaps, on_output=print,
    )
    for note in res.notes:
        print("note:", note)
    if res.ok:
        print(f"OK: {len(res.data)} tokens -> {res.csv_path}")
        return 0
    print("Extraction produced no usable data.", file=sys.stderr)
    return 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="vowelchemy", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="command", required=True)

    a = sub.add_parser("app", help="launch the API + React app (uvicorn)")
    a.add_argument("--port", type=int, default=None)
    a.add_argument("--reload", action="store_true", help="auto-reload (development)")
    a.add_argument("--no-browser", action="store_true", dest="no_browser",
                   help="don't open the app in a browser once the server is up")
    a.set_defaults(func=_cmd_app)

    doc = sub.add_parser("doctor", help="show what's installed, where, and which tools are found")
    doc.add_argument("--use-env", default=None, metavar="PATH",
                     help="use this conda/mamba environment for MFA/new-fave "
                          "(pass '' to clear)")
    doc.set_defaults(func=lambda a: _cmd_use_env(a) if a.use_env is not None else _cmd_doctor(a))

    setup = sub.add_parser("setup", help="build the React UI (needs Node)")
    setup.add_argument("--force", action="store_true", help="rebuild even if dist/ exists")
    setup.set_defaults(func=_cmd_setup)

    d = sub.add_parser("demo", help="write a synthetic demo dataset")
    d.add_argument("out_dir", nargs="?", default="demo")
    d.set_defaults(func=_cmd_demo)

    disc = sub.add_parser("discover", help="scan a corpus location")
    disc.add_argument("audio_dir")
    disc.add_argument("--transcripts", default=None, help="transcript folder (if separate)")
    disc.add_argument("--aligned", default=None, help="folder with aligned TextGrids")
    disc.set_defaults(func=_cmd_discover)

    al = sub.add_parser("align", help="force-align a corpus with MFA")
    al.add_argument("audio_dir")
    al.add_argument("--transcripts", default=None)
    al.add_argument("--aligned", default=None)
    al.add_argument("-o", "--output", default=None)
    al.add_argument("--acoustic", default=DEFAULT_ACOUSTIC_MODEL)
    al.add_argument("--dictionary", default=DEFAULT_DICTIONARY)
    al.add_argument("-j", "--jobs", type=int, default=3)
    al.add_argument("--download-models", action="store_true", dest="download_models")
    al.set_defaults(func=_cmd_align)

    v = sub.add_parser("validate", help="run `mfa validate` on a corpus before aligning")
    v.add_argument("audio_dir")
    v.add_argument("--transcripts", default=None)
    v.add_argument("--acoustic", default=DEFAULT_ACOUSTIC_MODEL)
    v.add_argument("--dictionary", default=DEFAULT_DICTIONARY)
    v.add_argument("-j", "--jobs", type=int, default=3)
    v.set_defaults(func=_cmd_validate)

    ex = sub.add_parser("extract", help="extract vowels with new-fave")
    ex.add_argument("audio_dir")
    ex.add_argument("--aligned", required=True, help="folder with aligned TextGrids")
    ex.add_argument("-o", "--output", default=None)
    ex.add_argument("-s", "--speakers", default=None)
    ex.add_argument("--no-exclude-overlaps", action="store_true", dest="no_exclude_overlaps")
    ex.set_defaults(func=_cmd_extract)

    n = sub.add_parser("normalize", help="normalize a vowel CSV")
    n.add_argument("vowels_csv")
    n.add_argument("-m", "--method", default="lobanov")
    n.add_argument("-s", "--speakers", default=None, help="speaker demographics CSV")
    n.add_argument("-o", "--output", default=None)
    n.set_defaults(func=_cmd_normalize)

    s = sub.add_parser("separation", help="compute JSD separation metrics")
    s.add_argument("vowels_csv")
    s.add_argument("--vowels", default=None, help="comma-separated vowels (ARPABET/keyword)")
    s.add_argument("--group-by", default=None, dest="group_by")
    s.add_argument("-m", "--method", default="lobanov", help="normalization before metrics")
    s.add_argument("-s", "--speakers", default=None)
    s.add_argument("-o", "--output", default=None)
    s.set_defaults(func=_cmd_separation)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
