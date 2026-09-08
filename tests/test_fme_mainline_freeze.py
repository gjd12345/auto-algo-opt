"""FME 主线与 RQ1b 协议的最小冻结测试；不调用模型、不跑求解器。"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from eoh_rag.fme.controller import FMEAction, FMEController, FMEControllerState
from eoh_rag.fme.mainline import MAINLINE_PROBLEMS, build_fme_mainline
from eoh_rag.fme.online_pilot import FixedGenerationController
from eoh_rag.fme.research_loop import (
    FMEReplayContractError,
    FMEResearchLoop,
    FrozenReplayContract,
    ReplayActionResult,
    ReplayEvidenceState,
)
from eoh_rag.fme.rq1b import load_and_freeze


ROOT = Path(__file__).resolve().parents[1]
RQ1B_MANIFEST = (
    ROOT
    / "eoh_rag_workspace"
    / "experiments"
    / "manifests"
    / "refactor0830_rq1b_v2.json"
)
EVIDENCE = hashlib.sha256(b"fme-dev-evidence").hexdigest()
CONTRACT = hashlib.sha256(b"fme-dev-contract").hexdigest()
OUTPUT = hashlib.sha256(b"fme-dev-output").hexdigest()


def _state(**overrides: object) -> ReplayEvidenceState:
    payload = dict(
        remaining_evaluation_budget=8,
        algorithm_archive_size=0,
        counterexample_archive_size=0,
        proposed_claim_count=0,
        weakened_claim_count=0,
        supported_claim_count=0,
        pending_counterexample_comparisons=0,
        transferable_claim_count=0,
        stalled_ticks=0,
        recent_generation_attempts=0,
        recent_generation_failures=0,
        consecutive_transfer_actions=0,
        evidence_hashes=(EVIDENCE,),
        visible_scope="dev_only",
    )
    payload.update(overrides)
    return ReplayEvidenceState(**payload)  # type: ignore[arg-type]


def _contract(*actions: FMEAction) -> FrozenReplayContract:
    return FrozenReplayContract(
        contract_id="test-fme-freeze",
        contract_hash=CONTRACT,
        allowed_actions=actions or (FMEAction.INVENT_ALGORITHM, FMEAction.STOP_BRANCH),
    )


def test_mainline_registers_three_problems_and_one_controller() -> None:
    composition = build_fme_mainline()
    assert MAINLINE_PROBLEMS == ("bp_online", "tsp_construct", "cvrp_construct")
    assert tuple(composition.problem_adapters) == MAINLINE_PROBLEMS
    assert composition.top_level_controller == "FMEResearchLoop"


def test_empty_archive_invents_and_exhausted_budget_stops() -> None:
    controller = FMEController()
    invent = controller.choose_action(
        FMEControllerState(
            remaining_evaluation_budget=4,
            algorithm_archive_size=0,
            counterexample_archive_size=0,
            proposed_claim_count=0,
            weakened_claim_count=0,
            supported_claim_count=0,
            pending_counterexample_comparisons=0,
            transferable_claim_count=0,
        )
    )
    assert invent.action is FMEAction.INVENT_ALGORITHM
    assert invent.allowed_eoh_operators == ("i1", "e1")

    stop = controller.choose_action(
        FMEControllerState(
            remaining_evaluation_budget=0,
            algorithm_archive_size=3,
            counterexample_archive_size=1,
            proposed_claim_count=1,
            weakened_claim_count=0,
            supported_claim_count=0,
            pending_counterexample_comparisons=0,
            transferable_claim_count=0,
        )
    )
    assert stop.action is FMEAction.STOP_BRANCH
    assert stop.reason == "evaluation_budget_exhausted"


def test_fixed_generation_controller_does_not_schedule_active_science() -> None:
    decision = FixedGenerationController().choose_action(
        FMEControllerState(
            remaining_evaluation_budget=6,
            algorithm_archive_size=4,
            counterexample_archive_size=2,
            proposed_claim_count=2,
            weakened_claim_count=1,
            supported_claim_count=1,
            pending_counterexample_comparisons=1,
            transferable_claim_count=1,
        )
    )
    assert decision.action is FMEAction.INVENT_ALGORITHM
    assert decision.reason == "preregistered_passive_generation"


def test_research_loop_rejects_held_out_state() -> None:
    loop = FMEResearchLoop()
    with pytest.raises(FMEReplayContractError, match="state_scope_not_dev_only"):
        loop.run(_contract(), _state(visible_scope="heldout"))


def test_research_loop_invents_when_adapter_completes() -> None:
    loop = FMEResearchLoop()

    def invent(_state: ReplayEvidenceState) -> ReplayActionResult:
        return ReplayActionResult(
            action=FMEAction.INVENT_ALGORITHM,
            status="completed",
            output_evidence_hashes=(OUTPUT,),
            algorithm_delta=1,
        )

    outcome = loop.run(
        _contract(FMEAction.INVENT_ALGORITHM, FMEAction.STOP_BRANCH),
        _state(),
        adapters={FMEAction.INVENT_ALGORITHM: invent},
    )
    assert outcome.stop_record is None
    assert outcome.action_result is not None
    assert outcome.decision.action is FMEAction.INVENT_ALGORITHM
    assert outcome.next_state.algorithm_archive_size == 1
    assert outcome.next_state.remaining_evaluation_budget == 7
    assert OUTPUT in outcome.next_state.evidence_hashes


def test_rq1b_manifest_rejects_non_cvrp_and_active_controller(tmp_path: Path) -> None:
    raw = json.loads(RQ1B_MANIFEST.read_text(encoding="utf-8"))
    raw["problems"] = ["tsp_construct"]
    bad_problem = tmp_path / "bad_problem.json"
    bad_problem.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="rq1b_cvrp_only"):
        load_and_freeze(bad_problem, fixture=True)

    raw = json.loads(RQ1B_MANIFEST.read_text(encoding="utf-8"))
    raw["arms"][2]["controller"] = "active"
    bad_arm = tmp_path / "bad_arm.json"
    bad_arm.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="rq1b_fixed_generation_only"):
        load_and_freeze(bad_arm, fixture=True)


def test_rq1b_fixture_freeze_does_not_call_a_model() -> None:
    protocol = load_and_freeze(RQ1B_MANIFEST, fixture=True)
    assert protocol["mode"] == "integration_smoke"
    assert protocol["resolved_model"] == "integration-fixture/primary"
    assert protocol["problems"] == ["cvrp_construct"]
    assert [arm["id"] for arm in protocol["arms"]] == [
        "scalar",
        "passive",
        "behavior_grounded",
    ]
    assert protocol["expected_cells"] == 3
    assert "suite_hashes" in protocol and protocol["suite_hashes"]
    assert "panel_hashes" in protocol and protocol["panel_hashes"]
