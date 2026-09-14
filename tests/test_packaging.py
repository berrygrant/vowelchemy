"""The desktop packaging pieces agree with each other.

The signing path spans three files that never run in CI on Linux: the
PyInstaller spec reads an environment variable that the macOS signing script
sets, and the entitlements file the spec points at must be a valid plist with
the exceptions a PyInstaller app needs under the hardened runtime. These
checks catch a rename in one place that the others did not follow.
"""

import plistlib
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "packaging" / "desktop"
WORKFLOWS = ROOT / ".github" / "workflows"

IDENTITY_VAR = "VOWELCHEMY_CODESIGN_IDENTITY"


def test_entitlements_are_a_valid_plist_with_the_hardened_runtime_exceptions():
    with open(DESKTOP / "entitlements.plist", "rb") as fh:
        ent = plistlib.load(fh)
    for key in (
        "com.apple.security.cs.allow-unsigned-executable-memory",
        "com.apple.security.cs.disable-library-validation",
    ):
        assert ent.get(key) is True, key


def test_spec_reads_the_identity_the_signing_script_exports():
    spec = (DESKTOP / "vowelchemy.spec").read_text(encoding="utf-8")
    script = (DESKTOP / "build_signed_macos.sh").read_text(encoding="utf-8")
    assert f'os.environ.get("{IDENTITY_VAR}")' in spec
    assert re.search(rf"^{IDENTITY_VAR}=", script, re.M), (
        "script must export the identity to pyinstaller"
    )
    assert "entitlements.plist" in spec
    assert "codesign_identity=CODESIGN_IDENTITY" in spec
    assert "entitlements_file=ENTITLEMENTS_FILE" in spec


def test_spec_stamps_the_declared_version_into_the_bundle():
    spec = (DESKTOP / "vowelchemy.spec").read_text(encoding="utf-8")
    assert "from vowelchemy import __version__ as APP_VERSION" in spec
    assert '"CFBundleShortVersionString": APP_VERSION' in spec


def test_release_workflow_hands_the_signing_secrets_to_the_build():
    release_text = (WORKFLOWS / "release.yml").read_text(encoding="utf-8")
    # Without this the reusable build sees no secrets and every release ships unsigned.
    assert re.search(r"^\s+secrets: inherit\s*$", release_text, re.M)

    yaml = pytest.importorskip("yaml")  # PyYAML is not a dependency of vowelchemy itself
    build = yaml.safe_load((WORKFLOWS / "build-app.yml").read_text(encoding="utf-8"))
    declared = set(build[True]["workflow_call"]["secrets"])  # YAML parses the `on:` key as True
    script = (DESKTOP / "build_signed_macos.sh").read_text(encoding="utf-8")
    used = set(re.findall(r"\$\{(MACOS_[A-Z_]+|APPLE_[A-Z_]+)", script))
    assert used <= declared, used - declared
    steps = {s.get("name"): s for s in build["jobs"]["build"]["steps"]}
    signed = steps["Build, sign, notarize and staple (macOS)"]
    assert set(signed["env"]) == {k for k in declared if not k.startswith("WINDOWS_")}
    assert "SIGN_MACOS == 'true'" in signed["if"]
    assert "SIGN_MACOS != 'true'" in steps["Build (unsigned)"]["if"]
