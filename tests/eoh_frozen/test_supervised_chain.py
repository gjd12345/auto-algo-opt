from __future__ import annotations
import json
import time
from pathlib import Path
import pytest

pytest.importorskip("eoh")
from eoh_frozen.__main__ import build_parser, cmd_run
from eoh_frozen.smoke import fixture_provider
from agent_skill_loop.problems.base import get_problem
from agent_skill_loop.evaluator import SubprocessEvaluator
from agent_skill_loop.skill_store import make_skill, save_skill, load_skill


def run(tmp_path, monkeypatch, *, problem="cvrp_construct", responder=None, extra=()):
    monkeypatch.setenv("EOH_TEST_KEY", "local-fixture")
    output = tmp_path / "run"
    with fixture_provider(problem, responder) as (endpoint, prompts):
        args = build_parser().parse_args(["run", "--problem", problem, "--model", "fixture",
            "--output", str(output), "--endpoint", endpoint, "--api-key-env", "EOH_TEST_KEY",
            "--pop-size", "2", "--n-pop", "1", "--max-sample-nums", "1", "--max-requests", "12",
            "--count", "1", "--size", "6", "--wall-seconds", "30", *extra])
        args.execution_mode = "fixture"
        exit_code = cmd_run(args)
    return output, json.loads((output / "summary.json").read_text()), prompts, exit_code


@pytest.mark.parametrize("problem", ["cvrp_construct", "tsp_construct", "tsp_2opt"])
def test_real_upstream_problem_to_export(tmp_path, monkeypatch, problem):
    out, result, prompts, code = run(tmp_path, monkeypatch, problem=problem)
    assert code == 0 and result["status"] == "completed"
    assert result["generated_valid_candidates"] == 5
    assert result["http_requests"] == 6 == len(prompts)
    assert prompts[0] == "1+1=?"
    skill = load_skill(out / result["best_generated_path"])
    assert skill.problem == problem and skill.origin == "generated"
    assert skill.search_policy_id == "official_eoh"
    suite = json.loads((out / "dev_suite.json").read_text())
    checked = SubprocessEvaluator().evaluate(skill.code, suite)
    assert checked.valid and checked.objective == skill.mean_objective
    assert (out / result["best_generated_path"] / "evidence.json").is_file()


@pytest.mark.parametrize("operator", ["e1", "e2", "m1", "m2"])
def test_official_operator_prompt_semantics(tmp_path, monkeypatch, operator):
    out, result, prompts, code = run(tmp_path, monkeypatch, extra=["--operators", operator])
    assert result["status"] == "completed"
    prompt = prompts[-1]
    if operator in {"e1", "e2"}:
        assert "2 existing algorithms" in prompt
    else:
        assert "I have one algorithm" in prompt
    assert "failed_code" not in prompt and "STAGNATION:" not in prompt
    if operator == "m2":
        assert "different parameter settings" in prompt


@pytest.mark.parametrize("status,body,error", [(401, "bad key", "provider_auth_invalid"), (200, b"[]", "provider_connectivity_or_protocol_error")])
def test_upstream_retries_never_repeat_terminal_provider_failure(tmp_path, monkeypatch, status, body, error):
    out, result, prompts, code = run(tmp_path, monkeypatch, responder=lambda p, n: (status, body))
    assert code == 2 and result["status"] == "provider_failed"
    assert result["provider_error_code"] == error
    assert len(prompts) == result["http_requests"] == 1
    assert result["best_generated_path"] is None


def test_request_limit_stops_engine_preserving_completed_candidate(tmp_path, monkeypatch):
    out, result, prompts, code = run(tmp_path, monkeypatch, extra=["--max-requests", "2"])
    assert code == 0 and result["stop_reason"] == "request_limit"
    assert len(prompts) == 2 and result["generated_valid_candidates"] == 1
    assert load_skill(out / result["best_generated_path"]).valid


def test_wall_deadline_during_candidate(tmp_path, monkeypatch):
    spec = get_problem("cvrp_construct")
    signature = spec.template_program.split("def ", 1)[1].split(":", 1)[0]
    # Use the contract baseline signature, with an endless body.
    import ast
    tree = ast.parse(spec.baseline_code)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef))
    fn.body = ast.parse("while True:\n    pass").body
    endless = ast.unparse(tree)
    def respond(prompt, n):
        return 200, "2" if n == 1 else "{Endless fixture}\n```python\n" + endless + "\n```"
    started = time.monotonic()
    out, result, prompts, code = run(tmp_path, monkeypatch, responder=respond,
        extra=["--wall-seconds", "3", "--solver-timeout", "30"])
    assert result["stop_reason"] == "wall_time_limit"
    assert time.monotonic() - started < 9
    assert result["generated_valid_candidates"] == 0
    assert len(prompts) <= 2
    assert result["solver_calls_started"] == result["solver_calls_completed"] + result["solver_calls_interrupted"]
    interruptions = json.loads((out / "results/evaluation_interruptions.json").read_text())
    assert result["solver_calls_interrupted"] == len(interruptions)
    assert all(row["state"] == "cancelled" and row["stop_reason"] == "wall_time_limit" for row in interruptions)


def test_unknown_request_result_is_not_retried(tmp_path, monkeypatch):
    def respond(prompt, n):
        time.sleep(0.8)
        return 200, "2"
    out, result, prompts, code = run(tmp_path, monkeypatch, responder=respond, extra=["--request-timeout", "0.3"])
    assert result["status"] == "provider_failed"
    assert result["provider_error_code"] == "request_deadline"
    assert result["http_requests"] == 1


def parent_skill(tmp_path, problem="tsp_construct", invalid=False):
    spec = get_problem(problem)
    suite = spec.build_suite(20260908, count=1, size=6, split="dev_train")
    result = SubprocessEvaluator().evaluate(spec.baseline_code, suite)
    code = f"def {spec.entrypoint}(*args):\n    return 'bad'\n" if invalid else spec.baseline_code
    skill = make_skill(version_id="external_seed", code=code, suite_hash=suite["content_hash"], valid=True,
        mean_objective=result.objective, instance_objectives=result.instance_objectives, parent_version_id=None,
        source_attempt_id=None, problem=problem, entrypoint=spec.entrypoint, search_policy_id="external_import")
    save_skill(tmp_path / "parent", skill)
    return tmp_path / "parent"


def test_seed_only_is_not_generated(tmp_path, monkeypatch):
    parent = parent_skill(tmp_path)
    out, result, prompts, code = run(tmp_path, monkeypatch, problem="tsp_construct",
        extra=["--parent-skill", str(parent), "--max-sample-nums", "0", "--n-pop", "0"])
    assert code == 0 and result["status"] == "completed"
    assert result["generated_valid_candidates"] == 0 and result["best_generated_path"] is None
    assert prompts == ["1+1=?"]
    assert load_skill(out / "skills/explicit_parent").parent_version_id == "external_seed"


def test_invalid_parent_never_reaches_provider_or_reusable_parent_store(tmp_path, monkeypatch):
    parent = parent_skill(tmp_path, invalid=True)
    out, result, prompts, code = run(tmp_path, monkeypatch, problem="tsp_construct", extra=["--parent-skill", str(parent)])
    assert code == 2 and result["status"] == "invalid_input" and prompts == []
    assert not (out / "skills/explicit_parent").exists()
    assert not (out / "seeds/parent_skill.json").exists()


def test_zero_wall_has_no_solver_or_http_calls(tmp_path, monkeypatch):
    out, result, prompts, code = run(tmp_path, monkeypatch, extra=["--wall-seconds", "0"])
    assert result["stop_reason"] == "wall_time_limit"
    assert result["solver_calls"] == result["http_requests"] == 0


@pytest.mark.parametrize("extra", [[], ["--max-requests", "0"]])
def test_export_failure_does_not_become_provider_failure(tmp_path, monkeypatch, extra):
    import eoh_frozen.export as exports
    def fail(*args, **kwargs):
        raise OSError("fixture disk failure")
    monkeypatch.setattr(exports, "save_skill", fail)
    out, result, prompts, code = run(tmp_path, monkeypatch, extra=extra)
    assert result["status"] == "export_failed" and code == 2
    assert result["loop_completed"] is False
    if extra:
        assert result["prior_status"] == "stopped" and result["prior_stop_reason"] == "request_limit"
    assert (out / "results/evaluations.jsonl").is_file()


def test_started_evaluation_is_reconciled_without_a_score(tmp_path):
    from eoh_frozen.problem import FrozenProblem
    from eoh_frozen.export import finalize_evaluations
    spec = get_problem("cvrp_construct")
    suite = spec.build_suite(20260908, count=1, size=6, split="dev_train")
    task = FrozenProblem(suite, spec=spec, evaluation_log=tmp_path / "results/evaluations.jsonl")
    task._record_evaluation(spec.baseline_code, None, evaluation_id="interrupted")
    counts = finalize_evaluations(tmp_path, suite, stop_reason="wall_time_limit")
    assert counts["solver_calls_started"] == counts["solver_calls_interrupted"] == 1
    assert counts["solver_calls_completed"] == 0
    row, = json.loads((tmp_path / "results/evaluation_interruptions.json").read_text())
    assert row["evaluation"] is None and row["state"] == "cancelled"


def test_evidence_failure_never_publishes_partial_skill(tmp_path, monkeypatch):
    spec = get_problem("cvrp_construct")
    suite = spec.build_suite(20260908, count=1, size=6, split="dev_train")
    result = SubprocessEvaluator().evaluate(spec.baseline_code, suite)
    skill = make_skill(version_id="atomic", code=spec.baseline_code, suite_hash=suite["content_hash"],
        valid=True, mean_objective=result.objective, instance_objectives=result.instance_objectives,
        parent_version_id=None, source_attempt_id=None, problem=spec.problem_id, entrypoint=spec.entrypoint)
    original = Path.write_text
    def fail_evidence(path, *args, **kwargs):
        if path.name == "evidence.json":
            raise OSError("fixture evidence failure")
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "write_text", fail_evidence)
    with pytest.raises(OSError):
        save_skill(tmp_path / "atomic", skill, evidence={"source": "fixture"})
    assert not (tmp_path / "atomic").exists()
    assert not list(tmp_path.glob("atomic.*"))
