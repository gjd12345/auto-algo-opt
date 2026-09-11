from __future__ import annotations

import json

from agent_skill_loop.client import FixtureTransport
from agent_skill_loop.contracts import DEFAULT_SEED
from agent_skill_loop.evaluator import SubprocessEvaluator
from agent_skill_loop.loop import AgentLoop
from agent_skill_loop.problems.base import PROBLEM_REGISTRY, get_problem
from agent_skill_loop.problems.tsp import (
    BASELINE_CODE,
    ENTRYPOINT,
    PROBLEM_NAME,
    SPLIT_OFFSETS,
    TASK_DESCRIPTION,
    TEMPLATE_PROGRAM,
    build_suite,
    suite_hash,
)


def test_tsp_spec_registered_with_identity():
    spec = get_problem("tsp_construct")
    assert spec.problem_id == PROBLEM_NAME == "tsp_construct"
    assert spec.entrypoint == ENTRYPOINT == "select_next_node"
    assert spec.task_description == TASK_DESCRIPTION
    assert spec.template_program == TEMPLATE_PROGRAM
    assert spec.baseline_code == BASELINE_CODE
    assert spec.objective_direction == "minimize"
    assert spec.split_offsets == SPLIT_OFFSETS
    assert PROBLEM_REGISTRY["tsp_construct"] is spec


def test_tsp_suite_is_deterministic_and_distinct_from_cvrp():
    first = build_suite(DEFAULT_SEED, split="dev_train", count=3, size=20)
    second = build_suite(DEFAULT_SEED, split="dev_train", count=3, size=20)
    assert first == second
    assert first["problem"] == "tsp_construct"
    assert len(first["instances"]) == 3
    assert all(len(instance["coordinates"]) == 20 for instance in first["instances"])
    assert first["content_hash"] == suite_hash("tsp_construct", "dev_train", first["instances"])
    from agent_skill_loop.problems.cvrp import build_suite as cvrp_build_suite

    cvrp = cvrp_build_suite(DEFAULT_SEED, split="dev_train", count=3, size=20)
    assert first["content_hash"] != cvrp["content_hash"]


def test_tsp_baseline_evaluates_to_finite_objective():
    suite = build_suite(DEFAULT_SEED, split="dev_train", count=3, size=20)
    result = SubprocessEvaluator(timeout=10.0).evaluate(BASELINE_CODE, suite)
    assert result.valid is True
    assert result.objective is not None and result.objective > 0
    assert len(result.instance_objectives) == 3
    assert all(value > 0 for value in result.instance_objectives)


def test_tsp_rejects_wrong_return_type():
    suite = build_suite(DEFAULT_SEED, count=2, size=8)
    code = (
        "def select_next_node(current_node, start_node, unvisited_nodes, distance_matrix):\n"
        "    return 'nope'\n"
    )
    result = SubprocessEvaluator(timeout=5.0).evaluate(code, suite)
    assert result.valid is False
    assert result.error_code == "invalid_return"


def test_tsp_rejects_early_return_to_start():
    suite = build_suite(DEFAULT_SEED, count=2, size=8)
    code = (
        "def select_next_node(current_node, start_node, unvisited_nodes, distance_matrix):\n"
        "    return 0\n"
    )
    result = SubprocessEvaluator(timeout=5.0).evaluate(code, suite)
    assert result.valid is False
    assert result.error_code == "invalid_return"


def test_tsp_rejects_mutated_input():
    suite = build_suite(DEFAULT_SEED, count=2, size=8)
    code = (
        "def select_next_node(current_node, start_node, unvisited_nodes, distance_matrix):\n"
        "    unvisited_nodes[0] = 0\n"
        "    return unvisited_nodes[0]\n"
    )
    result = SubprocessEvaluator(timeout=5.0).evaluate(code, suite)
    assert result.valid is False
    assert result.error_code == "candidate_mutated_input"


def test_tsp_fixture_smoke_exports_and_reevaluates(tmp_path):
    spec = get_problem("tsp_construct")
    farthest = spec.baseline_code.replace("argmin", "argmax")
    valid = "{Farthest-neighbor TSP heuristic}\n```python\n" + farthest.strip() + "\n```\n"
    invalid = (
        "{Broken return type}\n"
        "```python\n"
        "def select_next_node(*args, **kwargs):\n"
        "    return 'nope'\n"
        "```\n"
    )
    out = tmp_path / "tsp"
    out.mkdir()
    transport = FixtureTransport([valid, invalid, valid])
    summary = AgentLoop(out, transport=transport, execution_mode="fixture", problem_spec=spec, wall_seconds=120).run()
    assert summary.loop_completed is True
    assert summary.status == "completed_with_valid_candidate"
    assert summary.generated_valid_candidates >= 1
    assert summary.feedback_consumed_count >= 1
    assert (out / "exported_skill" / "ref.json").is_file()

    suite = json.loads((out / "dev_suite.json").read_text(encoding="utf-8"))
    assert suite["problem"] == "tsp_construct"
    from agent_skill_loop.skill_store import load_skill

    skill = load_skill(out / "exported_skill")
    assert skill.problem == "tsp_construct"
    first = SubprocessEvaluator(timeout=10.0).evaluate(skill.code, suite)
    second = SubprocessEvaluator(timeout=10.0).evaluate(skill.code, suite)
    assert first.valid is True
    assert first.objective == second.objective
    summary_data = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary_data["problem"] == "tsp_construct"
