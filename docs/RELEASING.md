# Releasing Vowelchemy

Two commands. The version is declared in four files, so never edit it by
hand — the script rewrites all of them, and the release action checks them.

```bash
python scripts/bump_version.py 0.3.4        # pyproject.toml, CITATION.cff (+ date), __init__.py, README
git commit -am "Bump version to 0.3.4" && git push
```

When that commit lands on `main` (pushed directly or merged from a branch),
**Release on version bump** (`.github/workflows/release.yml`) takes over:

1. it checks the four declarations agree — a bump made by hand in one file
   fails here, with the command that fixes it;
2. it tags the commit `v0.3.4` (if that tag does not already exist);
3. it runs **Build desktop app** (`build-app.yml`), which builds
   `Vowelchemy-macOS.zip` and `Vowelchemy-Windows.zip` with PyInstaller and
   publishes the GitHub Release for the tag with both zips attached and
   release notes generated from the commits since the previous release.

Running copies then see the new version through the in-app update check,
which reads GitHub's *latest release* — a bare tag without a release would be
invisible to them, which is why the workflow creates the release. Edit the
generated notes on the Releases page if you want to say more.

Manual paths still work: pushing a tag by hand (`git tag v0.3.4 && git push
origin v0.3.4`) runs the same build, and the Actions tab can build the zips
on demand without publishing anything. A tag that does not match the declared
version is refused before the builds start.

Checks you can run yourself: `python scripts/bump_version.py --check`
(which file is off?), `--check v0.3.4` (does this tag match?), `--print` (the
declared version). `tests/test_version.py` fails CI whenever the four
declarations disagree.

Version numbers: `MAJOR.MINOR.PATCH`. A change to the metrics' column names
or defaults (anything that changes numbers or CSVs users already have) is at
least a MINOR bump. A pre-release suffix (`0.4.0rc1`) is published as a
GitHub pre-release, which the update check ignores.

## Signing: opening without the Gatekeeper detour

An unsigned download is what makes macOS refuse the app with "Apple could not
verify…" and send people to **Privacy & Security ▸ Open Anyway** (macOS 15
removed the old right-click ▸ Open shortcut). There is no setting that avoids
this on the user's side short of a Terminal command
(`xattr -d com.apple.quarantine Vowelchemy.app`, per download, per machine).
The fix is on the publishing side: sign the app with a **Developer ID
Application** certificate, have Apple **notarize** it, and staple the
ticket. `build-app.yml` does all of this by itself as soon as the secrets
below exist; with no secrets it keeps producing the unsigned zip.

**What you need.** An Apple Developer Program membership (US$99/year for an
individual, or an organization account — Villanova may already have one; ask
the department or IT, since only the account holder can create Developer ID
certificates). Then:

1. **Certificate.** In Xcode ▸ Settings ▸ Accounts ▸ *Manage Certificates…*
   ▸ **+** ▸ *Developer ID Application* (or on
   developer.apple.com ▸ Certificates). In **Keychain Access** ▸ My
   Certificates, right-click the new "Developer ID Application: …"
   certificate ▸ *Export…* as a `.p12` with a password. Encode it:
   `base64 -i DeveloperID.p12 | pbcopy`.
2. **Notarization credentials.** Preferably an App Store Connect API key:
   appstoreconnect.apple.com ▸ Users and Access ▸ *Integrations* ▸ *Team
   Keys* ▸ **+**, role *Developer*; download the `AuthKey_<KEYID>.p8` (once
   only), note the **Key ID** and the **Issuer ID** shown above the list;
   `base64 -i AuthKey_<KEYID>.p8 | pbcopy`. Alternatively an Apple ID with
   an app-specific password from account.apple.com ▸ Sign-In and Security,
   plus the 10-character **Team ID** from developer.apple.com ▸ Membership.
3. **Repository secrets.** GitHub ▸ Settings ▸ Secrets and variables ▸
   Actions ▸ *New repository secret*:

   | Secret | Value |
   |---|---|
   | `MACOS_CERTIFICATE` | the base64 `.p12` |
   | `MACOS_CERTIFICATE_PASSWORD` | its export password |
   | `APPLE_API_KEY`, `APPLE_API_KEY_ID`, `APPLE_API_ISSUER_ID` | the base64 `.p8`, its key ID, the issuer ID |
   | *or* `APPLE_ID`, `APPLE_TEAM_ID`, `APPLE_APP_PASSWORD` | Apple ID e-mail, team ID, app-specific password |
   | `MACOS_SIGNING_IDENTITY` | optional: "Developer ID Application: Name (TEAMID)" if the `.p12` holds several identities |

4. **Try it.** Actions ▸ *Build desktop app* ▸ *Run workflow*. The macOS
   job's log shows "Signing as: Developer ID Application: …", the
   notarization result (`status: Accepted`) and `spctl` answering
   `accepted … source=Notarized Developer ID`. Download the artifact, unzip
   it and double-click: no prompt. The next `bump_version.py` release is
   then signed automatically (`release.yml` passes the secrets through).

The same script runs locally on a Mac with the variables exported —
`packaging/desktop/build_signed_macos.sh` — and prints Apple's notarization
log when a submission is rejected (it names the offending file). The
certificate is imported into a temporary keychain that is deleted
afterwards. The hardened-runtime exceptions the Python app needs are in
`packaging/desktop/entitlements.plist`; `vowelchemy.spec` applies them and
the identity whenever `VOWELCHEMY_CODESIGN_IDENTITY` is set.

**Windows (optional).** SmartScreen's "Windows protected your PC" is a
softer problem — *More info ▸ Run anyway* is one click — and needs a
code-signing certificate from a commercial CA. If you have one whose key can
be exported (`.pfx`), add `WINDOWS_CERTIFICATE` (base64) and
`WINDOWS_CERTIFICATE_PASSWORD` and the exe is signed with a timestamp;
certificates issued since mid-2023 must live on hardware or a cloud signing
service (Azure Trusted Signing, SignPath — free for open-source projects),
which would replace `packaging/desktop/sign_windows.ps1`. An OV certificate
still shows the SmartScreen warning until the publisher has built up
reputation; an EV certificate does not.
