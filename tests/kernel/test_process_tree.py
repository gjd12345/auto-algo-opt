from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

from agent_skill_loop.contracts import DEFAULT_COUNT, DEFAULT_SEED, DEFAULT_SIZE, DEFAULT_SPLIT
from agent_skill_loop.evaluator import SubprocessEvaluator, kill_process_tree
from agent_skill_loop.problems.cvrp import BASELINE_CODE, build_suite


@pytest.mark.skipif(sys.platform != "win32", reason="Windows process-tree semantics")
def test_kill_process_tree_kills_grandchildren():
    script = (
        "import subprocess, sys, time\n"
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(300)'])\n"
        "with open(sys.argv[1], 'w') as f:\n"
        "    f.write(str(child.pid))\n"
        "time.sleep(300)\n"
    )
    with tempfile.TemporaryDirectory(prefix="kill-tree-") as tmp:
        pid_file = Path(tmp) / "child.pid"
        proc = subprocess.Popen(
            [sys.executable, "-c", script, str(pid_file)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        deadline = time.monotonic() + 10.0
        while not pid_file.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert pid_file.exists(), "grandchild never started"
        child_pid = int(pid_file.read_text().strip())
        kill_process_tree(proc)
        for pid in (proc.pid, child_pid):
            out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True)
            assert "PID" not in out.stdout, f"process {pid} still alive"


def test_subprocess_evaluator_timeout_classification():
    suite = build_suite(DEFAULT_SEED, split=DEFAULT_SPLIT, count=DEFAULT_COUNT, size=DEFAULT_SIZE)
    evaluator = SubprocessEvaluator(timeout=5.0)
    code = (
        "def select_next_node(current_node, depot, unvisited_nodes, rest_capacity, demands, distance_matrix):\n"
        "    while True:\n"
        "        pass\n"
    )
    result = evaluator.evaluate(code, suite)
    assert result.valid is False
    assert result.error_code == "timeout"
    assert result.elapsed_seconds < 10.0
    # No leaked lock/process: a normal valid baseline candidate still evaluates.
    baseline = evaluator.evaluate(BASELINE_CODE, suite)
    assert baseline.valid is True


def test_eval_worker_exits_when_parent_is_dead():
    """The worker must not outlive its parent (nested official-EoH path)."""
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait(timeout=10)
    suite = build_suite(DEFAULT_SEED, count=1, size=4)
    code = (
        "def select_next_node(current_node, depot, unvisited_nodes, rest_capacity, demands, distance_matrix):\n"
        "    while True:\n"
        "        pass\n"
    )
    request = {
        "problem": "cvrp_construct",
        "code": code,
        "suite": suite,
        "parent_pid": dead.pid,
    }
    worker = subprocess.Popen(
        [sys.executable, "-m", "agent_skill_loop.eval_worker"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    try:
        worker.communicate(json.dumps(request).encode("utf-8"), timeout=8)
        # Without the watchdog the infinite loop would run until the caller's
        # timeout; exiting within the window is the assertion.
        assert worker.poll() is not None
    except subprocess.TimeoutExpired:
        worker.kill()
        pytest.fail("eval_worker outlived its dead parent")
    finally:
        if worker.poll() is None:
            worker.kill()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX process-group semantics")
def test_kill_process_tree_never_kills_its_own_group():
    """A child sharing our process group must not drag the caller down."""
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        assert os.getpgid(proc.pid) == os.getpgid(0)
        kill_process_tree(proc)
        assert proc.poll() is not None
        # Reaching this line proves the calling process group survived.
    finally:
        if proc.poll() is None:
            proc.kill()