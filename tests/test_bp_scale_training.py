from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from eoh_rag.experiments.batch_runner import _build_cmd, _validate_manifest


REPO_ROOT = Path(__file__).resolve().parents[1]
BP_EXAMPLE = REPO_ROOT / "official_eoh/examples/bp_online"
if str(BP_EXAMPLE) not in sys.path:
    sys.path.insert(0, str(BP_EXAMPLE))

from prob import BPONLINEBroad  # noqa: E402


def test_balanced_profile_matches_single_scale_item_budget() -> None:
    single, _ = BPONLINEBroad._gen_broad_instances(100, 128, "single_5k")
    balanced, lower_bounds = BPONLINEBroad._gen_broad_instances(
        100, 128, "balanced_1k_5k_10k"
    )

    single_item_budget = sum(
        instance["num_items"] for dataset in single.values() for instance in dataset.values()
    )
    balanced_item_budget = sum(
        instance["num_items"]
        for dataset in balanced.values()
        for instance in dataset.values()
    )
    assert single_item_budget == balanced_item_budget == 640_000
    assert {name: len(dataset) for name, dataset in balanced.items()} == {
        "broad_train_1000": 40,
        "broad_train_5000": 40,
        "broad_train_10000": 40,
    }
    assert set(lower_bounds) == set(balanced)


def test_scale_feedback_manifest_pairs_only_training_profile() -> None:
    manifest = json.loads(
        (
            REPO_ROOT
            / "eoh_rag_workspace/experiments/manifests/bp_scale_balanced_feedback_proxy_v1.json"
        ).read_text(encoding="utf-8")
    )

    assert _validate_manifest(manifest) == []
    assert manifest["seed_list"] == [11001, 11002, 11003]
    assert manifest["generations"] == [2]
    assert manifest["pop_size"] == 3
    assert "held_out_set" not in manifest

    profiles = []
    seed_paths = []
    policies = []
    for arm in manifest["arms"]:
        command = _build_cmd(manifest, "bp_online", arm, 2, 0, "out")
        profiles.append(command[command.index("--bp-training-profile") + 1])
        seed_paths.append(command[command.index("--seed-codes") + 1])
        policies.append(command[command.index("--evolution-feedback-policy") + 1])

    assert profiles == ["single_5k", "balanced_1k_5k_10k"]
    assert seed_paths[0] == seed_paths[1]
    assert policies == ["objective_aware", "objective_aware"]


def test_scale_proxy_candidate_stays_out_of_formal_seed_memory() -> None:
    asset = json.loads(
        (
            REPO_ROOT
            / "eoh_rag_workspace/experiments/assets/bp_online_agent_discovery_scale_v1.json"
        ).read_text(encoding="utf-8")
    )

    assert asset["actor"] == "research_agent_eoh"
    assert asset["selection"]["diagnostic_used_for_selection"] is False
    assert asset["proxy_reliability"]["proxy_gate_passed"] is False
    assert asset["proxy_reliability"]["formal_seed_allowed"] is False
    assert asset["evaluation"]["fresh_diagnostic_wins"] == 52
    assert hashlib.sha256(asset["code"].encode()).hexdigest().upper() == asset[
        "best_code_sha256"
    ]
