from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.evaluate_bp_generalization import (
    REPO_ROOT,
    _sign_test_p_value,
    evaluate_pair,
    load_candidates,
)


MANIFEST_PATH = (
    REPO_ROOT
    / "eoh_rag_workspace/experiments/manifests/bp_agent_v2_generalization_confirm_v1.json"
)
DUAL_MANIFEST_PATH = (
    REPO_ROOT
    / "eoh_rag_workspace/experiments/manifests/bp_dual_agent_generalization_confirm_v1.json"
)
GATE_MANIFEST_PATH = (
    REPO_ROOT
    / "eoh_rag_workspace/experiments/manifests/bp_confirmation_gate_agent_generalization_confirm_v1.json"
)


def test_generalization_manifest_freezes_new_large_paired_suite() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    candidates = load_candidates(manifest)

    assert manifest["generator"]["item_counts"] == [1000, 5000, 10000]
    assert manifest["generator"]["instances_per_scale"] == 100
    assert manifest["generator"]["seed_start"] == 31000
    assert manifest["comparison"]["previous_15_instance_diagnostic_set_reused"] is False
    assert [candidate["candidate_id"] for candidate in candidates] == [
        "inherited_seed_best",
        "bp_online_agent_discovery_v2",
    ]
    for candidate in candidates:
        assert hashlib.sha256(candidate["code"].encode()).hexdigest().upper() == candidate[
            "code_sha256"
        ]


def test_dual_agent_manifest_freezes_independent_confirmation_suite() -> None:
    manifest = json.loads(DUAL_MANIFEST_PATH.read_text(encoding="utf-8"))
    candidates = load_candidates(manifest)

    # 新确认集不得复用筛选候选时已经查看过的 39000 段实例，避免把诊断结果当作泛化结果。
    assert manifest["generator"]["item_counts"] == [1000, 5000, 10000]
    assert manifest["generator"]["instances_per_scale"] == 100
    assert manifest["generator"]["seed_start"] == 61000
    assert manifest["comparison"]["previous_90_instance_diagnostic_set_reused"] is False
    assert manifest["comparison"]["diagnostic_was_used_to_prioritize_confirmation"] is True
    assert [candidate["candidate_id"] for candidate in candidates] == [
        "inherited_seed_best",
        "bp_online_agent_discovery_dual_v1",
    ]
    assert candidates[1]["actor"] == "research_agent_eoh"
    for candidate in candidates:
        assert hashlib.sha256(candidate["code"].encode()).hexdigest().upper() == candidate[
            "code_sha256"
        ]


def test_confirmation_gate_candidate_stays_pending_before_large_suite() -> None:
    asset_path = (
        REPO_ROOT
        / "eoh_rag_workspace/experiments/assets/bp_online_agent_discovery_gate_v1.json"
    )
    asset = json.loads(asset_path.read_text(encoding="utf-8"))
    manifest = json.loads(GATE_MANIFEST_PATH.read_text(encoding="utf-8"))
    candidates = load_candidates(manifest)

    assert asset["actor"] == "research_agent_eoh"
    assert asset["origin"] == "automatic_evolution"
    assert asset["visibility"]["confirmation_values_visible_to_llm"] is False
    assert asset["visibility"]["confirmation_values_visible_to_acceptance_gate"] is True
    assert asset["selection"]["formal_seed_allowed"] is False
    assert asset["evaluation"]["large_confirmation_status"] == "pending"
    assert hashlib.sha256(asset["code"].encode()).hexdigest().upper() == asset[
        "best_code_sha256"
    ]
    assert manifest["generator"]["seed_start"] == 81000
    assert manifest["generator"]["instances_per_scale"] == 100
    assert manifest["comparison"]["previous_90_instance_diagnostic_set_reused"] is False
    assert manifest["comparison"][
        "diagnostic_was_used_to_select_confirmation_candidate"
    ] is True
    assert [candidate["candidate_id"] for candidate in candidates] == [
        "inherited_seed_best",
        "bp_online_agent_discovery_gate_v1",
    ]


def test_pair_evaluation_is_deterministic_and_strictly_paired() -> None:
    code = "def score(item, bins):\n    return -bins"
    task = {
        "capacity": 100,
        "generator": {
            "distribution": "weibull",
            "shape": 3.0,
            "scale": 45.0,
            "clip_min": 1,
            "clip_max": 100,
        },
        "item_count": 20,
        "instance_index": 0,
        "seed": 123,
        "candidates": [
            {"candidate_id": "a", "code": code},
            {"candidate_id": "b", "code": code},
        ],
    }

    first = evaluate_pair(task)
    second = evaluate_pair(task)

    assert first == second
    assert first["results"]["a"] == first["results"]["b"]


def test_exact_sign_test_excludes_ties() -> None:
    assert _sign_test_p_value(10, 0) < 0.01
    assert _sign_test_p_value(5, 5) == 1.0
