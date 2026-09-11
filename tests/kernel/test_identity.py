from __future__ import annotations

import json

import pytest

from agent_skill_loop.client import FixtureTransport
from agent_skill_loop.contracts import SkillVersion
from agent_skill_loop.loop import AgentLoop
from agent_skill_loop.problems.base import get_problem
from agent_skill_loop.problems.cvrp import BASELINE_CODE, build_suite as cvrp_build_suite
from agent_skill_loop.problems.tsp import build_suite as tsp_build_suite
from agent_skill_loop.problems.tsp_2opt import build_suite as tsp2_build_suite
from agent_skill_loop.skill_store import make_skill, save_skill


def _parent(problem: str, entrypoint: str) -> SkillVersion:
    return SkillVersion(
        version_id="parent",
        problem=problem,
        entrypoint=entrypoint,
        code="def select_next_node(*args):\n    return 0\n",
        code_sha256="0" * 64,
        parent_version_id=None,
        suite_hash="x",
        evaluator_hash="y",
        valid=True,
        mean_objective=1.0,
        instance_objectives=(1.0,),
        source_attempt_id=None,
    )


def test_loop_rejects_suite_problem_mismatch(tmp_path):
    with pytest.raises(ValueError, match="suite_problem_mismatch"):
        AgentLoop(
            tmp_path / "x",
            transport=FixtureTransport([]),
            problem_spec=get_problem("tsp_2opt"),
            suite=tsp_build_suite(20260908, count=3, size=20),
        )


def test_loop_rejects_parent_problem_mismatch(tmp_path):
    with pytest.raises(ValueError, match="parent_problem_mismatch"):
        AgentLoop(
            tmp_path / "x",
            transport=FixtureTransport([]),
            problem_spec=get_problem("tsp_2opt"),
            suite=tsp2_build_suite(20260908, count=3, size=20),
            parent_skill=_parent("tsp_construct", "select_next_node"),
        )


def test_loop_rejects_parent_entrypoint_mismatch(tmp_path):
    with pytest.raises(ValueError, match="parent_entrypoint_mismatch"):
        AgentLoop(
            tmp_path / "x",
            transport=FixtureTransport([]),
            problem_spec=get_problem("tsp_2opt"),
            suite=tsp2_build_suite(20260908, count=3, size=20),
            parent_skill=_parent("tsp_2opt", "select_next_node"),
        )


def test_loop_accepts_matching_identity(tmp_path):
    out = tmp_path / "ok"
    out.mkdir()
    loop = AgentLoop(
        out,
        transport=FixtureTransport([]),
        problem_spec=get_problem("tsp_2opt"),
        suite=tsp2_build_suite(20260908, count=3, size=20),
    )
    assert loop.suite["problem"] == "tsp_2opt"


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
