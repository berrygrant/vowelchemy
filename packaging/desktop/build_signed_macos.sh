#!/usr/bin/env bash
# Build Vowelchemy.app signed with a Developer ID, have Apple notarize it,
# staple the ticket and zip it. The result opens on any Mac with a plain
# double-click — no "Apple could not verify…" refusal, no trip through
# System Settings ▸ Privacy & Security ▸ Open Anyway.
#
# Usage, from the repository root (after `pip install . "pyinstaller>=6"`):
#     packaging/desktop/build_signed_macos.sh [Vowelchemy-macOS.zip]
#
# Environment — the release workflow sets these from repository secrets;
# docs/RELEASING.md ("Signing") explains where each one comes from:
#     MACOS_CERTIFICATE           base64 of the "Developer ID Application" .p12
#     MACOS_CERTIFICATE_PASSWORD  the password chosen when exporting it
#     MACOS_SIGNING_IDENTITY      optional: "Developer ID Application: Name (TEAMID)";
#                                 read from the certificate when unset
# and notarization credentials — either an App Store Connect API key
#     APPLE_API_KEY               base64 of the AuthKey_<KEYID>.p8 file
#     APPLE_API_KEY_ID            its key ID
#     APPLE_API_ISSUER_ID         the issuer ID shown above the key list
# or an Apple ID
#     APPLE_ID                    the account's e-mail address
#     APPLE_TEAM_ID               the 10-character team ID
#     APPLE_APP_PASSWORD          an app-specific password (account.apple.com)
#
# The certificate is imported into a throw-away keychain that is deleted on
# exit; nothing is added to the login keychain. Works with macOS's own bash 3.2.
set -euo pipefail

ZIP="${1:-Vowelchemy-macOS.zip}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SPEC="packaging/desktop/vowelchemy.spec"
APP="dist/Vowelchemy.app"
cd "$ROOT"

[ "$(uname)" = "Darwin" ] || { echo "This script needs macOS (codesign, notarytool, stapler)." >&2; exit 1; }
: "${MACOS_CERTIFICATE:?set MACOS_CERTIFICATE (base64 of the Developer ID Application .p12)}"
: "${MACOS_CERTIFICATE_PASSWORD:?set MACOS_CERTIFICATE_PASSWORD}"
if [ -n "${APPLE_API_KEY:-}" ]; then
  : "${APPLE_API_KEY_ID:?set APPLE_API_KEY_ID}"
  : "${APPLE_API_ISSUER_ID:?set APPLE_API_ISSUER_ID}"
else
  : "${APPLE_ID:?set APPLE_ID (or an App Store Connect API key in APPLE_API_KEY)}"
  : "${APPLE_TEAM_ID:?set APPLE_TEAM_ID}"
  : "${APPLE_APP_PASSWORD:?set APPLE_APP_PASSWORD (an app-specific password)}"
fi

WORK="$(mktemp -d)"
KEYCHAIN="$WORK/vowelchemy-signing.keychain-db"
KEYCHAIN_PASSWORD="$(uuidgen)"
# Remember the current keychain search list so it can be restored on exit.
ORIGINAL_KEYCHAINS=()
while IFS= read -r line; do
  line="${line#"${line%%[![:space:]]*}"}"   # strip leading spaces
  line="${line%\"}"; line="${line#\"}"       # and the quotes
  [ -n "$line" ] && ORIGINAL_KEYCHAINS+=("$line")
done < <(security list-keychains -d user)
cleanup() {
  security list-keychains -d user -s ${ORIGINAL_KEYCHAINS[@]+"${ORIGINAL_KEYCHAINS[@]}"} >/dev/null 2>&1 || true
  security delete-keychain "$KEYCHAIN" >/dev/null 2>&1 || true
  rm -rf "$WORK"
}
trap cleanup EXIT

echo "::group::Import the Developer ID certificate into a temporary keychain"
printf '%s' "$MACOS_CERTIFICATE" | base64 --decode > "$WORK/certificate.p12"
security create-keychain -p "$KEYCHAIN_PASSWORD" "$KEYCHAIN"
security set-keychain-settings -lut 21600 "$KEYCHAIN"   # do not auto-lock during the build
security unlock-keychain -p "$KEYCHAIN_PASSWORD" "$KEYCHAIN"
security import "$WORK/certificate.p12" -k "$KEYCHAIN" -P "$MACOS_CERTIFICATE_PASSWORD" \
  -T /usr/bin/codesign -T /usr/bin/security
# Apple's intermediate for Developer ID certificates, in case the machine
# has never had Xcode sign in (codesign otherwise fails to build the chain).
if curl -fsSL -o "$WORK/DeveloperIDG2CA.cer" https://www.apple.com/certificateauthority/DeveloperIDG2CA.cer; then
  security import "$WORK/DeveloperIDG2CA.cer" -k "$KEYCHAIN" >/dev/null 2>&1 || true
fi
# Let codesign use the private key without a GUI prompt.
security set-key-partition-list -S apple-tool:,apple: -s -k "$KEYCHAIN_PASSWORD" "$KEYCHAIN" >/dev/null
security list-keychains -d user -s "$KEYCHAIN" ${ORIGINAL_KEYCHAINS[@]+"${ORIGINAL_KEYCHAINS[@]}"}

IDENTITY="${MACOS_SIGNING_IDENTITY:-}"
if [ -z "$IDENTITY" ]; then
  IDENTITY="$(security find-identity -v -p codesigning "$KEYCHAIN" \
    | sed -n 's/.*"\(Developer ID Application: [^"]*\)".*/\1/p' | head -n 1)"
fi
if [ -z "$IDENTITY" ]; then
  echo "The certificate holds no valid 'Developer ID Application' identity — that is the" >&2
  echo "kind Gatekeeper trusts outside the App Store. See docs/RELEASING.md, 'Signing'." >&2
  security find-identity -v -p codesigning "$KEYCHAIN" >&2 || true
  exit 1
fi
echo "Signing as: $IDENTITY"
echo "::endgroup::"

echo "::group::Build with PyInstaller, signing every binary and then the bundle"
# vowelchemy.spec passes the identity and packaging/desktop/entitlements.plist
# to PyInstaller, which signs each binary with the hardened runtime and a
# secure timestamp, then the .app itself — the order notarization expects.
VOWELCHEMY_CODESIGN_IDENTITY="$IDENTITY" pyinstaller "$SPEC" --noconfirm
codesign --verify --deep --strict --verbose=2 "$APP"
echo "::endgroup::"

echo "::group::Notarize with Apple"
if [ -n "${APPLE_API_KEY:-}" ]; then
  printf '%s' "$APPLE_API_KEY" | base64 --decode > "$WORK/AuthKey.p8"
  AUTH=(--key "$WORK/AuthKey.p8" --key-id "$APPLE_API_KEY_ID" --issuer "$APPLE_API_ISSUER_ID")
else
  AUTH=(--apple-id "$APPLE_ID" --team-id "$APPLE_TEAM_ID" --password "$APPLE_APP_PASSWORD")
fi
ditto -c -k --keepParent "$APP" "$WORK/for-notarization.zip"
set +e
RESULT="$(xcrun notarytool submit "$WORK/for-notarization.zip" --wait --timeout 1h \
  --output-format json "${AUTH[@]}" 2>&1)"
SUBMIT_EXIT=$?
set -e
echo "$RESULT"
json_field() {  # json_field "$json" key -> value ("" when absent or unparsable)
  python3 -c 'import json, re, sys
m = re.search(r"\{.*\}", sys.argv[1], re.S)
print((json.loads(m.group(0)) if m else {}).get(sys.argv[2], ""))' "$1" "$2" 2>/dev/null || true
}
SUBMISSION_ID="$(json_field "$RESULT" id)"
STATUS="$(json_field "$RESULT" status)"
if [ "$SUBMIT_EXIT" -ne 0 ] || [ "$STATUS" != "Accepted" ]; then
  echo "::error::Notarization did not succeed (status: ${STATUS:-unknown})."
  if [ -n "$SUBMISSION_ID" ]; then
    echo "Apple's log for submission $SUBMISSION_ID — each 'issue' names the file to fix:"
    xcrun notarytool log "$SUBMISSION_ID" "${AUTH[@]}" || true
  fi
  exit 1
fi
# Staple the ticket into the bundle so Gatekeeper accepts it offline as well.
xcrun stapler staple "$APP"
spctl --assess --type exec --verbose=2 "$APP"   # expects "accepted … Notarized Developer ID"
echo "::endgroup::"

# The zip must hold the *stapled* bundle, so it is made only now.
rm -f "$ZIP"
ditto -c -k --keepParent "$APP" "$ZIP"
echo "Signed, notarized and stapled: $ZIP"
