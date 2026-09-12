from __future__ import annotations

import json

from agent_skill_loop.problems.cvrp import BASELINE_CODE, build_suite as cvrp_build_suite
from agent_skill_loop.problems.tsp_2opt import build_suite as tsp2_build_suite
from agent_skill_loop.skill_store import make_skill, save_skill
from agent_skill_loop.workflow import WorkflowRunner


def test_workflow_binds_registered_problem_and_suite_identity(tmp_path):
    runner = WorkflowRunner(
        tmp_path / "workflow",
        problem="tsp_2opt",
        model="fixture",
        max_rounds=1,
        max_requests=0,
        plan_request=lambda **_kwargs: "{}",
    )
    assert runner.spec.problem_id == "tsp_2opt"
    assert runner.suite["problem"] == runner.spec.problem_id
    assert runner.suite["content_hash"] == runner.spec.suite_hash(
        runner.suite["problem"], "dev_train", runner.suite["instances"]
    )


def _write_skill(tmp_path, *, problem: str, entrypoint: str, code: str) -> "object":
    skill = make_skill(
        version_id="v1",
        code=code,
        suite_hash="x",
        valid=True,
        mean_objective=1.0,
        instance_objectives=(1.0,),
        parent_version_id=None,
        source_attempt_id=None,
        problem=problem,
        entrypoint=entrypoint,
    )
    return save_skill(tmp_path / "skills" / "v1", skill)


def test_evaluate_skill_cli_rejects_problem_mismatch(tmp_path, capsys):
    from agent_skill_loop.__main__ import main

    skill_dir = _write_skill(tmp_path, problem="tsp_construct", entrypoint="select_next_node", code=BASELINE_CODE)
    suite = tsp2_build_suite(20260908, count=3, size=20)
    suite_file = tmp_path / "suite.json"
    suite_file.write_text(json.dumps(suite), encoding="utf-8")
    code = main(["evaluate-skill", "--skill", str(skill_dir), "--suite", str(suite_file)])
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["error_code"] == "skill_problem_mismatch"


def test_evaluate_skill_cli_rejects_entrypoint_mismatch(tmp_path, capsys):
    from agent_skill_loop.__main__ import main

    skill_dir = _write_skill(tmp_path, problem="tsp_2opt", entrypoint="select_next_node", code=BASELINE_CODE)
    suite = tsp2_build_suite(20260908, count=3, size=20)
    suite_file = tmp_path / "suite.json"
    suite_file.write_text(json.dumps(suite), encoding="utf-8")
    code = main(["evaluate-skill", "--skill", str(skill_dir), "--suite", str(suite_file)])
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["error_code"] == "skill_entrypoint_mismatch"


def test_evaluate_skill_cli_accepts_matching_identity(tmp_path, capsys):
    from agent_skill_loop.__main__ import main

    skill_dir = _write_skill(tmp_path, problem="cvrp_construct", entrypoint="select_next_node", code=BASELINE_CODE)
    suite = cvrp_build_suite(20260908, count=3, size=20)
    suite_file = tmp_path / "suite.json"
    suite_file.write_text(json.dumps(suite), encoding="utf-8")
    code = main(["evaluate-skill", "--skill", str(skill_dir), "--suite", str(suite_file)])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["valid"] is True
