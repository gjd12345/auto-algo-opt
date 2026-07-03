"""
脚本：test_hooks.py
功能：hooks.on_run_success / on_run_failure 单元测试
输入：无（tmp_path 隔离 + mock card_synthesis）
输出：pytest 断言
用法：python3 -m pytest tests/test_hooks.py -v
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from eoh_rag.experiments.hooks import on_run_failure, on_run_success
from eoh_rag.experiments.pool_api import PoolAPI


@pytest.fixture
def pool(tmp_path: Path) -> PoolAPI:
    return PoolAPI(tmp_path / "pool")


class TestOnRunSuccess:
    def _make_summary(self, obj: float = 0.00674, code: str = "def h(): pass") -> dict:
        return {
            "run_summary": {
                "best_objective": obj,
                "best_code": code,
                "population_size": 4,
                "valid_candidates": 3,
                "latest_generation": 4,
            },
            "rag_trace": {},
        }

    def test_registers_run_and_code(self, pool: PoolAPI):
        summary = self._make_summary(0.01, "code_a")
        on_run_success(pool, "bp_online", "/run/1", summary, {})
        assert pool.best_run("bp_online") == "/run/1"
        codes = pool.best_codes("bp_online")
        assert len(codes) == 1
        assert codes[0]["code"] == "code_a"

    def test_returns_eval_result(self, pool: PoolAPI):
        summary = self._make_summary(0.00674)
        result = on_run_success(pool, "bp_online", "/run/1", summary, {})
        assert result["decision"] == "archive"
        assert result["passed"] is True

    def test_registers_operator_stat(self, pool: PoolAPI):
        # 先注册一个旧 code 作为 prev_best
        pool.register_code("bp_online", "old", 0.02)
        summary = self._make_summary(0.01)
        on_run_success(pool, "bp_online", "/run/2", summary, {"operators": "e1,m2"})
        weights = pool.operator_weights("bp_online")
        assert "e1,m2" in weights

    @patch("eoh_rag.experiments.hooks._maybe_synthesize_card")
    def test_card_synthesis_triggered_on_archive(self, mock_card, pool: PoolAPI):
        summary = self._make_summary(0.00674)  # strong improvement → archive
        on_run_success(pool, "bp_online", "/run/1", summary, {})
        mock_card.assert_called_once()

    @patch("eoh_rag.experiments.hooks._maybe_synthesize_card")
    def test_card_synthesis_not_triggered_below_threshold(self, mock_card, pool: PoolAPI):
        summary = self._make_summary(0.039)  # barely any improvement → continue
        on_run_success(pool, "bp_online", "/run/1", summary, {})
        mock_card.assert_not_called()

    def test_missing_objective_handled(self, pool: PoolAPI):
        summary = {"run_summary": {"best_objective": None, "best_code": ""}}
        result = on_run_success(pool, "bp_online", "/run/1", summary, {})
        assert result == {}
        assert pool.list_runs() == []

    @patch("eoh_rag.experiments.hooks._maybe_synthesize_card")
    def test_online_outcome_uses_real_baseline_and_run_id(self, _mock_card, pool: PoolAPI, tmp_path: Path):
        """在线 outcome 应带真实基线、算出 objective_success，并以 run 目录名作 run_id。"""
        summary = {
            "run_summary": {
                "best_objective": 0.00674,  # 优于 bp_online 官方基线 0.0398
                "best_code": "def h(): pass",
                "population_size": 4,
                "valid_candidates": 3,
                "latest_generation": 4,
            },
            "rag_trace": {
                "rag_injected_items": [
                    {"id": "history_bp_x", "kind": "algorithm_card",
                     "section": "strategy", "status": "full", "chars": 400},
                ],
            },
        }
        outcome_file = tmp_path / "outcomes.jsonl"
        on_run_success(pool, "bp_online", "/runs/run_xyz", summary, {}, outcome_file=str(outcome_file))

        lines = outcome_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        rec = json.loads(lines[0])
        assert rec["pure_baseline"] == 0.0398          # 真实基线，不再是 None
        assert rec["delta_pct"] is not None and rec["delta_pct"] < 0
        assert rec["objective_success"] is True         # best 优于基线 → 反馈闭环成立
        assert rec["run_id"] == "run_xyz"               # 用 run 目录名，避免固定键去重冲突


class TestOnRunFailure:
    def test_registers_failure(self, pool: PoolAPI):
        summary = {
            "failure_reason": "eval_timeout",
            "run_summary": {"best_code": "for i in x:\n  for j in y:\n    pass"},
        }
        on_run_failure(pool, "bp_online", summary)
        hints = pool.failure_hints("bp_online")
        assert len(hints) == 1
        assert "nested loops" in hints[0]

    def test_no_code_no_register(self, pool: PoolAPI):
        summary = {"failure_reason": "eval_timeout", "run_summary": {"best_code": ""}}
        on_run_failure(pool, "bp_online", summary)
        assert pool.failure_hints("bp_online") == []

    def test_no_reason_no_register(self, pool: PoolAPI):
        summary = {"failure_reason": "", "run_summary": {"best_code": "some code"}}
        on_run_failure(pool, "bp_online", summary)
        assert pool.failure_hints("bp_online") == []
