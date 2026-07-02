"""
脚本：test_evaluator.py
功能：覆盖 evaluate_run 的四种 decision 分支 + baselines 常量正确性。
输入：无
输出：pytest 断言
用法：pytest tests/test_evaluator.py -v
"""

from __future__ import annotations

import math

import pytest

from eoh_rag.experiments.baselines import PROBLEM_BASELINES, get_baseline
from eoh_rag.experiments.evaluator import evaluate_run


# --------------------------------------------------------------------------- #
# baselines                                                                   #
# --------------------------------------------------------------------------- #


def test_baseline_constants_frozen() -> None:
    """Step 0 evidence 冻结的 baseline —— 改动这里必须先动 Step 0 evidence。"""
    assert PROBLEM_BASELINES == {
        "bp_online": 0.0398,
        "tsp_construct": 6.560,
        "cvrp_construct": 13.519,
    }


def test_get_baseline_known_and_unknown() -> None:
    assert get_baseline("bp_online") == 0.0398
    assert get_baseline("unknown") is None


# --------------------------------------------------------------------------- #
# evaluate_run —— 主要 decision 分支                                          #
# --------------------------------------------------------------------------- #


def test_bp_evidence_archive() -> None:
    """Step 0 evidence: BP 0.00674 → improvement ≈ 0.831 → archive。"""
    r = evaluate_run("bp_online", 0.00674)
    assert r["baseline"] == 0.0398
    assert r["improvement"] == pytest.approx(0.831, abs=0.01)
    assert r["passed"] is True
    assert r["decision"] == "archive"


def test_tsp_evidence_archive() -> None:
    r = evaluate_run("tsp_construct", 6.00393)
    assert r["improvement"] == pytest.approx(0.0848, abs=0.01)
    assert r["decision"] == "archive"


def test_cvrp_evidence_archive() -> None:
    r = evaluate_run("cvrp_construct", 12.35639)
    assert r["improvement"] == pytest.approx(0.0861, abs=0.01)
    assert r["decision"] == "archive"


def test_positive_but_below_target_continue() -> None:
    """有改进但 < 5% → continue。"""
    r = evaluate_run("bp_online", 0.0398 * 0.98)  # 2% 改进
    assert r["passed"] is False
    assert r["decision"] == "continue"


def test_no_change_continue() -> None:
    r = evaluate_run("bp_online", 0.0398)
    assert r["improvement"] == 0.0
    assert r["decision"] == "continue"


def test_regression_adjust() -> None:
    r = evaluate_run("bp_online", 0.05)  # 比 baseline 差
    assert r["improvement"] < 0
    assert r["decision"] == "adjust"


def test_missing_objective_adjust() -> None:
    r = evaluate_run("bp_online", float("nan"))
    assert r["decision"] == "adjust"
    assert "objective missing" in r["reason"]


def test_inf_objective_adjust() -> None:
    r = evaluate_run("bp_online", math.inf)
    assert r["decision"] == "adjust"


def test_unknown_problem_escalate() -> None:
    r = evaluate_run("unknown_problem", 1.0)
    assert r["baseline"] is None
    assert r["decision"] == "escalate"


def test_custom_baseline_override() -> None:
    r = evaluate_run("bp_online", 0.01, baseline=0.02)
    assert r["baseline"] == 0.02
    assert r["improvement"] == pytest.approx(0.5)
    assert r["decision"] == "archive"


def test_custom_target() -> None:
    """把 target 抬到 90% 后原本 archive 的会被降级到 continue。"""
    r = evaluate_run("bp_online", 0.00674, target_improvement=0.9)
    assert r["passed"] is False
    assert r["decision"] == "continue"
