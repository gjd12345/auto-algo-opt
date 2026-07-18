from __future__ import annotations

import json
from pathlib import Path

from scripts.research_asset_inventory import build_inventory


ROOT = Path(__file__).resolve().parents[1]
PERSISTED_INVENTORY = ROOT / "agent_records" / "inventories" / "research_assets_v1.json"


def test_persisted_research_asset_inventory_is_current() -> None:
    """事实源变化后必须重新生成清单，避免手工问题数量继续漂移。"""

    generated = build_inventory(ROOT)
    persisted = json.loads(PERSISTED_INVENTORY.read_text(encoding="utf-8"))
    assert persisted == generated


def test_research_asset_inventory_preserves_execution_boundaries() -> None:
    inventory = build_inventory(ROOT)
    current = {
        item["problem_id"] for item in inventory["problem_catalog"]["current_formal_runner"]
    }
    legacy = {
        item["problem_id"] for item in inventory["problem_catalog"]["legacy_go_runner"]
    }

    assert current == {
        "bp_online",
        "tsp_construct",
        "cvrp_construct",
        "tsp_search_controller",
        "cvrp_expert_router",
    }
    assert legacy == {
        "vrp_insertships",
        "knapsack",
        "mixer_split",
        "bin_packing_online",
    }
    assert current.isdisjoint(legacy)
    assert inventory["structural_boundaries"]["per_instance_selector_problem_count"] == 1


def test_research_asset_inventory_verifies_registered_code_hashes() -> None:
    inventory = build_inventory(ROOT)
    records = inventory["algorithm_assets"]["records"]
    selector_records = [item for item in records if item["selector_pool_id"]]
    experiment_records_with_inline_code = [
        item
        for item in records
        if item["origin"] == "automatic_evolution" and item["computed_code_sha256"]
    ]

    assert len(selector_records) == 4
    assert {item["code_hash_status"] for item in selector_records} == {"verified"}
    assert experiment_records_with_inline_code
    assert {
        item["code_hash_status"] for item in experiment_records_with_inline_code
    } == {"verified"}
    assert not inventory["core_benchmarks"]["missing_paths"]
    assert not inventory["core_benchmarks"]["hash_mismatches"]


def test_research_asset_inventory_has_unique_record_ids() -> None:
    records = build_inventory(ROOT)["algorithm_assets"]["records"]
    asset_ids = [item["asset_id"] for item in records]
    assert len(asset_ids) == len(set(asset_ids))
