import time

from vowelchemy.jobs import JobManager, ProgressTracker


def test_progress_tracker_phase_and_percent():
    t = ProgressTracker()
    t.update("Setting up corpus")
    t.update("Generating MFCCs")
    t.update(" 45%|####     | 45/100 [00:10<00:12]")
    assert t.phase == "Generating MFCCs"
    assert t.percent == 45.0


def test_progress_tracker_fraction_and_ansi_strip():
    t = ProgressTracker()
    t.update("Aligning")
    t.update("\x1b[32m 12/48 files done\x1b[0m")
    assert t.phase == "Aligning"
    assert t.percent == 25.0


def test_new_phase_resets_percent():
    t = ProgressTracker()
    t.update("Generating MFCCs")
    t.update(" 90%")
    assert t.percent == 90.0
    t.update("Aligning")
    assert t.percent is None


def _run_to_completion(jm, job):
    for _ in range(300):
        snap = jm.snapshot(job.id)
        if snap["status"] != "running":
            return snap
        time.sleep(0.01)
    return jm.snapshot(job.id)


def test_job_manager_success():
    jm = JobManager()

    def target(emit):
        emit("Extracting")
        emit(" 50%")
        return {"ok": True, "n": 3}

    snap = _run_to_completion(jm, jm.start("test", target))
    assert snap["status"] == "done"
    assert snap["result"] == {"ok": True, "n": 3}
    assert snap["percent"] == 100.0


def test_job_manager_error_is_captured():
    jm = JobManager()

    def bad(emit):
        raise RuntimeError("boom")

    snap = _run_to_completion(jm, jm.start("test", bad))
    assert snap["status"] == "error"
    assert "boom" in snap["error"]


def test_snapshot_unknown_returns_none():
    assert JobManager().snapshot("does-not-exist") is None
