"""Background jobs with live progress for long-running external tools.

Force-alignment (MFA) and extraction (new-fave) can run for many minutes, so the
API launches them in a worker thread and the front-end polls for progress.  MFA
and new-fave print tqdm/rich-style progress that updates in place with carriage
returns; Python's universal-newline reader already splits those updates into
separate lines, and :class:`ProgressTracker` turns them into a
``(phase, percent)`` pair the UI can show as a progress bar.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from typing import Callable, Optional
from uuid import uuid4

_ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
_PCT = re.compile(r"(\d{1,3})\s*%")
_FRAC = re.compile(r"\b(\d+)\s*/\s*(\d+)\b")

# Recognised phase labels from MFA (3.x) and new-fave output. Order doesn't
# matter; the most recent match wins.
_PHASE_KEYWORDS = (
    "Setting up corpus", "Loading corpus", "Creating corpus", "Parsing",
    "Generating MFCCs", "Calculating CMVN", "Compiling training graphs",
    "Generating alignments", "Performing first-pass alignment",
    "Performing second-pass alignment", "Calculating fMLLR", "Aligning",
    "Exporting", "Validating", "Analyzing", "Extracting", "Measuring",
    "Processing", "Optimizing", "Tracking",
)


class ProgressTracker:
    """Incrementally derive ``(phase, percent)`` from streamed output lines."""

    def __init__(self) -> None:
        self.phase: Optional[str] = None
        self.percent: Optional[float] = None

    def update(self, line: str) -> None:
        clean = _ANSI.sub("", line).strip()
        if not clean:
            return
        lowered = clean.lower()
        for kw in _PHASE_KEYWORDS:
            if kw.lower() in lowered:
                if self.phase != kw:
                    self.phase = kw
                    self.percent = None  # a new phase restarts its own bar
                break
        pct = _PCT.search(clean)
        if pct:
            val = int(pct.group(1))
            if 0 <= val <= 100:
                self.percent = float(val)
            return
        frac = _FRAC.search(clean)
        if frac:
            num, den = int(frac.group(1)), int(frac.group(2))
            if den > 0:
                self.percent = min(100.0, round(100.0 * num / den, 1))


@dataclass
class Job:
    id: str
    kind: str
    status: str = "running"  # running | done | error
    phase: Optional[str] = None
    percent: Optional[float] = None
    log: list[str] = field(default_factory=list)
    result: Optional[dict] = None
    error: Optional[str] = None


class JobManager:
    """Runs callables on worker threads, tracking progress and results."""

    def __init__(self, max_log: int = 800) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._max_log = max_log

    def start(self, kind: str, target: Callable[[Callable[[str], None]], dict]) -> Job:
        """Start ``target(emit)`` in a thread; ``emit(line)`` feeds progress."""
        job = Job(id=uuid4().hex[:12], kind=kind)
        with self._lock:
            self._jobs[job.id] = job
        tracker = ProgressTracker()

        def emit(line: str) -> None:
            tracker.update(line)
            with self._lock:
                job.log.append(line)
                if len(job.log) > self._max_log:
                    del job.log[: -self._max_log]
                job.phase = tracker.phase
                job.percent = tracker.percent

        def run() -> None:
            try:
                result = target(emit)
                with self._lock:
                    job.result = result or {}
                    job.status = "done"
                    job.percent = 100.0
            except Exception as exc:  # noqa: BLE001 - surfaced to the UI
                with self._lock:
                    job.error = str(exc)
                    job.status = "error"

        threading.Thread(target=run, daemon=True).start()
        return job

    def snapshot(self, job_id: str, log_tail: int = 60) -> Optional[dict]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            return {
                "id": job.id,
                "kind": job.kind,
                "status": job.status,
                "phase": job.phase,
                "percent": job.percent,
                "log": "\n".join(job.log[-log_tail:]),
                "result": job.result,
                "error": job.error,
            }
