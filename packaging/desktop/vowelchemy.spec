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
HERE = os.path.abspath(SPECPATH)  # noqa: F821
ICON_ICO = os.path.join(HERE, "icon.ico")     # Windows executable
ICON_ICNS = os.path.join(HERE, "icon.icns")   # macOS .app bundle
ICON_PNG = os.path.join(HERE, "icon.png")     # Tk status window
PLATFORM_ICON = ICON_ICNS if sys.platform == "darwin" else ICON_ICO
# Resolve the vowelchemy package from the source checkout itself (src layout),
# so the build works whether the venv install was editable or regular.
SRC_DIR = os.path.abspath(os.path.join(SPECPATH, "..", "..", "src"))  # noqa: F821
sys.path.insert(0, SRC_DIR)
from vowelchemy import __version__ as APP_VERSION  # noqa: E402  (the bundle's version)

# macOS signing. When VOWELCHEMY_CODESIGN_IDENTITY names a "Developer ID
# Application" certificate in an unlocked keychain, PyInstaller signs every
# binary and then the bundle with it — hardened runtime, secure timestamp and
# the entitlements next to this file — which is what notarization requires.
# build_signed_macos.sh sets it (and notarizes afterwards); unset means the
# usual ad-hoc signature, fine for local test builds and other platforms.
CODESIGN_IDENTITY = os.environ.get("VOWELCHEMY_CODESIGN_IDENTITY") or None
ENTITLEMENTS_FILE = os.path.join(HERE, "entitlements.plist") if CODESIGN_IDENTITY else None

datas = collect_data_files("vowelchemy")  # webui/** and any other package data
datas += [(ICON_PNG, ".")]  # the status window loads this at run time

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
    pathex=[SRC_DIR],
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
        icon=PLATFORM_ICON,
        codesign_identity=CODESIGN_IDENTITY,
        entitlements_file=ENTITLEMENTS_FILE,
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        exclude_binaries=True,
        name=APP_NAME,
        console=False,
        upx=False,
        icon=PLATFORM_ICON,
        codesign_identity=CODESIGN_IDENTITY,
        entitlements_file=ENTITLEMENTS_FILE,
    )
    # COLLECT and BUNDLE inherit the signing settings from the EXE.
    coll = COLLECT(exe, a.binaries, a.datas, name=APP_NAME, upx=False)
    if sys.platform == "darwin":
        app = BUNDLE(
            coll,
            name=f"{APP_NAME}.app",
            icon=ICON_ICNS,
            bundle_identifier="info.luv-lab.vowelchemy",
            info_plist={
                "CFBundleShortVersionString": APP_VERSION,
                "CFBundleVersion": APP_VERSION,
                "NSHighResolutionCapable": True,
                "LSApplicationCategoryType": "public.app-category.education",
            },
        )
