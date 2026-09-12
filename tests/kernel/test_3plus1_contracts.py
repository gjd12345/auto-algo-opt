from __future__ import annotations

import pytest

from agent_skill_loop.contracts_3plus1 import (
    EvaluateDocument,
    PlanDocument,
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
    with pytest.raises(ValueError, match="unknown_fields"):
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


def test_evaluate_memory_contract_obeys_enabled_flag():
    raw = {
        "plan_alignment": "aligned",
        "observations": ["候选在实例 0 改善"],
        "causal_claim": "unproven",
        "memory_action": {"kind": "disabled"},
    }
    assert EvaluateDocument.from_dict(raw, memory_enabled=False).memory_action.kind == "disabled"
    raw["memory_action"] = {"kind": "none"}
    with pytest.raises(ValueError, match="requires_enabled"):
        EvaluateDocument.from_dict(raw, memory_enabled=False)


def test_plan_context_is_bounded():
    plan = PlanDocument.from_dict(plan_payload(), expected_round_id=1, suite_hash="suite-1",
                                  available_feedback_refs={"rounds/round_0000/evaluation_facts.json"}, allowed_targets={"tie_break"})
    with pytest.raises(ValueError, match="too_large"):
        compile_round_context(plan, max_chars=10)
