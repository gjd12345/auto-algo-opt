from __future__ import annotations

import json
import hashlib
from pathlib import Path

import pytest

from agent_skill_loop import session_actions
from agent_skill_loop import session_runtime as db
from agent_skill_loop.benchmark.contracts import sha256_json
from agent_skill_loop.benchmark.pilot import build_research_loop_manifests
from agent_skill_loop.benchmark.research_report import build_research_loop_report
from agent_skill_loop.evidence.comparison import build_comparison_packet
from agent_skill_loop.evidence.execution import build_execution_delta
from agent_skill_loop.session_contracts import PlanDocument
from agent_skill_loop.session_runtime import initialize_session


def _behavior(signature, *, status="complete", comparable=True):
    return {"status": status, "comparable": comparable, "behavior_contract_hash": "b" * 64,
            "suite_hash": "s" * 64, "behavior_signature": signature}


def _row(cid, code_hash, evaluation_id, objective, vector, *, origin="generated", parents=None,
         signature=None, valid=True, request=1):
    code = f"def priority(item, bins):\n    return bins  # {cid}\n"
    return {
        "candidate_id": cid, "code": code,
        "code_sha256": hashlib.sha256(code.encode()).hexdigest(), "evaluation_id": evaluation_id, "origin": origin,
        "revision": "original", "source_request_index": request,
        "generation_parents": parents or [], "lineage_status": "verified" if parents else "no_parent",
        "evaluator_hash": "e" * 64, "metric_spec_hash": "m" * 64,
        "evaluation": {"valid": valid, "objective": objective if valid else None,
                       "instance_objectives": vector if valid else None, "suite_hash": "s" * 64,
                       "error_code": None if valid else "invalid_return",
                       "metrics": {"behavior_evidence": _behavior(signature)} if signature else {}},
    }


def test_comparison_packet_selection_is_deterministic_and_exact_identity_only():
    parent = _row("parent", "p" * 64, "eval-parent", 10.0, [5.0, 5.0], origin="baseline", signature="same", request=0)
    child = _row("child", "c" * 64, "eval-child", 8.0, [3.0, 5.0],
                 parents=[{"code_sha256": parent["code_sha256"]}], signature="different", request=2)
    duplicate = _row("duplicate", "d" * 64, "eval-duplicate", 10.0, [6.0, 4.0], signature="same", request=3)
    rows = [parent, child, duplicate]
    delta = build_execution_delta(rows, plan_ref="plan.json", plan_sha256="a" * 64,
                                  hypothesis="test", incumbent_code=parent["code"],
                                  incumbent_ref="parent", reference_skill_ref=None,
                                  behavior_supported=True)
    kwargs = dict(plan={"direction": "test", "hypothesis": "test", "operations": []},
                  plan_ref="plan.json", plan_sha256="a" * 64, execution_delta=delta,
                  search_progress={}, request_costs={}, problem="obp_online", suite_hash="s" * 64)
    first = build_comparison_packet(rows, **kwargs)
    second = build_comparison_packet(list(rows), **kwargs)
    assert first == second
    assert first["slots"]["lineage_contrast"]["candidate"]["evaluation_id"] == "eval-child"
    assert first["slots"]["behavior_duplicate"]["candidate"]["evaluation_id"] == "eval-duplicate"
    assert first["slots"]["behavior_duplicate"]["behavior_relation"] == "same"


def test_effect_contrast_skips_identical_reevaluations():
    repeated_a = _row("explicit_parent", "p" * 64, "eval-a", 1.0, [1.0, 1.0],
                      origin="explicit_parent", signature="same", request=1)
    repeated_b = _row("explicit_parent", "p" * 64, "eval-b", 1.0, [1.0, 1.0],
                      origin="explicit_parent", signature="same", request=2)
    different = _row("candidate", "c" * 64, "eval-c", 1.01, [1.0, 1.02],
                     signature="different", request=3)
    packet = build_comparison_packet(
        [repeated_a, repeated_b, different],
        plan={"direction": "test", "hypothesis": "test", "operations": []},
        plan_ref="plan.json", plan_sha256="a" * 64, execution_delta={"candidates": []},
        search_progress={}, request_costs={}, problem="obp_online", suite_hash="s" * 64,
    )
    effect = packet["slots"]["effect_contrast"]
    assert packet["selection_policy_version"] == "obp-research-contrasts/v2"
    assert effect["status"] == "available"
    assert effect["instance_objective_l1"] > 0
    assert {effect["left"]["evaluation_id"], effect["right"]["evaluation_id"]} != {"eval-a", "eval-b"}


def test_reflection_basis_is_required_or_forbidden_by_treatment_contract():
    payload = {
        "round_id": 2, "direction": "next", "operations": [{"type": "replace", "target": "ranking", "mechanism": "contrast"}],
        "preserve": "contract", "feedback_basis": None, "memory_basis": [], "reference_skill_ref": None,
        "hypothesis": "bounded", "reflection_basis": {"round_id": 1, "evaluation_ref": "rounds/round_0001/evaluation.submitted.json",
                                                         "evaluation_sha256": "a" * 64},
    }
    expected = payload["reflection_basis"]
    plan = PlanDocument.from_dict(payload, expected_round_id=2, suite_hash="suite",
                                  available_reflection_basis=expected, reflection_requirement="required")
    assert plan.reflection_basis.as_dict() == expected
    with pytest.raises(ValueError, match="forbidden"):
        PlanDocument.from_dict(payload, expected_round_id=2, suite_hash="suite",
                               available_reflection_basis=expected, reflection_requirement="forbidden")


def test_research_loop_manifest_freezes_budget_inputs_and_online_memory_source():
    base = {
        "benchmark_spec_hash": "a" * 64, "metric_spec_hash": "b" * 64,
        "eoh_commit": "eoh", "runtime_hash": "c" * 64, "skill_hash": "d" * 64,
        "model": "model", "endpoint_identity": "offline", "inheritance_mode": "population_seeds",
        "feedback_mode": "runtime_facts", "agent_guidance": True, "repair_mode": "off",
        "memory_enabled": False, "evaluation_budget": 20, "population_size": 4,
        "rounds": 2, "round_budget": 10, "search_seed": 7,
    }
    pilot = build_research_loop_manifests(base)
    assert set(pilot["groups"]) == {"A", "B", "C"}
    for group in pilot["groups"].values():
        assert (group["manifest"]["evaluation_budget"], group["manifest"]["rounds"],
                group["manifest"]["round_budget"]) == (100, 4, 25)
        assert group["manifest"]["extra"]["comparison_packet_policy"] == "obp-research-contrasts/v2"
        assert group["manifest"]["extra"]["population_seed_policy"] == \
            "verified_final_population_up_to_capacity_minimum_one"
    assert pilot["groups"]["C"]["manifest"]["memory_enabled"] is True
    assert pilot["groups"]["C"]["manifest"]["extra"]["memory_source"] == "run_internal_empty_start"


def test_controller_usage_records_unavailable_tokens_as_unknown(tmp_path):
    run = tmp_path / "run"
    initialize_session(output=run, operation_id="init", eoh_model="fixture", memory_enabled=False,
                       size=4, count=1)
    event = tmp_path / "usage.json"
    event.write_text(json.dumps({
        "schema_version": "algorithm-optimization-controller-usage/v1", "event_id": "round-1-plan",
        "round_id": 1, "treatment": "", "activity": "plan", "model": "host-agent",
        "input_tokens": None, "output_tokens": None, "elapsed_seconds": 1.0,
        "availability": "unavailable", "unavailable_reason": "host_usage_unavailable", "source": "host",
    }), encoding="utf-8")
    result = session_actions.record_controller_usage(run=run, file=event)
    stored = json.loads((run / result["result"]["event_ref"]).read_text(encoding="utf-8"))
    assert stored["availability"] == "unavailable"
    assert stored["total_tokens"] is None


def _write_bundle(root: Path, group: str, seed: int) -> None:
    def write(ref, payload):
        path = root / ref
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")

    treatment = {"A": "facts_to_plan", "B": "explicit_reflection", "C": "reflection_with_online_memory"}[group]
    manifest = {
        "evaluation_budget": 100, "rounds": 4, "round_budget": 25,
        "memory_enabled": group == "C", "extra": {
            "research_loop_schema": "algorithm-optimization-research-loop-pilot/v1",
            "problem_scope": "obp_online", "benchmark_profile": "obp_evolution_mini",
            "primary_budget_resource": "solver_calls", "comparison_packet_policy": "obp-research-contrasts/v2",
            "heldout_policy": "locked_no_access_diagnostic", "treatment": treatment,
            "memory_source": "run_internal_empty_start" if group == "C" else "disabled",
        },
    }
    write("experiment_manifest.json", {"sha256": sha256_json(manifest), "document": manifest})
    evaluation_id, code_hash = f"eval-{group}-{seed}", hashlib.sha256(f"{group}-{seed}".encode()).hexdigest()
    write("bundle.json", {"run_id": f"run-{group}-{seed}", "run_state": "COMPLETED"})
    write("budget_receipt.json", {
        "solver_calls": [{"round_id": 1, "evaluation_id": evaluation_id, "code_sha256": code_hash,
                          "state": "complete", "valid": 1, "objective": float(seed)}],
        "requests": [], "tasks": [{"round_id": round_id, "engine_elapsed_seconds": 1.0}
                                    for round_id in range(1, 5)],
    })
    write("controller_usage.json", {"events": []})
    write("cost_summary.json", {
        "eoh_provider": {"status": "unavailable", "input_tokens": None, "output_tokens": None},
        "outer_controller": {"status": "unavailable", "input_tokens": None, "output_tokens": None},
        "total_model_token_status": "incomplete", "total_model_tokens": None,
    })
    previous_ref = previous_sha = None
    for round_id in range(1, 5):
        prefix = f"rounds/round_{round_id:04d}"
        evaluation_ref = f"{prefix}/evaluation.submitted.json"
        write(evaluation_ref, {"observations": [], "hypotheses": [], "next_search_advice": {}})
        evaluation_sha = hashlib.sha256((root / evaluation_ref).read_bytes()).hexdigest()
        basis = None if group == "A" or round_id == 1 else {
            "round_id": round_id - 1, "evaluation_ref": previous_ref, "evaluation_sha256": previous_sha,
        }
        write(f"{prefix}/plan.json", {"round_id": round_id, "reflection_basis": basis})
        write(f"{prefix}/comparison_packet.json", {"schema_version": "algorithm-optimization-comparison-packet/v1"})
        candidate = {"evaluation_id": evaluation_id, "code_sha256": code_hash, "origin": "generated",
                     "valid": True, "objective": float(seed), "instance_objectives": [float(seed), float(seed + 1)]}
        write(f"{prefix}/evaluation_facts.json", {
            "round_id": round_id, "candidates": [candidate] if round_id == 1 else [],
            "search_progress": {"cumulative": {"behavior_duplicate_count": 0,
                                                  "behavior_comparable_count": 1}},
        })
        previous_ref, previous_sha = evaluation_ref, evaluation_sha
    if group == "C":
        write("rounds/round_0002/memory_consumption.json", {
            "round_id": 2, "publication": {"writes": []},
            "searched": [{"results": ["memory://run/round1/insight"]}],
            "read": [{"reference": "memory://run/round1/insight", "status": "complete"}],
            "selected": ["memory://run/round1/insight"],
            "gateway_requests": [{"input_ref": "request-1.json",
                                  "context_status": "gateway_attempt_exact_context"}],
        })
    hashes = {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
              for path in root.rglob("*") if path.is_file()}
    write("SHA256SUMS.json", hashes)


def test_research_report_requires_hash_checked_three_seed_matrix_and_keeps_unknown_costs_null(tmp_path):
    runs = []
    for seed in (1, 2, 3):
        for group in ("A", "B", "C"):
            relative = Path(f"{group}-{seed}")
            _write_bundle(tmp_path / relative, group, seed)
            runs.append({"group": group, "seed": seed, "bundle": relative.as_posix()})
    report = build_research_loop_report({
        "schema_version": "algorithm-optimization-research-loop-index/v1", "runs": runs,
    }, base_dir=tmp_path)
    assert report["readiness"]["three_seed_paired_matrix"] is True
    assert report["readiness"]["all_runs_auditable"] is True
    assert all(run["cost_summary"]["total_model_tokens"] is None for run in report["runs"])
    assert all(report["readiness"]["memory_reuse_observed_by_seed"].values())


def test_stagnated_continue_requires_evidence_bound_observation_and_direction(tmp_path):
    run = tmp_path / "stagnated"
    initialize_session(output=run, operation_id="init", eoh_model="fixture", memory_enabled=False,
                       size=4, count=1, max_rounds=2)
    evidence_ref = "rounds/round_0001/comparison_packet.json"
    session_actions.save(run, evidence_ref, {"slot": "design"})
    facts_ref = "rounds/round_0001/evaluation_facts.json"
    facts_sha = session_actions.save(run, facts_ref, {
        "evidence_refs": [evidence_ref],
        "search_progress": {"stagnation": {"status": "stagnated"}},
    })

    def install_evaluation(payload):
        ref = "rounds/round_0001/evaluation.submitted.json"
        sha = session_actions.save(run, ref, payload)
        con = db._connect(run / "session.sqlite3")
        try:
            con.execute("""UPDATE rounds SET state='READY_TO_FINISH', memory_commit_status='none',
                        evaluation_facts_ref=?, evaluation_facts_sha256=?,
                        submitted_evaluation_ref=?, submitted_evaluation_sha256=? WHERE round_id=1""",
                        (facts_ref, facts_sha, ref, sha))
        finally:
            con.close()

    install_evaluation({"observations": [], "next_search_advice": {}})
    with pytest.raises(db.SessionError, match="STAGNATION_CONTINUE_EVIDENCE_REQUIRED"):
        session_actions.finish_round(run=run, operation_id="continue-1", expected_state_version=1,
                                     decision="continue")
    install_evaluation({"observations": [{"claim": "fact", "evidence_refs": [evidence_ref]}],
                        "next_search_advice": {}})
    with pytest.raises(db.SessionError, match="STAGNATION_CONTINUE_JUSTIFICATION_REQUIRED"):
        session_actions.finish_round(run=run, operation_id="continue-2", expected_state_version=1,
                                     decision="continue")
    install_evaluation({"observations": [{"claim": "fact", "evidence_refs": [evidence_ref]}],
                        "next_search_advice": {"direction": "distinguish the two mechanisms"}})
    result = session_actions.finish_round(run=run, operation_id="continue-3", expected_state_version=1,
                                          decision="continue")
    assert result["round_id"] == 2
