"""Tests for tools/multi_task_mux.py Windows-compatible tmux-style multi-task session runner."""

from __future__ import annotations

import json
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

import tools.multi_task_mux as mux_mod
from tools.multi_task_mux import _pump_pending_slots, inspect_session, kill_session, main as mux_main


def test_multi_task_mux_start_auto_advances_queued_jobs_and_tail(tmp_path: Path, capsys) -> None:
    manifest = tmp_path / "jobs.json"
    out_dir = tmp_path / "outputs"
    out_dir.mkdir()
    py = sys.executable

    jobs = {
        "panes": [
            {
                "id": f"job_{i}",
                "command": [
                    py,
                    "-c",
                    (
                        "import pathlib, time; "
                        "time.sleep(0.2); "
                        f"pathlib.Path({str(out_dir / f'r_{i}.txt')!r}).write_text('ok_{i}', encoding='utf-8'); "
                        f"print('finished_job_{i}')"
                    ),
                ],
            }
            for i in range(4)
        ]
    }
    manifest.write_text(json.dumps(jobs), encoding="utf-8")
    base_dir = tmp_path / "mux_base"

    rc_start = mux_main(
        [
            "--base-dir",
            str(base_dir),
            "start",
            "--session",
            "m31_batch",
            "--manifest",
            str(manifest),
            "--max-concurrent",
            "2",
        ]
    )
    assert rc_start == 0
    snap_start = json.loads(capsys.readouterr().out)
    assert snap_start["counts"]["running"] <= 2
    assert snap_start["supervisor_pid"] is not None

    # Verify background supervisor automatically advances queued jobs even WITHOUT calling wait() or status --pump
    deadline = time.monotonic() + 15.0
    snap_done = inspect_session(base_dir, "m31_batch")
    while not snap_done["all_finished"] and time.monotonic() < deadline:
        time.sleep(0.2)
        snap_done = inspect_session(base_dir, "m31_batch")

    assert snap_done["all_finished"] is True
    assert snap_done["counts"]["done"] == 4
    assert snap_done["counts"]["failed"] == 0

    for i in range(4):
        assert (out_dir / f"r_{i}.txt").read_text(encoding="utf-8") == f"ok_{i}"

    rc_tail = mux_main(
        ["--base-dir", str(base_dir), "tail", "--session", "m31_batch", "--pane", "job_2", "--lines", "5"]
    )
    assert rc_tail == 0
    assert "finished_job_2" in capsys.readouterr().out


def test_multi_task_mux_kill_cancels_queued_panes_and_concurrent_pump_is_atomic(tmp_path: Path, capsys) -> None:
    manifest = tmp_path / "kill_jobs.json"
    marker = tmp_path / "should_never_run.txt"
    py = sys.executable
    manifest.write_text(
        json.dumps(
            {
                "panes": [
                    {"id": "sleeper", "command": [py, "-c", "import time; print('sleeping', flush=True); time.sleep(30)"]},
                    {
                        "id": "queued_job",
                        "command": [
                            py,
                            "-c",
                            f"import pathlib; pathlib.Path({str(marker)!r}).write_text('RAN', encoding='utf-8')",
                        ],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    base_dir = tmp_path / "mux_base"
    assert (
        mux_main(
            [
                "--base-dir",
                str(base_dir),
                "start",
                "--session",
                "ktest",
                "--manifest",
                str(manifest),
                "--max-concurrent",
                "1",
                "--no-supervisor",
            ]
        )
        == 0
    )
    capsys.readouterr()

    time.sleep(0.3)
    kill_res = kill_session(base_dir, "ktest")
    assert set(kill_res["killed"]) == {"sleeper", "queued_job"}

    # Even pumping or waiting afterward MUST NOT launch previously cancelled queued_job
    rc_wait = mux_main(["--base-dir", str(base_dir), "wait", "--session", "ktest", "--timeout", "5"])
    assert rc_wait == 1
    capsys.readouterr()
    assert not marker.exists()

    snap = inspect_session(base_dir, "ktest")
    assert snap["stopped"] is True
    assert snap["counts"]["failed"] == 2

    # Concurrent _pump_pending_slots on a 1-slot 2-job session must spawn each job exactly once
    count_file = tmp_path / "spawn_counts.txt"
    conc_manifest = tmp_path / "conc_jobs.json"
    conc_manifest.write_text(
        json.dumps(
            {
                "panes": [
                    {
                        "id": "p1",
                        "command": [
                            py,
                            "-c",
                            f"import time; open({str(count_file)!r}, 'a').write('p1\\n'); time.sleep(0.25)",
                        ],
                    },
                    {
                        "id": "p2",
                        "command": [
                            py,
                            "-c",
                            f"import time; open({str(count_file)!r}, 'a').write('p2\\n'); time.sleep(0.15)",
                        ],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    assert (
        mux_main(
            [
                "--base-dir",
                str(base_dir),
                "start",
                "--session",
                "conclock",
                "--manifest",
                str(conc_manifest),
                "--max-concurrent",
                "1",
                "--no-supervisor",
            ]
        )
        == 0
    )
    capsys.readouterr()
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: _pump_pending_slots(base_dir, "conclock"), range(4)))
    assert mux_main(["--base-dir", str(base_dir), "wait", "--session", "conclock", "--timeout", "15"]) == 0
    capsys.readouterr()
    lines = sorted(count_file.read_text(encoding="utf-8").splitlines())
    assert lines == ["p1", "p2"]

    # --replace on an active session must cancel prior panes safely and run the new manifest
    rep_manifest = tmp_path / "rep_jobs.json"
    rep_manifest.write_text(
        json.dumps({"panes": [{"id": "fresh", "command": [py, "-c", "print('replaced_ok')"]}]}),
        encoding="utf-8",
    )
    assert (
        mux_main(
            [
                "--base-dir",
                str(base_dir),
                "start",
                "--session",
                "ktest",
                "--manifest",
                str(rep_manifest),
                "--replace",
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert mux_main(["--base-dir", str(base_dir), "wait", "--session", "ktest", "--timeout", "10"]) == 0
    capsys.readouterr()
    assert inspect_session(base_dir, "ktest")["counts"]["done"] == 1
    assert not marker.exists()

    # Deterministic check: if cancelled=True is recorded before _run-pane executes, child never spawns
    race_manifest = tmp_path / "race_jobs.json"
    race_marker = tmp_path / "race_should_not_run.txt"
    race_manifest.write_text(
        json.dumps(
            {
                "panes": [
                    {
                        "id": "r1",
                        "command": [
                            py,
                            "-c",
                            f"import pathlib; pathlib.Path({str(race_marker)!r}).write_text('SPAWNED', encoding='utf-8')",
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    sess_dir = base_dir / "racecheck"
    (sess_dir / "panes").mkdir(parents=True)
    (sess_dir / "logs").mkdir(parents=True)
    (sess_dir / "session.json").write_text(
        json.dumps({"session": "racecheck", "max_concurrent": 1, "stopped": False, "panes": json.loads(race_manifest.read_text())["panes"]}),
        encoding="utf-8",
    )
    (sess_dir / "panes" / "r1.spec.json").write_text(
        json.dumps({"id": "r1", "command": json.loads(race_manifest.read_text())["panes"][0]["command"], "cwd": str(tmp_path), "env": {}}),
        encoding="utf-8",
    )
    (sess_dir / "panes" / "r1.json").write_text(
        json.dumps({"id": "r1", "status": "failed", "cancelled": True}),
        encoding="utf-8",
    )
    assert mux_main(["--base-dir", str(base_dir), "_run-pane", "--session", "racecheck", "--pane", "r1"]) == -15
    assert not race_marker.exists()


def test_multi_task_mux_replace_rejects_cleanup_failure_and_ignores_stale_run_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    py = sys.executable
    base_dir = tmp_path / "mux_base"
    manifest = tmp_path / "rep_jobs.json"
    manifest.write_text(
        json.dumps({"panes": [{"id": "p1", "command": [py, "-c", "print('v1')"]}]}),
        encoding="utf-8",
    )
    assert (
        mux_main(
            [
                "--base-dir",
                str(base_dir),
                "start",
                "--session",
                "repfail",
                "--manifest",
                str(manifest),
                "--no-supervisor",
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert mux_main(["--base-dir", str(base_dir), "wait", "--session", "repfail", "--timeout", "10"]) == 0
    capsys.readouterr()

    orig_rmtree = shutil.rmtree
    monkeypatch.setattr(mux_mod.time, "sleep", lambda _s: None)

    def _fail_rmtree(path, *args, **kwargs):
        raise PermissionError(f"locked handle at {path}")

    monkeypatch.setattr(mux_mod.shutil, "rmtree", _fail_rmtree)
    with pytest.raises(RuntimeError, match="Failed to remove stale session artifacts"):
        mux_main(
            [
                "--base-dir",
                str(base_dir),
                "start",
                "--session",
                "repfail",
                "--manifest",
                str(manifest),
                "--replace",
                "--no-supervisor",
            ]
        )
    monkeypatch.setattr(mux_mod.shutil, "rmtree", orig_rmtree)

    # Also reject replacement if an old process survives termination
    (base_dir / "repfail" / "session.json").write_text(
        json.dumps(
            {
                "session": "repfail",
                "run_id": "old_epoch",
                "max_concurrent": 1,
                "stopped": False,
                "panes": [{"id": "p1", "command": [py, "-c", "print('x')"]}],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(mux_mod, "_terminate_pids_parallel", lambda pids, wait_timeout=3.0: [999999])
    orig_inspect = mux_mod._inspect_session_unlocked

    def _fake_inspect(sess_dir, session):
        snap = orig_inspect(sess_dir, session)
        snap["panes"][0]["status"] = "running"
        snap["panes"][0]["pid"] = 999999
        return snap

    monkeypatch.setattr(mux_mod, "_inspect_session_unlocked", _fake_inspect)
    with pytest.raises(RuntimeError, match="processes remained alive"):
        mux_main(
            [
                "--base-dir",
                str(base_dir),
                "start",
                "--session",
                "repfail",
                "--manifest",
                str(manifest),
                "--replace",
                "--no-supervisor",
            ]
        )
    monkeypatch.undo()

    # Stale wrapper with mismatched run_id must exit -15 without touching child or new state
    stale_marker = tmp_path / "stale_epoch_ran.txt"
    sess_dir = base_dir / "epochtest"
    (sess_dir / "panes").mkdir(parents=True)
    (sess_dir / "logs").mkdir(parents=True)
    stale_cmd = [
        py,
        "-c",
        f"import pathlib; pathlib.Path({str(stale_marker)!r}).write_text('BAD', encoding='utf-8')",
    ]
    (sess_dir / "session.json").write_text(
        json.dumps(
            {
                "session": "epochtest",
                "run_id": "new_epoch_2",
                "max_concurrent": 1,
                "stopped": False,
                "panes": [{"id": "p1", "command": stale_cmd}],
            }
        ),
        encoding="utf-8",
    )
    (sess_dir / "panes" / "p1.spec.json").write_text(
        json.dumps({"id": "p1", "run_id": "old_epoch_1", "command": stale_cmd, "cwd": str(tmp_path), "env": {}}),
        encoding="utf-8",
    )
    assert mux_main(["--base-dir", str(base_dir), "_run-pane", "--session", "epochtest", "--pane", "p1"]) == -15
    assert not stale_marker.exists()

    # Even if --replace already rewrote BOTH session.json and p1.spec.json with new_epoch_2,
    # a delayed wrapper carrying immutable --run-id old_epoch_1 must still exit -15 cleanly.
    (sess_dir / "panes" / "p1.spec.json").write_text(
        json.dumps({"id": "p1", "run_id": "new_epoch_2", "command": stale_cmd, "cwd": str(tmp_path), "env": {}}),
        encoding="utf-8",
    )
    assert (
        mux_main(
            [
                "--base-dir",
                str(base_dir),
                "_run-pane",
                "--session",
                "epochtest",
                "--pane",
                "p1",
                "--run-id",
                "old_epoch_1",
            ]
        )
        == -15
    )
    assert not stale_marker.exists()


def test_multi_task_mux_supervisor_survives_lock_timeout_and_kill_does_not_hold_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    py = sys.executable
    base_dir = tmp_path / "mux_base"
    out_dir = tmp_path / "sup_out"
    out_dir.mkdir()
    manifest = tmp_path / "sup_jobs.json"
    manifest.write_text(
        json.dumps(
            {
                "panes": [
                    {
                        "id": f"j{i}",
                        "command": [
                            py,
                            "-c",
                            f"import pathlib, time; time.sleep(0.1); pathlib.Path({str(out_dir / f'j{i}.txt')!r}).write_text('ok', encoding='utf-8')",
                        ],
                    }
                    for i in range(2)
                ]
            }
        ),
        encoding="utf-8",
    )
    assert (
        mux_main(
            [
                "--base-dir",
                str(base_dir),
                "start",
                "--session",
                "suptime",
                "--manifest",
                str(manifest),
                "--max-concurrent",
                "1",
                "--no-supervisor",
            ]
        )
        == 0
    )
    capsys.readouterr()

    real_pump = mux_mod._pump_pending_slots
    calls = {"n": 0}

    def _flaky_pump(bd: Path, sess: str):
        calls["n"] += 1
        if calls["n"] <= 2:
            raise TimeoutError("transient lock contention")
        return real_pump(bd, sess)

    monkeypatch.setattr(mux_mod, "_pump_pending_slots", _flaky_pump)
    assert mux_main(["--base-dir", str(base_dir), "_pump-daemon", "--session", "suptime"]) == 0
    snap = inspect_session(base_dir, "suptime")
    assert snap["all_finished"] is True
    assert snap["counts"]["done"] == 2
    assert calls["n"] >= 3
    monkeypatch.undo()

    # Verify kill_session releases .session.lock before calling _terminate_pids_parallel
    kill_manifest = tmp_path / "kill_fast.json"
    kill_manifest.write_text(
        json.dumps({"panes": [{"id": "s1", "command": [py, "-c", "import time; time.sleep(10)"]}]}),
        encoding="utf-8",
    )
    assert (
        mux_main(
            [
                "--base-dir",
                str(base_dir),
                "start",
                "--session",
                "killlock",
                "--manifest",
                str(kill_manifest),
                "--no-supervisor",
            ]
        )
        == 0
    )
    capsys.readouterr()
    observed_during_kill: dict[str, bool] = {"lock_free": False}
    real_term = mux_mod._terminate_pids_parallel

    def _inspecting_term(pids, wait_timeout=3.0):
        with ThreadPoolExecutor(max_workers=1) as pool:
            snap_inner = pool.submit(inspect_session, base_dir, "killlock").result(timeout=2.0)
            observed_during_kill["lock_free"] = snap_inner["stopped"] is True
        return real_term(pids, wait_timeout=wait_timeout)

    monkeypatch.setattr(mux_mod, "_terminate_pids_parallel", _inspecting_term)
    res = kill_session(base_dir, "killlock")
    assert observed_during_kill["lock_free"] is True
    assert res["unkilled_pids"] == []


def test_multi_task_mux_resumable_exit_code_auto_resumes(tmp_path: Path, capsys) -> None:
    manifest = tmp_path / "resume_jobs.json"
    marker = tmp_path / "attempt_count.txt"
    py = sys.executable
    script = (
        f"import pathlib, sys; p = pathlib.Path({str(marker)!r}); "
        "n = int(p.read_text()) + 1 if p.exists() else 1; "
        "p.write_text(str(n), encoding='utf-8'); "
        "sys.exit(75 if n == 1 else 0)"
    )
    manifest.write_text(
        json.dumps({"panes": [{"id": "retry_job", "command": [py, "-c", script, "--resume"]}]}),
        encoding="utf-8",
    )
    base_dir = tmp_path / "mux_base"
    assert mux_main(["--base-dir", str(base_dir), "start", "--session", "res_sess", "--manifest", str(manifest), "--max-concurrent", "1"]) == 0
    capsys.readouterr()

    deadline = time.monotonic() + 20.0
    snap = inspect_session(base_dir, "res_sess")
    while not snap["all_finished"] and time.monotonic() < deadline:
        time.sleep(0.2)
        snap = inspect_session(base_dir, "res_sess")

    assert snap["all_finished"] is True
    assert snap["counts"]["done"] == 1
    assert snap["counts"]["failed"] == 0
    assert snap["counts"].get("resumable", 0) == 0
    assert int(marker.read_text(encoding="utf-8")) == 2


def test_multi_task_mux_retry_exhausted_and_log_append(tmp_path: Path, capsys) -> None:
    manifest = tmp_path / "exhaust_jobs.json"
    marker = tmp_path / "always75_count.txt"
    py = sys.executable
    script = (
        f"import pathlib, sys; p = pathlib.Path({str(marker)!r}); "
        "n = int(p.read_text()) + 1 if p.exists() else 1; "
        "p.write_text(str(n), encoding='utf-8'); "
        "print(f'attempt={n}', flush=True); "
        "sys.exit(75)"
    )
    manifest.write_text(
        json.dumps({"panes": [{"id": "exhaust_job", "command": [py, "-c", script, "--resume"]}]}),
        encoding="utf-8",
    )
    base_dir = tmp_path / "mux_base"
    assert mux_main(["--base-dir", str(base_dir), "start", "--session", "ex_sess", "--manifest", str(manifest), "--max-concurrent", "1"]) == 0
    capsys.readouterr()

    rc_wait = mux_main(["--base-dir", str(base_dir), "wait", "--session", "ex_sess", "--timeout", "40", "--interval", "0.2"])
    assert rc_wait == 1
    snap = json.loads(capsys.readouterr().out)
    assert snap["all_finished"] is True
    assert snap["counts"]["retry_exhausted"] == 1
    assert snap["counts"].get("resumable", 0) == 0
    assert int(marker.read_text(encoding="utf-8")) == 4

    log_text = (base_dir / "ex_sess" / "logs" / "exhaust_job.log").read_text(encoding="utf-8")
    assert "attempt=1" in log_text
    assert "attempt=4" in log_text
    assert "[mux resume attempt 1" in log_text

    assert mux_main(["--base-dir", str(base_dir), "status", "--session", "ex_sess"]) == 0
    assert "retry_exhausted=1" in capsys.readouterr().out
