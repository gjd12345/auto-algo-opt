from __future__ import annotations

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