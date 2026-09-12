from __future__ import annotations

from agent_skill_loop.contracts import DEFAULT_SEED
from agent_skill_loop.evaluator import SubprocessEvaluator
from agent_skill_loop.problems.base import PROBLEM_REGISTRY, get_problem
from agent_skill_loop.problems.tsp_2opt import (
    BASELINE_CODE,
    ENTRYPOINT,
    PROBLEM_NAME,
    SPLIT_OFFSETS,
    TASK_DESCRIPTION,
    TEMPLATE_PROGRAM,
    build_suite,
    suite_hash,
)


def test_tsp2_spec_registered_with_identity():
    spec = get_problem("tsp_2opt")
    assert spec.problem_id == PROBLEM_NAME == "tsp_2opt"
    assert spec.entrypoint == ENTRYPOINT == "select_2opt_move"
    assert spec.task_description == TASK_DESCRIPTION
    assert spec.template_program == TEMPLATE_PROGRAM
    assert spec.baseline_code == BASELINE_CODE
    assert spec.split_offsets == SPLIT_OFFSETS
    assert PROBLEM_REGISTRY["tsp_2opt"] is spec


def test_tsp2_suite_is_deterministic_and_distinct():
    first = build_suite(DEFAULT_SEED, split="dev_train", count=3, size=20)
    second = build_suite(DEFAULT_SEED, split="dev_train", count=3, size=20)
    assert first == second
    assert first["content_hash"] == suite_hash("tsp_2opt", "dev_train", first["instances"])
    from agent_skill_loop.problems.tsp import build_suite as tsp_build_suite

    tsp = tsp_build_suite(DEFAULT_SEED, split="dev_train", count=3, size=20)
    assert first["content_hash"] != tsp["content_hash"]


def test_tsp2_baseline_is_valid_and_finite():
    suite = build_suite(DEFAULT_SEED, count=3, size=20)
    result = SubprocessEvaluator(timeout=10.0).evaluate(BASELINE_CODE, suite)
    assert result.valid is True
    assert result.objective is not None and result.objective > 0
    assert len(result.instance_objectives) == 3


def test_tsp2_records_operation_metrics():
    suite = build_suite(DEFAULT_SEED, count=3, size=20)
    result = SubprocessEvaluator(timeout=10.0).evaluate(BASELINE_CODE, suite)
    assert result.valid is True
    metrics = result.metrics
    assert isinstance(metrics, dict)
    assert metrics["operation_budget_per_instance"] == [20, 20, 20]
    assert all(0 <= moves <= 20 for moves in metrics["moves_applied"])
    assert all(scanned >= 0 for scanned in metrics["pairs_scanned"])
    assert metrics["total_moves_applied"] == sum(metrics["moves_applied"])
    assert metrics["total_pairs_scanned"] == sum(metrics["pairs_scanned"])


def test_tsp2_spec_has_baseline_description():
    spec = get_problem("tsp_2opt")
    assert spec.baseline_description
    assert "2-opt" in spec.baseline_description


def test_tsp2_is_bounded_for_constant_choice():
    """A trivial always-first rule must still terminate with a finite objective."""
    suite = build_suite(DEFAULT_SEED, count=2, size=12)
    code = (
        "def select_2opt_move(tour, distance_matrix, move_start, move_end, move_delta, remaining_moves):\n"
        "    return 0\n"
    )
    result = SubprocessEvaluator(timeout=10.0).evaluate(code, suite)
    assert result.valid is True
    assert result.objective is not None and result.objective > 0


def test_tsp2_rejects_wrong_return_type():
    suite = build_suite(DEFAULT_SEED, count=2, size=8)
    code = (
        "def select_2opt_move(tour, distance_matrix, move_start, move_end, move_delta, remaining_moves):\n"
        "    return 'nope'\n"
    )
    result = SubprocessEvaluator(timeout=5.0).evaluate(code, suite)
    assert result.valid is False
    assert result.error_code == "invalid_return"


def test_tsp2_rejects_out_of_range_index():
    suite = build_suite(DEFAULT_SEED, count=2, size=8)
    code = (
        "def select_2opt_move(tour, distance_matrix, move_start, move_end, move_delta, remaining_moves):\n"
        "    return 10 ** 6\n"
    )
    result = SubprocessEvaluator(timeout=5.0).evaluate(code, suite)
    assert result.valid is False
    assert result.error_code == "invalid_return"


def test_tsp2_rejects_mutated_input():
    suite = build_suite(DEFAULT_SEED, count=2, size=8)
    code = (
        "def select_2opt_move(tour, distance_matrix, move_start, move_end, move_delta, remaining_moves):\n"
        "    tour[0] = 3\n"
        "    return 0\n"
    )
    result = SubprocessEvaluator(timeout=5.0).evaluate(code, suite)
    assert result.valid is False
    assert result.error_code == "candidate_mutated_input"
