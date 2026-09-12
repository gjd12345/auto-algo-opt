from __future__ import annotations

import json
import time

from agent_skill_loop.contracts_3plus1 import EvaluateDocument, MemoryAction
from agent_skill_loop.memory import MemoryAPI, MemoryEntry
from agent_skill_loop.skill_store import make_skill, publish_export_ref, save_skill
from agent_skill_loop.workflow import WorkflowRunner
from eoh_frozen.smoke import fixture_provider


def _plan(prompt: str, **_kwargs: object) -> str:
    payload = json.loads(prompt)
    return json.dumps({
        "round_id": payload["round_id"],
        "direction": "保持接口并调整启发式排序",
        "operations": [{"type": "replace", "target": "tie_break", "mechanism": "按剩余容量排序"}],
        "preserve": "接口、容量约束、确定性评测",
        "feedback_basis": None,
        "memory_basis": [],
        "reference_skill_ref": None,
        "hypothesis": "unknown",
    })


def test_provider_terminal_stops_before_evaluate_and_accounts_request(tmp_path, monkeypatch):
    monkeypatch.setenv("REPAIR_FIXTURE_KEY", "fixture")
    evaluate_calls: list[str] = []

    def evaluate_request(prompt: str, **_kwargs: object) -> str:
        evaluate_calls.append(prompt)
        return json.dumps({"plan_alignment": "unknown", "observations": [], "causal_claim": "unknown", "memory_action": {"kind": "disabled"}})

    with fixture_provider("cvrp_construct", responder=lambda _prompt, _index: (401, "bad key")) as (endpoint, prompts):
        result = WorkflowRunner(
            tmp_path / "workflow", model="fixture", endpoint=endpoint, api_key_env="REPAIR_FIXTURE_KEY",
            max_rounds=1, max_requests=5, count=1, size=6, pop_size=2, n_pop=1, max_sample_nums=1,
            plan_request=_plan, evaluate_request=evaluate_request,
        ).run()
    assert result["status"] == "provider_failed"
    assert result["request_used"] == len(prompts) == 1
    assert result["rounds"][0]["eoh"]["status"] == "provider_failed"
    assert not evaluate_calls
    skipped = json.loads((tmp_path / "workflow/rounds/round_0001/evaluate_skipped.json").read_text())
    assert skipped["agent_evaluate"] == "skipped" and skipped["memory_decision"] == "not_run"


def test_deadline_reconciles_child_and_writes_recovered_summary(tmp_path, monkeypatch):
    monkeypatch.setenv("REPAIR_SLOW_KEY", "fixture")

    def slow_response(prompt: str, _index: int):
        if prompt == "1+1=?":
            time.sleep(2.0)
        else:
            time.sleep(2.0)
        return 200, "{}"

    with fixture_provider("cvrp_construct", responder=slow_response) as (endpoint, _prompts):
        result = WorkflowRunner(
            tmp_path / "workflow", model="fixture", endpoint=endpoint, api_key_env="REPAIR_SLOW_KEY",
            max_rounds=1, max_requests=5, wall_seconds=1.0, request_timeout=5.0,
            count=1, size=6, pop_size=2, n_pop=1, max_sample_nums=1, plan_request=_plan,
            evaluate_request=lambda **_kwargs: json.dumps({"plan_alignment": "unknown", "observations": [], "causal_claim": "unknown", "memory_action": {"kind": "disabled"}}),
        ).run()
    eoh = result["rounds"][0]["eoh"]
    assert result["status"] == "stopped"
    assert eoh["status"] == "stopped" and eoh["stop_reason"] == "wall_time_limit"
    assert 0 <= result["request_used"] <= 5
    assert (tmp_path / "workflow/rounds/round_0001/eoh_run/summary.json").is_file()
    assert (tmp_path / "workflow/rounds/round_0001/evaluate_skipped.json").is_file()


def test_memory_is_versioned_and_does_not_cross_projects_by_default(tmp_path):
    api = MemoryAPI(tmp_path / "memory")
    base = MemoryEntry("same", "same problem insight", "insight", "cvrp_construct", "select_next_node", "one\n\n**Why:** first\n\n**How to apply:** use one")
    other = MemoryEntry("other", "other problem insight", "insight", "other_problem", "select_next_node", "other\n\n**Why:** other\n\n**How to apply:** use other")
    first = api.write(base)
    second = api.write(MemoryEntry(**{**base.__dict__, "body": "two\n\n**Why:** second\n\n**How to apply:** use two"}), based_on=first["reference"])
    api.write(other)
    assert first["reference"].endswith("@v0001") and second["reference"].endswith("@v0002")
    result = api.read("insight", project="cvrp_construct", scene="select_next_node")
    assert [row["reference"] for row in result["memories"]] == [second["reference"]]
    assert api.read_version(second["reference"])["body"] .startswith("two")
    assert not api.read("other", project="cvrp_construct", scene="select_next_node")["memories"]


def test_incumbent_and_solution_gate_use_same_round_trusted_asset(tmp_path):
    runner = WorkflowRunner(
        tmp_path / "workflow", model="fixture", max_rounds=1, max_requests=1,
        plan_request=_plan, evaluate_request=lambda **_kwargs: "{}",
    )
    eoh_root = tmp_path / "round" / "eoh_run"
    baseline_code = runner.spec.baseline_code
    generated_code = baseline_code + "\n# generated\n"

    def put(path, version, code, objective, evidence=None, origin="generated"):
        skill = make_skill(version_id=version, code=code, suite_hash=runner.suite["content_hash"], valid=True,
                           mean_objective=objective, instance_objectives=(objective,), parent_version_id=None,
                           source_attempt_id=1, problem=runner.spec.problem_id, entrypoint=runner.spec.entrypoint,
                           origin=origin)
        save_skill(path, skill, evidence=evidence)

    put(eoh_root / "skills" / "baseline", "baseline", baseline_code, 10.0, origin="baseline")
    put(eoh_root / "skills" / "generated_1", "generated_1", generated_code, 20.0,
        evidence={"evaluation_line": 2, "source_request_index": 1, "local_objective": 20.0})
    publish_export_ref(eoh_root, eoh_root / "skills" / "baseline")
    runner._update_incumbent(tmp_path / "round", {"best_generated_path": "skills/generated_1", "exported_skill": "exported_skill"})
    assert runner.current_objective == 10.0

    evidence = {"evaluation_line": 2, "source_request_index": 7, "local_objective": 9.4}
    put(eoh_root / "skills" / "generated_2", "generated_2", baseline_code + "\n# better\n", 9.4, evidence=evidence)
    action = MemoryAction("solution", based_on="eoh_run/skills/generated_2")
    facts = {
        "generated_valid_candidates": 2, "best_generated_path": "skills/generated_2",
        "best_objective": 1.0,
        "baseline": {"objective": 10.0},
        "evaluations": [{"evaluation_line": 2, "source_request_index": 7,
                          "code_sha256": json.loads((eoh_root / "skills" / "generated_2" / "skill.json").read_text())["code_sha256"],
                          "problem": runner.problem, "entrypoint": runner.spec.entrypoint,
                          "evaluation": {"suite_hash": runner.suite["content_hash"], "objective": 9.4}}],
    }
    assert runner._solution_eligible(tmp_path / "round", facts, action)
    assert not runner._solution_eligible(tmp_path / "round", {**facts, "best_generated_path": "skills/generated_1"}, action)

    runner.memory = MemoryAPI(tmp_path / "memory")
    action = MemoryAction(
        "solution", name="generated-solution", description="可信生成技能", project="cvrp_construct",
        scene="select_next_node", body="可复用技能。\n\n**Reusable Experience:** 先在同一套件重评，再迁移。",
        based_on="eoh_run/skills/generated_2",
    )
    runner._write_memory_action(tmp_path / "round", EvaluateDocument("unknown", (), "unknown", action), facts)
    result = json.loads((tmp_path / "round/memory_result.json").read_text())
    assert result["written"] is True and result["reference"].endswith("@v0001")


def test_plan_failure_preserves_raw_exchange_and_refreshes_budget_snapshot(tmp_path):
    runner: WorkflowRunner

    def bad_plan(prompt: str, **_kwargs: object) -> str:
        slot = runner.budget.reserve(purpose="plan", problem="cvrp_construct", model="fixture")
        assert slot is not None
        runner.budget.finish(slot, "complete", status=200, model="fixture", input_tokens=1, output_tokens=1)
        return '{"budget": 1}'

    runner = WorkflowRunner(
        tmp_path / "workflow", model="fixture", max_rounds=1, max_requests=3,
        plan_request=bad_plan,
    )
    result = runner.run()
    round_root = tmp_path / "workflow" / "rounds" / "round_0001"
    manifest = json.loads((round_root / "manifest.json").read_text())
    assert result["status"] == "stopped"
    assert result["request_used"] == 1 and result["remaining_requests"] == 2
    assert manifest["remaining_requests"] == result["remaining_requests"]
    assert '"budget": 1' in (round_root / "journal" / "responses" / "attempt_1.txt").read_text()
    assert '"role":"plan"' in (round_root / "journal" / "prompts" / "attempt_1.txt").read_text()
