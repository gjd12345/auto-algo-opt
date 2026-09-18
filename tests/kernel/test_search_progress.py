from agent_skill_loop.evidence.search_progress import (
    build_search_progress,
    evaluate_stagnation,
    normalize_policy,
)
from agent_skill_loop.benchmark.pilot import build_co_pilot_manifests
from agent_skill_loop.session_runtime import initialize_session, read_state
import json


def _candidate(candidate_id, code_hash, objective, *, valid=True, signature=None, lineage="verified", revision="original"):
    metrics = {}
    if signature is not None:
        metrics["behavior_evidence"] = {
            "status": "complete", "comparable": True,
            "behavior_contract_hash": "b" * 64, "suite_hash": "s" * 64,
            "behavior_signature": signature,
        }
    return {
        "candidate_id": candidate_id, "code_sha256": code_hash,
        "origin": "generated" if revision == "original" else "generated_repair",
        "revision": revision, "valid": valid, "objective": objective,
        "instance_objectives": [objective, objective + 1], "metrics": metrics,
        "lineage_status": lineage,
        "generation_parents": [{"code_sha256": "p" * 64}] if lineage == "verified" else [],
    }


def test_search_progress_reports_scoped_duplicate_yield_lineage_and_diversity():
    first = {"round_id": 1, "objective_direction": "minimize", "incumbent_before": {"objective": 10, "instance_objectives": [5, 5]},
             "incumbent_after": {"objective": 9, "instance_objectives": [4, 5]},
             "candidates": [_candidate("c1", "a" * 64, 9, signature="sig-a"),
                            _candidate("c2", "a" * 64, 9, signature="sig-a"),
                            _candidate("c3", "c" * 64, 11, valid=False, signature=None, lineage="unknown")],
             "request_costs": {"round": {"requests": 3, "input_tokens": 10, "output_tokens": 20, "elapsed_seconds": 1.5},
                               "cumulative": {"requests": 3, "solver_attempts": 3, "input_tokens": 10, "output_tokens": 20, "elapsed_seconds": 1.5}},
             "round_solver_attempts": 3, "dual_budget": {"round_evaluation_attempts": 3}}
    progress = build_search_progress([first], round_id=1, request_costs=first["request_costs"])
    assert progress["source_duplicate_rate"] == 1 / 3
    assert progress["behavior_duplicate_rate"] == 1 / 2
    assert progress["valid_generation_yield"] == 2 / 3
    assert progress["lineage_unknown_rate"] == 1 / 3
    assert progress["instance_response_unique_vector_count"] == 1
    assert progress["requests_per_novel_behavior"] == 3
    assert progress["solver_attempts_per_novel_behavior"] == 3


def test_stagnation_uses_fixed_attempt_window_and_behavior_gate():
    policy = normalize_policy({
        "schema_version": "algorithm-optimization-search-progress-policy/v1",
        "enabled": True, "window_evaluations": 2,
        "min_absolute_gain": 0.5, "min_relative_gain": 0.0,
        "min_behavior_coverage": 1.0,
        "phase_budgets": {"exploration": 1, "exploitation": 1},
        "phase_schedule": ["exploration", "exploitation"],
        "enforce_subbudgets": True,
    }, evaluation_budget=2, max_rounds=2)
    def progress(round_id, before, after, coverage):
        return {"round_id": round_id, "window": {
            "round_solver_attempts": 1,
            "incumbent_before_objective": before,
            "incumbent_after_objective": after,
            "behavior_comparable_count": coverage,
            "generation_attempt_count": 1,
        }}
    result = evaluate_stagnation([progress(1, 10, 10, 1), progress(2, 10, 10, 1)], policy)
    assert result["status"] == "stagnated"
    assert result["reason"] == "gain_or_behavior_coverage_gate_not_met"
    assert evaluate_stagnation([progress(1, 10, 10, 1)], policy)["status"] == "insufficient_window"


def test_co_pilot_freezes_g0_to_g4_factors():
    base = {
        "benchmark_spec_hash": "a" * 64, "metric_spec_hash": "b" * 64,
        "eoh_commit": "eoh", "runtime_hash": "c" * 64, "skill_hash": "d" * 64,
        "model": "qwen/deepseek-v4.1-flash", "endpoint_identity": "router",
        "inheritance_mode": "population_seeds", "feedback_mode": "runtime_facts",
        "agent_guidance": True, "repair_mode": "off", "memory_enabled": False,
        "evaluation_budget": 100, "population_size": 4, "rounds": 2,
        "round_budget": 50, "search_seed": 1234,
    }
    pilot = build_co_pilot_manifests(base)
    assert set(pilot["groups"]) == {"G0", "G1", "G2", "G3", "G4"}
    assert pilot["groups"]["G0"]["manifest"]["memory_enabled"] is False
    assert pilot["groups"]["G3"]["manifest"]["memory_enabled"] is True
    assert pilot["groups"]["G4"]["manifest"]["extra"]["search_progress_policy"]["enforce_subbudgets"] is True
    assert pilot["groups"]["G0"]["manifest"]["extra"]["search_progress_mode"] == "record_only"
    assert pilot["groups"]["G2"]["manifest"]["extra"]["search_progress_mode"] == "expose"


def test_g4_manifest_freezes_policy_in_new_session_without_provider(tmp_path):
    source = tmp_path / "source"
    initialize_session(
        output=source, operation_id="source-init", eoh_model="fixture", eoh_endpoint="offline",
        benchmark_id="eohs_v1", benchmark_profile_name="obp_mini", inheritance_mode="population_seeds",
        max_rounds=2, round_budget=5, max_solver_calls=10,
    )
    base = json.loads((source / "config_frozen.json").read_text(encoding="utf-8"))["experiment_manifest"]["document"]
    g4 = build_co_pilot_manifests(base)["groups"]["G4"]["manifest"]
    target = tmp_path / "g4"
    initialize_session(
        output=target, operation_id="g4-init", experiment_manifest=g4,
        memory_store=str(tmp_path / "g4-memory"), eoh_endpoint="offline", eoh_model="fixture",
        benchmark_id="eohs_v1", benchmark_profile_name="obp_mini",
    )
    config = json.loads((target / "config_frozen.json").read_text(encoding="utf-8"))
    assert config["search_progress"]["policy"]["enforce_subbudgets"] is True
    assert read_state(run=target)["result"]["budgets"]["phase_evaluation_attempts"] == {}
