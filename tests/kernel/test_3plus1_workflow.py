from __future__ import annotations

import json

import pytest

from agent_skill_loop.contracts_3plus1 import EvaluateDocument, PlanDocument, RoundState
from agent_skill_loop.journal import verify_journal
from agent_skill_loop.workflow import WorkflowRound


def _plan():
    return PlanDocument.from_dict({
        "round_id": 1,
        "direction": "保持接口不变并尝试不同排序",
        "operations": [{"type": "replace", "target": "tie_break", "mechanism": "相对距离"}],
        "preserve": "容量约束",
        "feedback_basis": None,
        "memory_basis": [],
        "hypothesis": "unproven",
    }, expected_round_id=1, suite_hash="suite-1", allowed_targets={"tie_break"})


def test_round_state_machine_is_audited(tmp_path):
    round_dir = tmp_path / "round_0001"
    controller = WorkflowRound(round_dir, RoundState(1, "cvrp_construct", "suite-1", "eval-1"))
    controller.record_plan(_plan())
    controller.begin_execute(round_context="advisory")
    controller.record_evaluation({"status": "completed", "candidates": []})
    controller.record_memory_decision(EvaluateDocument.from_dict({
            "plan_alignment": "aligned", "observations": [], "causal_claim": "unproven",
        "memory_action": {"kind": "disabled"},
    }, memory_enabled=False))
    controller.finish()
    state = json.loads((round_dir / "manifest.json").read_text())
    assert state["status"] == "round_finished"
    journal = verify_journal(round_dir / "journal" / "events.jsonl")
    assert journal["events"] == 6


def test_round_rejects_skipping_execute(tmp_path):
    controller = WorkflowRound(tmp_path / "round", RoundState(1, "cvrp_construct", "suite-1", "eval-1"))
    with pytest.raises(ValueError, match="evaluation_recorded"):
        controller.record_evaluation({})
