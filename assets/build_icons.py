"""Regenerate every icon asset from ``assets/icon.svg``.

    pip install cairosvg pillow
    python assets/build_icons.py

The generated files are committed, because the desktop-app builds run on
GitHub's macOS/Windows runners where cairosvg (and its native cairo library)
isn't installed.  Re-run this only when the artwork changes.

Outputs
    frontend/public/icon.svg            browser tab + sidebar brand mark
    packaging/desktop/icon.png          the Tk status window's icon
    packaging/desktop/icon.ico          Windows executable
    packaging/desktop/icon.icns         macOS .app bundle
"""

from __future__ import annotations

import io
import shutil
import struct
from pathlib import Path

import cairosvg
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SVG = ROOT / "assets" / "icon.svg"
DESKTOP = ROOT / "packaging" / "desktop"
PUBLIC = ROOT / "frontend" / "public"

# macOS icon types that take a PNG payload, and the pixel size each expects.
ICNS_TYPES = {
    "ic07": 128, "ic08": 256, "ic09": 512, "ic10": 1024,
    "ic11": 32, "ic12": 64, "ic13": 256, "ic14": 512,
}
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)


def render(size: int) -> Image.Image:
    png = cairosvg.svg2png(url=str(SVG), output_width=size, output_height=size)
    return Image.open(io.BytesIO(png)).convert("RGBA")


def png_bytes(size: int) -> bytes:
    buf = io.BytesIO()
    render(size).save(buf, format="PNG")
    return buf.getvalue()


def write_icns(path: Path) -> None:
    """Assemble an .icns container (magic, length, then typed PNG chunks).

    Written by hand so the build works off macOS, where Pillow's ICNS writer
    isn't available.
    """
    chunks = b"".join(
        kind.encode("ascii") + struct.pack(">I", len(data) + 8) + data
        for kind, data in ((k, png_bytes(s)) for k, s in ICNS_TYPES.items())
    )
    path.write_bytes(b"icns" + struct.pack(">I", len(chunks) + 8) + chunks)


def main() -> None:
    DESKTOP.mkdir(parents=True, exist_ok=True)
    PUBLIC.mkdir(parents=True, exist_ok=True)

    shutil.copyfile(SVG, PUBLIC / "icon.svg")
    render(512).save(DESKTOP / "icon.png")
    render(256).save(DESKTOP / "icon.ico", sizes=[(s, s) for s in ICO_SIZES])
    write_icns(DESKTOP / "icon.icns")

    for out in (PUBLIC / "icon.svg", DESKTOP / "icon.png",
                DESKTOP / "icon.ico", DESKTOP / "icon.icns"):
        print(f"  {out.relative_to(ROOT)}  ({out.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
