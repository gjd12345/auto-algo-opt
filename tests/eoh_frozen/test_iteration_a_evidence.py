"""One offline official-EoH path proves the new sidecars compose across rounds."""

import json
import sqlite3
import time

import pytest

pytest.importorskip("eoh")

from agent_skill_loop import session_actions as actions, session_runtime as db
from agent_skill_loop.evaluator import evaluate_candidate_request
from agent_skill_loop.problems.obp import build_suite
from eoh_frozen.smoke import fixture_provider
from agent_skill_loop.session_supervisor import run_startup_preflight


def test_obp_behavior_is_scoped_not_source_identity():
    suite = build_suite(11, count=2, size=14)
    results = [evaluate_candidate_request({"problem": "obp_online", "suite": suite, "code": code}) for code in (
        "def priority(item,bins):\n    return -bins\n",
        "def priority(item,bins):\n    return -2*bins\n",
        "def priority(item,bins):\n    return bins\n",
    )]
    assert all(row["valid"] for row in results)
    first, second, third = [row["metrics"]["behavior_evidence"] for row in results]
    assert first["behavior_signature"] == second["behavior_signature"]
    assert third["behavior_signature"] != first["behavior_signature"]
    partial = evaluate_candidate_request({"problem": "obp_online", "suite": suite, "collect_partial": True,
                                          "code": "def priority(item,bins):\n    return bins[1:]\n"})
    evidence = partial["metrics"]["behavior_evidence"]
    assert evidence["status"] == "partial" and evidence["behavior_signature"] is None


def test_preflight_rejects_loaded_identity_drift_without_effect(tmp_path):
    expected = {"problem": "obp_online", "runtime_source_sha256": "wrong",
                "optimization_skill_sha256": "wrong", "evaluator_hash": "wrong",
                "eoh_commit": "wrong", "problem_spec_hash": "wrong", "eoh_model": "fixture"}
    result = run_startup_preflight(tmp_path, {"task_id": "drift", "round_id": 1}, expected)
    assert result["status"] == "failed" and result["error_code"] == "loaded_identity_mismatch"
    assert result["provider_requests"] == result["solver_calls"] == 0


def test_obp_two_round_population_memory_evidence(tmp_path, monkeypatch):
    monkeypatch.setenv("ITERATION_A_FIXTURE_KEY", "fixture")
    root = tmp_path / "session"
    def responder(prompt, index):
        expression = "-bins" if index % 2 == 0 else "bins"
        code = f"def priority(item: float, bins: np.ndarray) -> np.ndarray:\n    variant = {index}\n    return {expression}\n"
        return 200, "2" if prompt == "1+1=?" else "{Fixture priority}\n```python\n" + code + "```"

    with fixture_provider("obp_online", responder=responder) as (endpoint, prompts):
        db.initialize_session(
            output=root, operation_id="init", eoh_model="fixture", eoh_endpoint=endpoint,
            eoh_api_key_env="ITERATION_A_FIXTURE_KEY", benchmark_id="eohs_v1",
            benchmark_profile_name="obp_evolution_mini", inheritance_mode="population_seeds",
            max_rounds=2, round_budget=20, max_solver_calls=40, eoh_max_requests=20,
            search_policy_defaults={"pop_size": 2, "n_pop": 1, "max_sample_nums": 2},
            memory_store=str(tmp_path / "memory"), memory_enabled=True,
        )
        adopted = None
        for round_id in (1, 2):
            state = db.read_state(run=root)
            actions.memory_search(run=root)
            if adopted:
                actions.memory_read(run=root, reference=adopted)
            plan = {
                "round_id": round_id, "direction": "compare bin priorities",
                "operations": [{"type": "preserve", "target": "interface", "mechanism": "retain benchmark contract"}],
                "preserve": "same suite", "hypothesis": "fixture only", "feedback_basis": state["feedback_basis"],
                "memory_basis": [adopted] if adopted else [],
            }
            plan_file = tmp_path / "plan.json"
            plan_file.write_text(json.dumps(plan), encoding="utf-8")
            submitted = actions.submit_plan(run=root, operation_id=f"plan-{round_id}",
                                            expected_state_version=state["state_version"], file=plan_file)
            launched = actions.execute(run=root, operation_id=f"execute-{round_id}",
                                       expected_state_version=submitted["state_version"])
            if round_id == 1:
                assert launched["result"]["seed_selection"] is None
            else:
                assert launched["result"]["seed_selection"] is not None
            until = time.monotonic() + 75
            while time.monotonic() < until:
                state = db.read_state(run=root)
                if state["task"] and state["task"]["state"] == "EXITED":
                    break
                time.sleep(.1)
            else:
                pytest.fail("fixture supervisor did not terminate")
            collected = actions.collect(run=root, operation_id=f"collect-{round_id}",
                                        expected_state_version=state["state_version"])
            facts = actions.read_evaluation(run=root)["result"]
            assert facts["startup_preflight"]["identity"]["mismatches"] == []
            delta = json.loads((root / facts["execution_delta"]["ref"]).read_text(encoding="utf-8"))
            assert delta["schema_version"].endswith("execution-delta/v1")
            assert any(item["origin"] == "generated" for item in facts["candidates"])
            assert facts["population_snapshot"] is not None
            if round_id == 2:
                assert facts["dual_budget"]["seed_reevaluation_attempts"] >= 2
                assert any(item["lineage_status"] == "verified" and item["generation_parents"]
                           for item in facts["candidates"] if item["origin"] == "generated")
            action = ({"kind": "insight", "name": "fixture-insight", "description": "Scoped fixture observation",
                       "project": "obp_online", "scene": "priority",
                       "body": "Fixture observation only.\n**Why:** Two evaluated candidates.\n**How to apply:** Reevaluate on current suite."}
                      if round_id == 1 else {"kind": "none", "reason": "no new reusable evidence"})
            evaluation = {"plan_alignment": "unknown", "observations": [
                {"claim": "Candidate evidence available", "evidence_refs": [facts["evidence_refs"][0]]}],
                "hypotheses": [], "next_search_advice": {}, "memory_action": action}
            evaluation_file = tmp_path / "evaluation.json"
            evaluation_file.write_text(json.dumps(evaluation), encoding="utf-8")
            evaluated = actions.submit_evaluation(run=root, operation_id=f"evaluation-{round_id}",
                                                  expected_state_version=collected["state_version"], file=evaluation_file)
            if round_id == 1:
                adopted = evaluated["result"]["memory"].get("reference")
                assert adopted
            finished = actions.finish_round(run=root, operation_id=f"finish-{round_id}",
                                            expected_state_version=evaluated["state_version"],
                                            decision="continue" if round_id == 1 else "complete")
            consumption = json.loads((root / finished["result"]["memory_consumption_ref"]).read_text(encoding="utf-8"))
            assert consumption["search_status"] in {"hit", "no_hits"}
            if round_id == 2:
                assert consumption["selected"] == [adopted]
                assert any(receipt["memory"] for receipt in consumption["gateway_requests"]
                           if receipt["context_status"] == "gateway_attempt_exact_context")
        assert finished["run_state"] == "COMPLETED"
        assert prompts
    with sqlite3.connect(root / "session.sqlite3") as con:
        assert con.execute("SELECT COUNT(*) FROM requests").fetchone()[0] == len(prompts)
        assert con.execute("SELECT COUNT(*) FROM solver_calls WHERE state IN ('started','reserved')").fetchone()[0] == 0
    from agent_skill_loop.evidence.report import reconstruct_session_evidence
    rebuilt = reconstruct_session_evidence(root)
    assert len(rebuilt["rounds"]) == 2
    assert rebuilt["total_requests"] == len(prompts)
    assert rebuilt["rounds"][1]["memory_gateway_attempts"] > 0
