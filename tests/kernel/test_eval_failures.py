from __future__ import annotations

from agent_skill_loop.contracts import DEFAULT_SEED
from agent_skill_loop.evaluator import SubprocessEvaluator
from agent_skill_loop.problems.cvrp import BASELINE_CODE, build_suite


def test_illegal_source_is_invalid_not_success():
    suite = build_suite(DEFAULT_SEED, count=3, size=8)
    evaluator = SubprocessEvaluator(timeout=5.0)
    result = evaluator.evaluate("import os\n" + BASELINE_CODE, suite)
    assert result.valid is False
    assert result.error_code == "forbidden_import"


def test_missing_entrypoint_is_invalid():
    suite = build_suite(DEFAULT_SEED, count=3, size=8)
    evaluator = SubprocessEvaluator(timeout=5.0)
    result = evaluator.evaluate("def foo():\n    return 0\n", suite)
    assert result.valid is False
    assert result.error_code == "missing_entrypoint"


def test_infinite_loop_times_out():
    suite = build_suite(DEFAULT_SEED, count=1, size=4)
    evaluator = SubprocessEvaluator(timeout=1.0)
    code = (
        "def select_next_node(current_node, depot, unvisited_nodes, rest_capacity, demands, distance_matrix):\n"
        "    while True:\n"
        "        pass\n"
    )
    result = evaluator.evaluate(code, suite)
    assert result.valid is False
    assert result.error_code == "timeout"


def test_invalid_return_type():
    suite = build_suite(DEFAULT_SEED, count=2, size=6)
    evaluator = SubprocessEvaluator(timeout=5.0)
    code = (
        "def select_next_node(current_node, depot, unvisited_nodes, rest_capacity, demands, distance_matrix):\n"
        "    return 'nope'\n"
    )
    result = evaluator.evaluate(code, suite)
    assert result.valid is False
    assert result.error_code == "invalid_return"


def test_baseline_is_valid_and_finite():
    suite = build_suite(DEFAULT_SEED, count=3, size=8)
    result = SubprocessEvaluator(timeout=10.0).evaluate(BASELINE_CODE, suite)
    assert result.valid is True
    assert result.objective is not None and result.objective > 0
    assert len(result.instance_objectives) == 3
