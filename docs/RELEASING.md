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
