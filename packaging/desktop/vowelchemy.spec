# PyInstaller spec for the Vowelchemy desktop app.
#
# Build (from the repository root, with `pip install . pyinstaller` done):
#     pyinstaller packaging/desktop/vowelchemy.spec --noconfirm
#
# Outputs (under dist/):
#   Windows  -> Vowelchemy.exe            (single file)
#   macOS    -> Vowelchemy.app            (windowed bundle)
#   Linux    -> Vowelchemy/               (one-dir; mostly for CI smoke tests)
#
# The React UI ships inside the wheel (vowelchemy/webui), so collecting the
# package's data files is all it takes to serve the full app.

import os
import sys

from PyInstaller.utils.hooks import collect_data_files

APP_NAME = "Vowelchemy"
ONEFILE = sys.platform == "win32"
# Resolve the vowelchemy package from the source checkout itself, so the build
# works whether the venv install was editable or regular.
REPO_ROOT = os.path.abspath(os.path.join(SPECPATH, "..", ".."))  # noqa: F821

datas = collect_data_files("vowelchemy")  # webui/** and any other package data

hiddenimports = [
    # uvicorn assembles its stack dynamically
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on",
    # fastapi imports this lazily for UploadFile routes
    "multipart",
    # entry script imports these inside main(); make them explicit
    "vowelchemy",
    "vowelchemy.api",
]

a = Analysis(
    ["launch_vowelchemy.py"],
    pathex=[REPO_ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["pytest", "ruff"],
    noarchive=False,
)
pyz = PYZ(a.pure)

if ONEFILE:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        name=APP_NAME,
        console=False,
        upx=False,
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        exclude_binaries=True,
        name=APP_NAME,
        console=False,
        upx=False,
    )
    coll = COLLECT(exe, a.binaries, a.datas, name=APP_NAME, upx=False)
    if sys.platform == "darwin":
        app = BUNDLE(
            coll,
            name=f"{APP_NAME}.app",
            bundle_identifier="info.luv-lab.vowelchemy",
            info_plist={
                "NSHighResolutionCapable": True,
                "LSApplicationCategoryType": "public.app-category.education",
            },
        )
