from __future__ import annotations

import pytest

from agent_skill_loop.session_contracts import (
    PlanDocument,
    build_feedback_summary,
    compile_round_context,
)


def plan_payload(round_id=1):
    return {
        "round_id": round_id,
        "direction": "改变近似平局时的候选排序",
        "operations": [{"type": "replace", "target": "tie_break", "mechanism": "加入相对距离"}],
        "preserve": "容量约束和合法返回值",
        "feedback_basis": {"round_id": 0, "evaluation_ref": "rounds/round_0000/evaluation_facts.json", "suite_hash": "suite-1"},
        "memory_basis": [],
        "reference_skill_ref": None,
        "hypothesis": "可能改善停滞实例，但因果关系未证实",
    }


def test_plan_rejects_unknown_authority_fields_and_compiles_context():
    plan = PlanDocument.from_dict(plan_payload(), expected_round_id=1, suite_hash="suite-1",
                                  available_feedback_refs={"rounds/round_0000/evaluation_facts.json"}, allowed_targets={"tie_break"})
    context = compile_round_context(plan)
    assert "ROUND CONTEXT" in context and "budget" not in context
    metadata_plan = plan_payload()
    metadata_plan.update({"type": "json_object", "reasoning_summary": "non-authoritative provider metadata"})
    PlanDocument.from_dict(metadata_plan, expected_round_id=1, suite_hash="suite-1",
                           available_feedback_refs={"rounds/round_0000/evaluation_facts.json"}, allowed_targets={"tie_break"})
    invalid = plan_payload()
    invalid["budget"] = 3
    with pytest.raises(ValueError, match="forbidden_field"):
        PlanDocument.from_dict(invalid, expected_round_id=1, suite_hash="suite-1")


def test_plan_ignores_known_operation_metadata_without_expanding_authority():
    payload = plan_payload()
    payload["operations"][0]["mechanism_note"] = "advisory only"
    plan = PlanDocument.from_dict(
        payload,
        expected_round_id=1,
        suite_hash="suite-1",
        available_feedback_refs={"rounds/round_0000/evaluation_facts.json"},
        allowed_targets={"tie_break"},
    )
    assert plan.operations[0].as_dict() == {
        "type": "replace",
        "target": "tie_break",
        "mechanism": "加入相对距离",
    }

    payload["operations"][0]["budget"] = 1
    with pytest.raises(ValueError, match="unknown_fields"):
        PlanDocument.from_dict(payload, expected_round_id=1, suite_hash="suite-1")


def test_plan_context_is_bounded():
    plan = PlanDocument.from_dict(plan_payload(), expected_round_id=1, suite_hash="suite-1",
                                  available_feedback_refs={"rounds/round_0000/evaluation_facts.json"}, allowed_targets={"tie_break"})
    with pytest.raises(ValueError, match="too_large"):
        compile_round_context(plan, max_chars=10)


def test_feedback_summary_is_bounded_fact_only_context():
    facts = {
        "round_id": 1,
        "problem": "cvrp_construct",
        "suite_hash": "suite-1",
        "evaluator_hash": "evaluator-1",
        "baseline_code_sha256": "base-sha",
        "baseline": {"valid": True, "objective": 10.0, "instance_objectives": [9.0, 11.0]},
        "incumbent_after": {
            "ref": "rounds/round_0001/exported_skill",
            "origin": "baseline",
            "code_sha256": "base-sha",
            "evaluation_id": "baseline-evaluation",
            "objective": 10.0,
        },
        "candidates": [
            {
                "candidate_id": "baseline", "revision": "original", "origin": "baseline",
                "evaluation_id": "baseline-evaluation", "code_sha256": "base-sha",
                "valid": True, "objective": 10.0, "instance_objectives": [9.0, 11.0],
            },
            {
                "candidate_id": "candidate_1", "revision": "original", "origin": "generated",
                "evaluation_id": "evaluation-1", "code_sha256": "candidate-sha",
                "valid": True, "objective": 8.0, "instance_objectives": [7.0, 9.0],
                "code": "must not be injected",
            },
            {
                "candidate_id": "candidate_2", "revision": "original", "origin": "generated",
                "evaluation_id": "evaluation-2", "code_sha256": "invalid-sha",
                "valid": False, "objective": None, "error_code": "forbidden_attribute",
                "error_detail": "lexsort",
            },
        ],
        "evidence_refs": ["evaluation:evaluation-1", "evaluation:evaluation-2"],
    }
    summary = build_feedback_summary(
        facts,
        evaluation_ref="rounds/round_0001/evaluation_facts.json",
        evaluation_sha256="facts-sha",
        previous_round_id=1,
    )
    plan = PlanDocument.from_dict(plan_payload(2) | {
        "feedback_basis": {"round_id": 1, "evaluation_ref": "rounds/round_0001/evaluation_facts.json", "suite_hash": "suite-1"},
        "reasoning_summary": "The host Agent selected this experiment after comparing the previous facts.",
    }, expected_round_id=2, suite_hash="suite-1",
        available_feedback_refs={"rounds/round_0001/evaluation_facts.json"})
    context = compile_round_context(plan, feedback_summary=summary)
    assert "feedback_summary" in context
    assert "candidate-sha" in context and "forbidden_attribute" in context
    assert "must not be injected" not in context
    assert "reasoning_summary" not in context
    assert summary["objective_delta"] == -2.0
    assert summary["incumbent_candidate_match"]["status"] == "resolved"
    assert summary["generated_candidate_counts"] == {"total": 2, "valid": 1, "invalid": 1}


def test_feedback_never_resolves_incumbent_by_equal_objective():
    facts = {
        "suite_hash": "suite", "evaluator_hash": "evaluator", "baseline": {},
        "incumbent_after": {"code_sha256": "missing", "evaluation_id": "missing-eval", "objective": 1.0},
        "candidates": [{"candidate_id": "tie", "code_sha256": "other", "evaluation_id": "other-eval",
                        "origin": "generated", "valid": True, "objective": 1.0,
                        "instance_objectives": [0.0, 2.0]}],
        "evidence_refs": ["evaluation:other-eval"],
    }
    summary = build_feedback_summary(facts, evaluation_ref="facts.json", evaluation_sha256="sha", previous_round_id=1)
    assert summary["incumbent_candidate_match"]["status"] == "identity_unresolved"
    assert "instance_objectives" not in summary["incumbent"]


def test_feedback_compacts_search_progress_without_losing_full_evidence():
    events = [{
        "attempt_index_in_round": index,
        "evaluation_id": f"evaluation-{index}",
        "generated": index > 1,
        "best_before": 0.0,
        "best_after": 0.0,
        "behavior_comparable": True,
    } for index in range(1, 26)]
    full_window = {
        "attempt_trace": {"complete": True, "declared_attempts": 25, "observed_attempts": 25, "events": events},
        "lineage_parent_frequency": {f"parent-{index}": index for index in range(25)},
        "generation_attempt_count": 24,
        "valid_generation_count": 24,
        "behavior_duplicate_rate": 0.8,
        "round_solver_attempts": 25,
    }
    facts = {
        "suite_hash": "suite-1",
        "baseline": {},
        "incumbent_after": {},
        "candidates": [],
        "search_progress": {
            "schema_version": "algorithm-optimization-search-progress/v1",
            "round_id": 1,
            "window": full_window,
            "cumulative": full_window,
            "policy": {"window_evaluations": 25},
            "stagnation": {"status": "stagnated", "attempts": 25},
        },
    }
    summary = build_feedback_summary(
        facts,
        evaluation_ref="rounds/round_0001/evaluation_facts.json",
        evaluation_sha256="facts-sha",
        previous_round_id=1,
    )
    progress = summary["search_progress"]
    assert "attempt_trace" in facts["search_progress"]["window"]
    assert "attempt_trace" not in progress["window"]
    assert "lineage_parent_frequency" not in progress["cumulative"]
    assert progress["window"]["round_solver_attempts"] == 25

    plan = PlanDocument.from_dict(
        plan_payload(2) | {
            "feedback_basis": {
                "round_id": 1,
                "evaluation_ref": "rounds/round_0001/evaluation_facts.json",
                "suite_hash": "suite-1",
            },
        },
        expected_round_id=2,
        suite_hash="suite-1",
        available_feedback_refs={"rounds/round_0001/evaluation_facts.json"},
    )
    context = compile_round_context(plan, feedback_summary=summary)
    assert len(context) < 12_000
