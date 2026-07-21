"""Command-line interface for vowelchemy.

Mostly a convenience layer over the library so the pipeline is scriptable and
the Streamlit app is one command away::

    vowelchemy app                       # launch the interactive app
    vowelchemy demo ./demo               # write a synthetic corpus dataset
    vowelchemy discover ./audio --transcripts ./texts
    vowelchemy normalize vowels.csv -m lobanov -s speakers.csv -o out.csv
    vowelchemy separation vowels.csv --vowels IY,EH,AA,AO --group-by "Age Group"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _cmd_app(args: argparse.Namespace) -> int:
    import importlib.util
    import subprocess

    app_path = Path(__file__).with_name("app.py")
    if importlib.util.find_spec("streamlit") is None:
        print("Streamlit is not installed. Install with: pip install streamlit", file=sys.stderr)
        return 1
    cmd = [sys.executable, "-m", "streamlit", "run", str(app_path)]
    if args.port:
        cmd += ["--server.port", str(args.port)]
    return subprocess.call(cmd)


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


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="vowelchemy", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="command", required=True)

    a = sub.add_parser("app", help="launch the interactive Streamlit app")
    a.add_argument("--port", type=int, default=None)
    a.set_defaults(func=_cmd_app)

    d = sub.add_parser("demo", help="write a synthetic demo dataset")
    d.add_argument("out_dir", nargs="?", default="demo")
    d.set_defaults(func=_cmd_demo)

    disc = sub.add_parser("discover", help="scan a corpus location")
    disc.add_argument("audio_dir")
    disc.add_argument("--transcripts", default=None, help="transcript folder (if separate)")
    disc.add_argument("--aligned", default=None, help="folder with aligned TextGrids")
    disc.set_defaults(func=_cmd_discover)

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
