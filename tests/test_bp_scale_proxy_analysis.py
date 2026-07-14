from __future__ import annotations

import json

from scripts.analyze_bp_scale_proxy import REPO_ROOT, gate_checks


def test_proxy_diagnostic_is_frozen_before_result_inspection() -> None:
    manifest = json.loads(
        (
            REPO_ROOT
            / "eoh_rag_workspace/experiments/manifests/bp_scale_proxy_diagnostic_v1.json"
        ).read_text(encoding="utf-8")
    )

    assert manifest["freeze_timing"] == "after_generation_before_result_inspection"
    assert manifest["pair_seeds"] == [11001, 11002, 11003]
    assert manifest["generator"]["instances_per_scale"] == 30
    assert manifest["generator"]["seed_start"] == 36000
    assert manifest["proxy_gate"]["valid_instance_pairs_min"] == 270


def test_proxy_gate_requires_both_overall_and_small_scale_support() -> None:
    manifest = {
        "proxy_gate": {
            "valid_instance_pairs_min": 270,
            "balanced_beats_single_seed_pairs_min": 2,
            "balanced_1k_mean_gap_not_worse_seed_pairs_min": 2,
        }
    }
    pair = lambda overall, small: {  # noqa: E731 - 测试中直白构造三个配对摘要
        "overall": {"pairs": 90, "gap_reduction_pct_points": {"mean": overall}},
        "by_scale": {"1000": {"gap_reduction_pct_points": {"mean": small}}},
    }

    checks = gate_checks([pair(1, 1), pair(1, 0), pair(-1, -1)], [], manifest)

    assert all(checks.values())


def test_structured_proxy_diagnostic_is_frozen_before_generation() -> None:
    manifest = json.loads(
        (
            REPO_ROOT
            / "eoh_rag_workspace/experiments/manifests/bp_scale_structured_proxy_diagnostic_v1.json"
        ).read_text(encoding="utf-8")
    )

    assert manifest["freeze_timing"] == "before_generation"
    assert manifest["pair_seeds"] == [12001, 12002, 12003]
    assert manifest["generator"]["seed_start"] == 37000
    assert manifest["baseline_arm"] == "scalar_feedback"
    assert manifest["agent_arm"] == "scale_aware_feedback"


def test_robust_proxy_diagnostic_is_frozen_before_generation() -> None:
    manifest = json.loads(
        (
            REPO_ROOT
            / "eoh_rag_workspace/experiments/manifests/bp_robust_feedback_proxy_diagnostic_v1.json"
        ).read_text(encoding="utf-8")
    )

    assert manifest["freeze_timing"] == "before_generation"
    assert manifest["pair_seeds"] == [13001, 13002, 13003]
    assert manifest["generator"]["seed_start"] == 38000
    assert manifest["baseline_arm"] == "scalar_feedback"
    assert manifest["agent_arm"] == "robust_feedback"
