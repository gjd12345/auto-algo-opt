"""
脚本：test_run_tracker.py
功能：RunTracker 单元测试 —— 覆盖 start_run / save_* / finalize 的目录结构和文件内容
输入：无（pytest tmp_path 隔离）
输出：pytest 断言
用法：python3 -m pytest tests/test_run_tracker.py -v
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eoh_rag.experiments.run_tracker import RunTracker


@pytest.fixture
def tracker(tmp_path: Path) -> RunTracker:
    return RunTracker(tmp_path / "runs")


class TestStartRun:
    def test_creates_directory_and_run_json(self, tracker: RunTracker):
        td = tracker.start_run("island_1", "bp_online", "mixed_rag", gen=8, rep=3, run_dir="/actual/run")
        assert td.exists()
        run_json = td / "run.json"
        assert run_json.exists()
        meta = json.loads(run_json.read_text())
        assert meta["suite"] == "island_1"
        assert meta["problem"] == "bp_online"
        assert meta["arm"] == "mixed_rag"
        assert meta["gen"] == 8
        assert meta["rep"] == 3
        assert meta["run_dir"] == "/actual/run"
        assert meta["status"] == "running"
        assert "started_at" in meta

    def test_run_tag_format(self, tracker: RunTracker):
        td = tracker.start_run("s1", "tsp_construct", "pure_eoh", gen=4, rep=1, run_dir="/x")
        assert td.name == "tsp_construct_pure_eoh_g4_r1"

    def test_idempotent_on_existing_dir(self, tracker: RunTracker):
        td1 = tracker.start_run("s1", "bp_online", "a", gen=1, rep=1, run_dir="/x")
        td2 = tracker.start_run("s1", "bp_online", "a", gen=1, rep=1, run_dir="/y")
        assert td1 == td2
        meta = json.loads((td2 / "run.json").read_text())
        assert meta["run_dir"] == "/y"


class TestSaveFiles:
    def test_save_summary(self, tracker: RunTracker):
        td = tracker.start_run("s", "bp", "a", 1, 1, "/x")
        tracker.save_summary(td, {"best_objective": 0.01, "valid_candidates": 3})
        assert (td / "official_eoh_run_summary.json").exists()
        data = json.loads((td / "official_eoh_run_summary.json").read_text())
        assert data["best_objective"] == 0.01

    def test_save_eval(self, tracker: RunTracker):
        td = tracker.start_run("s", "bp", "a", 1, 1, "/x")
        tracker.save_eval(td, {"decision": "archive", "improvement": 0.83})
        data = json.loads((td / "eval_result.json").read_text())
        assert data["decision"] == "archive"

    def test_save_rag_trace(self, tracker: RunTracker):
        td = tracker.start_run("s", "bp", "a", 1, 1, "/x")
        tracker.save_rag_trace(td, {"rag_injected_items": ["card_1"]})
        data = json.loads((td / "rag_trace.json").read_text())
        assert data["rag_injected_items"] == ["card_1"]

    def test_save_command(self, tracker: RunTracker):
        td = tracker.start_run("s", "bp", "a", 1, 1, "/x")
        tracker.save_command(td, ["python3", "-m", "eoh_rag.experiments.eoh_single_runner", "--problem", "bp"])
        data = json.loads((td / "command.json").read_text())
        assert data["cmd"][0] == "python3"


class TestFinalize:
    def test_finalize_ok_with_code(self, tracker: RunTracker):
        td = tracker.start_run("s", "bp", "a", 1, 1, "/x")
        tracker.finalize(td, status="ok", best_code="def heuristic(): pass", objective=0.007)
        outcome = json.loads((td / "outcome.json").read_text())
        assert outcome["status"] == "ok"
        assert outcome["objective"] == 0.007
        assert (td / "best_code.py").exists()
        assert "heuristic" in (td / "best_code.py").read_text()
        # run.json 也更新了
        meta = json.loads((td / "run.json").read_text())
        assert meta["status"] == "ok"

    def test_finalize_failed(self, tracker: RunTracker):
        td = tracker.start_run("s", "bp", "a", 1, 1, "/x")
        tracker.finalize(td, status="timeout")
        outcome = json.loads((td / "outcome.json").read_text())
        assert outcome["status"] == "timeout"
        assert "best_code" not in outcome
        assert not (td / "best_code.py").exists()

    def test_finalize_without_run_json(self, tmp_path: Path):
        """即使 run.json 不存在，finalize 也不崩（容错）。"""
        tracker = RunTracker(tmp_path)
        td = tmp_path / "orphan"
        td.mkdir()
        tracker.finalize(td, status="ok")
        assert (td / "outcome.json").exists()
