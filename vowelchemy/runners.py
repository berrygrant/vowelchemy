"""Small subprocess helper for orchestrating external CLI tools.

MFA and new-fave are heavy command-line programs installed in their own
environments; vowelchemy shells out to them and streams their output back so
the UI can show live progress.  Keeping this in one place means the alignment
and extraction wrappers share identical process-handling and error semantics.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Callable, Optional, Sequence


@dataclass
class CommandResult:
    args: list[str]
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out

    @property
    def command(self) -> str:
        return " ".join(self.args)


@dataclass
class ToolStatus:
    """Whether an external tool is installed and, if so, its version string."""

    name: str
    path: Optional[str]
    version: Optional[str] = None
    install_hint: str = ""

    @property
    def available(self) -> bool:
        return self.path is not None


def which(executable: str) -> Optional[str]:
    return shutil.which(executable)


def run_streaming(
    args: Sequence[str],
    on_output: Optional[Callable[[str], None]] = None,
    cwd: Optional[str] = None,
    env: Optional[dict] = None,
    timeout: Optional[float] = None,
) -> CommandResult:
    """Run ``args``, streaming merged stdout/stderr line-by-line to ``on_output``.

    Returns a :class:`CommandResult` capturing the full output.  Never raises on
    a non-zero exit — callers inspect ``result.ok`` — but does surface a missing
    executable as a ``FileNotFoundError``-derived returncode of 127.
    """
    args = [str(a) for a in args]
    full_env = {**os.environ, **(env or {})}
    lines: list[str] = []
    try:
        proc = subprocess.Popen(
            args,
            cwd=cwd,
            env=full_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except FileNotFoundError as exc:
        msg = f"Executable not found: {args[0]} ({exc})"
        if on_output:
            on_output(msg)
        return CommandResult(args, 127, "", msg)

    timed_out = False
    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            line = line.rstrip("\n")
            lines.append(line)
            if on_output:
                on_output(line)
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        timed_out = True
        if on_output:
            on_output(f"[timed out after {timeout}s]")
    output = "\n".join(lines)
    return CommandResult(args, proc.returncode if proc.returncode is not None else -1,
                         output, output, timed_out=timed_out)


def probe_version(executable: str, version_args: Sequence[str] = ("version",)) -> Optional[str]:
    """Best-effort version probe for a CLI tool."""
    path = which(executable)
    if not path:
        return None
    for candidate in (list(version_args), ["--version"], ["-V"]):
        try:
            res = subprocess.run(
                [executable, *candidate],
                capture_output=True, text=True, timeout=30,
            )
        except (subprocess.SubprocessError, OSError):
            continue
        out = (res.stdout or res.stderr).strip()
        if res.returncode == 0 and out:
            return out.splitlines()[0].strip()
    return path  # installed but version unknown
