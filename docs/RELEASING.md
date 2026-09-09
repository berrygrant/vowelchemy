# Releasing Vowelchemy

Three commands. The version is declared in four files, so never edit it by
hand — the script rewrites all of them and the release build checks them.

```bash
python scripts/bump_version.py 0.3.3        # pyproject.toml, CITATION.cff (+ date), __init__.py, README
git commit -am "Bump version to 0.3.3"
git tag v0.3.3 && git push origin main v0.3.3
```

The tag triggers **Build desktop app** (`.github/workflows/build-app.yml`),
which:

1. refuses to build if the tag does not match the declared version
   (`python scripts/bump_version.py --check v0.3.3`);
2. builds `Vowelchemy-macOS.zip` and `Vowelchemy-Windows.zip` with PyInstaller;
3. creates the GitHub Release for the tag and attaches both zips.

Write the release notes on that GitHub Release. The in-app update check
(`src/vowelchemy/updates.py`) reads GitHub's *latest release*, so a plain
tag without a release is invisible to running copies — the workflow's
release is what makes older installs show "0.3.3 available".

`tests/test_version.py` fails CI whenever the four declarations disagree,
and `python scripts/bump_version.py --check` says which one is off.

Version numbers: `MAJOR.MINOR.PATCH`. A change to the metrics' column names
or defaults (anything that changes numbers or CSVs users already have) is at
least a MINOR bump.
