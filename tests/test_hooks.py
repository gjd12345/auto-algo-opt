"""
脚本：test_hooks.py
功能：hooks.on_run_success / on_run_failure 单元测试
输入：无（tmp_path 隔离 + mock card_synthesis）
输出：pytest 断言
用法：python3 -m pytest tests/test_hooks.py -v
"""

from __future__ import annotations

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
