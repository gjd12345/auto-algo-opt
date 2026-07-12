import json
from pathlib import Path
from eoh_rag.experiments.strategy_assets import load_and_validate_assets
from scripts.opencode_go_env import build_env

ROOT=Path(__file__).resolve().parents[1]
def test_frozen_strategy_assets_are_balanced_and_valid() -> None:
    strategies,mapping=load_and_validate_assets(ROOT/"eoh_rag_workspace/experiments/strategies/abstract_strategies.json",ROOT/"eoh_rag_workspace/experiments/strategies/transfer_card_map.json")
    assert len(strategies["strategies"])==12
    assert set(mapping["problems"])=={"bp_online","tsp_construct","cvrp_construct"}

def test_cross_manifest_has_30_runs_and_read_only_snapshot() -> None:
    manifest=json.loads((ROOT/"eoh_rag_workspace/experiments/manifests/cross_problem_transfer_v1.json").read_text(encoding="utf-8"))
    assert len(manifest["problems"])*len(manifest["arms"])*len(manifest["seed_list"])==30
    assert manifest["shared_pool_policy"]=="read_only"
    assert manifest["shared_pool_top_k"]==3

def test_opencode_explicit_environment_key_has_priority(monkeypatch) -> None:
    monkeypatch.setenv("OPENCODE_GO_API_KEY", "explicit-test-key")
    env, auth_path = build_env("deepseek-v4-flash", "https://example.invalid")
    assert env["DEEPSEEK_API_KEY"] == "explicit-test-key"
    assert auth_path is None
