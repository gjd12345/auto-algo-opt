from __future__ import annotations

import json

import pytest

pytest.importorskip("eoh")

from agent_skill_loop.contracts import DEFAULT_SEED
from agent_skill_loop.evaluator import SubprocessEvaluator
from agent_skill_loop.problems.cvrp import BASELINE_CODE, TASK_DESCRIPTION, TEMPLATE_PROGRAM, build_suite
from eoh_frozen.export import export_best_skill, load_best_individual
from eoh_frozen.problem import FrozenProblem
from agent_skill_loop.problems.base import get_problem


def test_frozen_problem_matches_kernel_baseline():
    suite = build_suite(DEFAULT_SEED, count=3, size=20)
    problem = FrozenProblem(suite, spec=get_problem("cvrp_construct"), timeout=20)
    assert problem.template_program == TEMPLATE_PROGRAM
    assert problem.task_description == TASK_DESCRIPTION
    assert problem.suite["content_hash"] == suite["content_hash"]
    assert suite["content_hash"] == "abc17e034e981f79954b779240cb5f4b417020e6c048a2e6d91e19ab95ddf8f0"
    fitness = problem.evaluate(BASELINE_CODE)
    kernel = SubprocessEvaluator(timeout=20.0).evaluate(BASELINE_CODE, suite)
    assert fitness is not None
    assert kernel.valid is True
    assert abs(float(fitness) - float(kernel.objective)) < 1e-9


def test_frozen_problem_invalid_code_is_none():
    suite = build_suite(DEFAULT_SEED, count=3, size=8)
    problem = FrozenProblem(suite, spec=get_problem("cvrp_construct"), timeout=10)
    assert problem.evaluate("def select_next_node(*args):\n    return 'nope'\n") is None


def test_frozen_problem_writes_eval_failure_log(tmp_path):
    suite = build_suite(DEFAULT_SEED, count=2, size=6)
    fail_log = tmp_path / "eval_failures.jsonl"
    problem = FrozenProblem(suite, spec=get_problem("cvrp_construct"), timeout=10, fail_log=fail_log)
    assert problem.evaluate("def select_next_node(*args):\n    return 'nope'\n") is None
    lines = fail_log.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["error_code"] == "invalid_return"
    assert "select_next_node" in payload["code"]


def test_export_best_from_official_population(tmp_path):
    suite = build_suite(DEFAULT_SEED, count=3, size=20)
    out = tmp_path / "eoh_out"
    best_dir = out / "results" / "pops_best"
    best_dir.mkdir(parents=True)
    payload = {
        "algorithm": "nearest neighbor",
        "code": BASELINE_CODE,
        "objective": 6.95622,
        "other_inf": None,
    }
    (best_dir / "population_generation_3.json").write_text(json.dumps(payload), encoding="utf-8")
    path = export_best_skill(out, suite, timeout=20.0)
    assert path is not None
    meta = json.loads((path / "skill.json").read_text(encoding="utf-8"))
    assert meta["version_id"] == "eoh_best"
    assert meta["valid"] is True
    assert meta["suite_hash"] == suite["content_hash"]
    assert path == out / "skills" / "eoh_best"
    from agent_skill_loop.skill_store import load_skill

    exported = load_skill(out / "exported_skill")
    assert exported.code == BASELINE_CODE
    assert (out / "exported_skill" / "ref.json").is_file()
    assert not (out / "exported_skill" / "skill.json").exists()
    loaded = load_best_individual(out)
    assert loaded["code"] == BASELINE_CODE
