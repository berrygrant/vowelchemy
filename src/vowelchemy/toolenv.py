"""Find MFA / new-fave outside the app's own Python environment.

Students launch Vowelchemy by double-clicking a launcher, which installs the
app into a private virtual environment.  The acquisition tools can't simply
ride along in that environment:

* **MFA is conda-only.** ``pip install montreal-forced-aligner`` appears to
  succeed and then fails at run time with ``No module named '_kalpy'`` — the
  Kaldi bindings it needs are published through conda-forge, not PyPI.  So an
  aligner lives in a *separate* conda/mamba environment
  (``mamba install -c conda-forge montreal-forced-aligner``).
* **new-fave is pip-installable** (``pip install new-fave``, providing
  ``fave-extract``), so the app can install it on request — see
  :func:`pip_install_plan`.

This module therefore does two things: it *discovers* conda/mamba environments
that already contain these tools, and it resolves tool executables from a
chosen environment so the app can borrow them without anyone activating
anything.  It also searches the app's own environment, which is **not** on
``PATH`` when a launcher starts the server without activating the venv.

Selection is remembered in ``~/.vowelchemy/settings.json`` (override the
directory with ``VOWELCHEMY_HOME``); ``VOWELCHEMY_TOOL_ENV`` wins over the
stored value, which suits lab machines and containers.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

# Tool key -> the executable that proves the tool is present.
TOOL_EXECUTABLES = {"mfa": "mfa", "newfave": "fave-extract"}

# Tools the app can install into its own environment, and their PyPI names.
# MFA is deliberately absent: pip cannot deliver a working aligner.
PIP_INSTALLABLE = {"newfave": "new-fave"}

MFA_CONDA_HINT = (
    "MFA needs conda/mamba — pip cannot install a working aligner (its Kaldi\n"
    "bindings ship only through conda-forge). In a terminal:\n"
    "  mamba create -n aligner -c conda-forge montreal-forced-aligner\n"
    "  mamba activate aligner\n"
    "  mfa model download acoustic english_us_arpa\n"
    "  mfa model download dictionary english_us_arpa\n"
    "Then point Vowelchemy at that environment (Tools ▸ Set up tools) — you\n"
    "never have to activate it again."
)

# Directory names that commonly hold conda/mamba installations.
_CONDA_ROOTS = (
    "miniforge3", "mambaforge", "miniconda3", "anaconda3", "micromamba",
    "miniforge", "conda",
)


# --------------------------------------------------------------------------- #
# Settings
# --------------------------------------------------------------------------- #
def vowelchemy_home() -> Path:
    root = os.environ.get("VOWELCHEMY_HOME")
    return Path(root).expanduser() if root else Path.home() / ".vowelchemy"


def settings_path() -> Path:
    return vowelchemy_home() / "settings.json"


def read_settings() -> dict:
    try:
        return json.loads(settings_path().read_text())
    except (OSError, ValueError):
        return {}


def write_settings(settings: dict) -> None:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=2))


# --------------------------------------------------------------------------- #
# Environments
# --------------------------------------------------------------------------- #
@dataclass
class ToolEnvironment:
    """An environment prefix (or bare folder) that holds one or more tools."""

    path: str
    name: str
    tools: dict[str, str] = field(default_factory=dict)
    source: str = "conda"

    def as_dict(self) -> dict:
        return {"path": self.path, "name": self.name, "source": self.source,
                "tools": sorted(self.tools)}


def bin_dirs(prefix: str | os.PathLike) -> list[Path]:
    """Executable directories inside an environment prefix.

    Covers POSIX (``bin``) and Windows (``Scripts`` plus ``Library/bin``, where
    conda keeps DLLs). If the caller points straight at a directory of
    executables, that directory is used as-is.
    """
    p = Path(prefix).expanduser()
    dirs = [d for d in (p / "bin", p / "Scripts", p / "Library" / "bin") if d.is_dir()]
    if not dirs and p.is_dir():
        dirs = [p]
    return dirs


def tools_in(prefix: str | os.PathLike) -> dict[str, str]:
    """Map tool key -> executable path for the tools present in ``prefix``."""
    dirs = bin_dirs(prefix)
    if not dirs:
        return {}
    search = os.pathsep.join(str(d) for d in dirs)
    found: dict[str, str] = {}
    for key, exe in TOOL_EXECUTABLES.items():
        hit = shutil.which(exe, path=search)
        if hit:
            found[key] = hit
    return found


def _candidate_prefixes() -> list[Path]:
    """Plausible environment prefixes, most-likely first, de-duplicated."""
    out: list[Path] = []

    def add(p: Optional[str | os.PathLike]) -> None:
        if not p:
            return
        path = Path(p).expanduser()
        if path.is_dir() and path not in out:
            out.append(path)

    # The environment the server itself runs in, and any active conda env.
    for var in ("CONDA_PREFIX", "CONDA_PREFIX_1", "MAMBA_ROOT_PREFIX"):
        add(os.environ.get(var))
    if not getattr(sys, "frozen", False):
        add(sys.prefix)

    roots: list[Path] = []
    home = Path.home()
    for name in _CONDA_ROOTS:
        roots += [home / name, Path("/opt") / name, Path("/usr/local") / name]
    roots.append(home / "opt" / "anaconda3")
    # Homebrew casks on macOS.
    roots.append(Path("/opt/homebrew/Caskroom/miniforge/base"))
    roots.append(home / ".conda")

    for root in roots:
        if not root.is_dir():
            continue
        add(root)  # the base environment itself
        envs = root / "envs"
        if envs.is_dir():
            try:
                for child in sorted(envs.iterdir()):
                    add(child)
            except OSError:
                continue
    return out


def _conda_cli_prefixes(timeout: float = 15.0) -> list[Path]:
    """Ask conda/mamba where its environments live (best effort)."""
    for exe in ("conda", "mamba", "micromamba"):
        binary = shutil.which(exe)
        if not binary:
            continue
        try:
            res = subprocess.run([binary, "info", "--envs", "--json"],
                                 capture_output=True, text=True, timeout=timeout)
            data = json.loads(res.stdout)
        except (subprocess.SubprocessError, OSError, ValueError):
            continue
        prefixes = data.get("envs") or []
        return [Path(p) for p in prefixes if isinstance(p, str)]
    return []


def discover_environments(use_conda_cli: bool = True) -> list[ToolEnvironment]:
    """Environments that contain MFA and/or new-fave.

    Scans well-known conda/mamba locations plus the app's own environment, and
    (optionally) asks the conda CLI — which finds environments in custom
    locations that a filesystem scan would miss.
    """
    prefixes = _candidate_prefixes()
    if use_conda_cli:
        for extra in _conda_cli_prefixes():
            if extra.is_dir() and extra not in prefixes:
                prefixes.append(extra)

    selected = selected_prefix()
    found: list[ToolEnvironment] = []
    seen: set[Path] = set()
    for prefix in prefixes:
        resolved = prefix.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        tools = tools_in(prefix)
        if not tools:
            continue
        source = "app" if (not getattr(sys, "frozen", False)
                           and resolved == Path(sys.prefix).resolve()) else "conda"
        found.append(ToolEnvironment(path=str(prefix), name=prefix.name,
                                     tools=tools, source=source))

    def rank(env: ToolEnvironment) -> tuple:
        is_selected = selected is not None and Path(env.path).resolve() == selected.resolve()
        return (not is_selected, "mfa" not in env.tools, env.name.lower())

    return sorted(found, key=rank)


# --------------------------------------------------------------------------- #
# Selection + resolution
# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
# Version-probe cache
# --------------------------------------------------------------------------- #
# Probing a tool means starting it: `fave-extract --version` takes ~2s and MFA
# is slower still. The sidebar polls status continuously, so without a cache the
# whole app crawls on exactly the machines that *have* the tools installed.
_VERSION_CACHE: dict[str, tuple[float, Optional[str]]] = {}
_VERSION_TTL = 600.0


def cached_version(key: str, probe: "Callable[[], Optional[str]]") -> Optional[str]:
    """Return a probed version, re-running ``probe`` at most every 10 minutes."""
    import time

    hit = _VERSION_CACHE.get(key)
    now = time.time()
    if hit is not None and (now - hit[0]) < _VERSION_TTL:
        return hit[1]
    value = probe()
    _VERSION_CACHE[key] = (now, value)
    return value


_INFLIGHT: set[str] = set()


def cached_version_async(key: str, probe: "Callable[[], Optional[str]]") -> Optional[str]:
    """Cached version if known; otherwise probe in the background and return None.

    Availability must never wait on a tool launching. Callers report the tool as
    present (the executable exists) with an unknown version, and the version
    appears on the next poll a moment later.
    """
    import threading
    import time

    hit = _VERSION_CACHE.get(key)
    if hit is not None and (time.time() - hit[0]) < _VERSION_TTL:
        return hit[1]
    if key not in _INFLIGHT:
        _INFLIGHT.add(key)

        def run() -> None:
            try:
                value = probe()
            except Exception:
                value = None
            _VERSION_CACHE[key] = (time.time(), value)
            _INFLIGHT.discard(key)

        threading.Thread(target=run, daemon=True).start()
    return hit[1] if hit is not None else None


def invalidate_caches() -> None:
    """Forget probed versions (after switching environments or installing)."""
    _VERSION_CACHE.clear()
    _INFLIGHT.clear()


def selected_prefix() -> Optional[Path]:
    """The environment the user chose, if any (env var wins over settings)."""
    override = os.environ.get("VOWELCHEMY_TOOL_ENV")
    if override:
        return Path(override).expanduser()
    stored = read_settings().get("tool_env")
    return Path(stored).expanduser() if stored else None


def set_selected_prefix(path: Optional[str]) -> dict[str, str]:
    """Remember (or clear, with ``None``) the environment to borrow tools from.

    Returns the tools found there. Raises ``ValueError`` if the path holds
    neither tool, so the UI can explain rather than silently store a dud.
    """
    settings = read_settings()
    if not path:
        settings.pop("tool_env", None)
        write_settings(settings)
        invalidate_caches()
        return {}
    prefix = Path(path).expanduser()
    if not prefix.is_dir():
        raise ValueError(f"No such folder: {prefix}")
    tools = tools_in(prefix)
    if not tools:
        wanted = " or ".join(sorted(TOOL_EXECUTABLES.values()))
        raise ValueError(
            f"{prefix} doesn't contain {wanted}. Pick the environment folder "
            "itself (the one with a bin/ or Scripts/ inside)."
        )
    settings["tool_env"] = str(prefix)
    write_settings(settings)
    invalidate_caches()  # probe the new environment's tools fresh
    return tools


def search_dirs() -> list[Path]:
    """Directories searched for tools before falling back to ``PATH``."""
    dirs: list[Path] = []
    selected = selected_prefix()
    if selected:
        dirs += bin_dirs(selected)
    # A launcher starts the server without activating its venv, so the venv's
    # own bin/Scripts directory is not on PATH — look there too.
    if not getattr(sys, "frozen", False):
        dirs.append(Path(sys.executable).parent)
    return [d for d in dirs if d.is_dir()]


def resolve(executable: str) -> Optional[str]:
    """``shutil.which`` that also looks in the chosen and app environments."""
    dirs = search_dirs()
    if dirs:
        hit = shutil.which(executable, path=os.pathsep.join(str(d) for d in dirs))
        if hit:
            return hit
    return shutil.which(executable)


def subprocess_env(base: Optional[dict] = None) -> dict:
    """Environment for running a borrowed tool.

    Prepending the environment's directories to ``PATH`` is what lets a conda
    tool run un-activated: helper executables resolve, and on Windows the DLLs
    in ``Library\\bin`` are found.
    """
    env = dict(base if base is not None else os.environ)
    dirs = [str(d) for d in search_dirs()]
    if dirs:
        existing = env.get("PATH", "")
        env["PATH"] = os.pathsep.join(dirs + ([existing] if existing else []))
    return env


# --------------------------------------------------------------------------- #
# Installing what can be installed
# --------------------------------------------------------------------------- #
def env_python(prefix: str | os.PathLike) -> Optional[str]:
    """The interpreter inside an environment prefix, if there is one."""
    for name in ("python3", "python", "python.exe"):
        for d in bin_dirs(prefix):
            candidate = d / name
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return str(candidate)
    return None


def _python_version(executable: str) -> Optional[tuple[int, int]]:
    try:
        res = subprocess.run(
            [executable, "-c", "import sys; print(sys.version_info[0], sys.version_info[1])"],
            capture_output=True, text=True, timeout=20,
        )
        major, minor = res.stdout.split()[:2]
        return int(major), int(minor)
    except (subprocess.SubprocessError, OSError, ValueError, IndexError):
        return None


def pip_install_plan(
    tool: str, prefix: Optional[str | os.PathLike] = None
) -> tuple[Optional[list[str]], str]:
    """Command to install ``tool``, or ``None`` plus the reason why not.

    With ``prefix``, installs into *that* environment (which is how a packaged
    app — with no pip of its own — can still equip a conda environment the user
    already picked). Without it, installs into the app's own environment.
    """
    package = PIP_INSTALLABLE.get(tool)
    if package is None:
        if tool == "mfa":
            return None, ("MFA can't be installed with pip — its Kaldi bindings come "
                          "from conda-forge only. " + MFA_CONDA_HINT)
        return None, f"Unknown tool: {tool}"

    if prefix is not None:
        python = env_python(prefix)
        if python is None:
            return None, f"No Python interpreter found in {prefix}."
        version = _python_version(python)
        if version is not None and version < (3, 10):
            return None, (f"{Path(prefix).name} runs Python {version[0]}.{version[1]}, "
                          f"but {package} needs 3.10 or newer.")
        return [python, "-m", "pip", "install", package], ""

    if getattr(sys, "frozen", False):
        return None, ("The downloadable app can't install Python packages into itself. "
                      "Pick a conda/mamba environment above and Vowelchemy can install "
                      f"{package} into that instead — or create one with: "
                      "mamba create -n extract -c conda-forge python=3.12")
    if sys.version_info < (3, 10):
        current = f"{sys.version_info.major}.{sys.version_info.minor}"
        return None, (f"{package} needs Python 3.10 or newer; this app is running on "
                      f"{current}. Pick an environment above with a newer Python and "
                      "Vowelchemy can install it there instead.")
    return [sys.executable, "-m", "pip", "install", package], ""


def app_info() -> dict:
    """What code is actually running — the answer to 'why is my fix missing?'."""
    from . import __version__, webui_dir

    return {
        "version": __version__,
        "location": str(Path(__file__).resolve().parent),
        "python": sys.version.split()[0],
        "executable": sys.executable,
        "frozen": bool(getattr(sys, "frozen", False)),
        "webui": str(webui_dir()) if webui_dir() else None,
    }
