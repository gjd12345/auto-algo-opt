from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

import pytest

from eoh_rag.experiments.batch_runner import _build_cmd, _validate_manifest
from eoh_rag.search_control.controller_seed_factory import (
    append_agent_discoveries,
    build_diverse_seed_records,
    generate_random_plan,
)
from eoh_rag.search_control.tsp_controller import (
    MAX_TOTAL_BUDGET,
    PRIMITIVE_BUDGET_WEIGHTS,
    build_controller_suite,
    evaluate_controller,
    validate_search_plan,
)


def test_balanced_v2_suites_cover_each_distribution_at_each_size() -> None:
    for suite_name in (
        "synthetic_dev_v2",
        "synthetic_confirm_v2",
        "synthetic_confirm_v3",
        "synthetic_confirm_v4",
    ):
        suite = build_controller_suite(suite_name)
        sizes = sorted({len(instance.initial_route) for instance in suite})
        assert len(suite) == 12
        for size in sizes:
            names = [instance.name for instance in suite if len(instance.initial_route) == size]
            assert len(names) == 3
            assert any(name.startswith("uniform_") for name in names)
            assert any(name.startswith("clustered_") for name in names)
            assert any(name.startswith("ring_") for name in names)


def test_seed_factory_is_deterministic_and_generates_valid_plans() -> None:
    base = [{"algorithm": "base", "code": "def build_search_plan(a, b):\n    return [('two_opt', 1, 0.0)]\n"}]
    first = build_diverse_seed_records(base, total_count=5, random_seed=17)
    second = build_diverse_seed_records(base, total_count=5, random_seed=17)

    assert first == second
    assert first[0] == base[0]
    for record in first:
        namespace: dict[str, object] = {}
        exec(record["code"], namespace)
        plan = namespace["build_search_plan"](100, MAX_TOTAL_BUDGET)
        assert validate_search_plan(plan, MAX_TOTAL_BUDGET)


def test_random_plan_generator_stays_within_weighted_budget() -> None:
    rng = random.Random(23)
    for _ in range(50):
        plan = generate_random_plan(rng)
        validate_search_plan(plan, MAX_TOTAL_BUDGET)
        assert sum(
            PRIMITIVE_BUDGET_WEIGHTS[primitive] * budget
            for primitive, budget, _ in plan
        ) <= MAX_TOTAL_BUDGET


def test_seed_diversity_manifest_freezes_suites_and_seed_hash() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    manifest = json.loads(
        (
            repo_root
            / "eoh_rag_workspace/experiments/manifests/tsp_search_controller_seed_diversity_proxy_v1.json"
        ).read_text(encoding="utf-8")
    )
    seed_path = (
        repo_root
        / "official_eoh/examples/tsp_search_controller/seeds/controller_diverse_seeds_v1.json"
    )
    static_seed_path = (
        repo_root / "official_eoh/examples/tsp_search_controller/seeds/controller_seeds.json"
    )

    assert _validate_manifest(manifest) == []
    assert manifest["controller_dev_suite"] == "synthetic_dev_v2"
    assert manifest["controller_confirm_suite"] == "synthetic_confirm_v2"
    assert hashlib.sha256(seed_path.read_bytes()).hexdigest().upper() == manifest[
        "diverse_seed_asset"
    ]["sha256"]
    assert hashlib.sha256(static_seed_path.read_bytes()).hexdigest().upper() == manifest[
        "diverse_seed_asset"
    ]["static_seed_sha256"]

    diverse_arm = next(arm for arm in manifest["arms"] if arm["name"] == "diverse_seed")
    command = _build_cmd(
        manifest,
        "tsp_search_controller",
        diverse_arm,
        2,
        1,
        "diverse-output",
        seed=9501,
    )
    assert Path(command[command.index("--seed-codes") + 1]) == seed_path.resolve()
    assert command[command.index("--controller-dev-suite") + 1] == "synthetic_dev_v2"
    assert command[command.index("--controller-confirm-suite") + 1] == "synthetic_confirm_v2"


def test_agent_discovery_asset_reproduces_dev_and_confirm_results() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    asset = json.loads(
        (
            repo_root
            / "eoh_rag_workspace/experiments/assets/tsp_search_controller_agent_discovery_v1.json"
        ).read_text(encoding="utf-8")
    )
    namespace: dict[str, object] = {}
    exec(asset["code"], namespace)
    function = namespace["build_search_plan"]

    dev = evaluate_controller(function, build_controller_suite("synthetic_dev_v2"), budget_policy="clip")
    confirm = evaluate_controller(
        function,
        build_controller_suite("synthetic_confirm_v2"),
        budget_policy="clip",
    )

    assert asset["actor"] == "research_agent_eoh"
    assert asset["visibility"]["external_teacher_visible"] is False
    assert asset["visibility"]["confirm_suite_visible_during_evolution"] is False
    assert dev["objective"] == pytest.approx(asset["evaluation"]["agent_dev_objective"], abs=1e-12)
    assert confirm["objective"] == pytest.approx(
        asset["evaluation"]["agent_confirm_objective"], abs=1e-12
    )


def test_second_agent_discovery_reproduces_dev_and_confirm_results() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    asset = json.loads(
        (
            repo_root
            / "eoh_rag_workspace/experiments/assets/tsp_search_controller_agent_discovery_v2.json"
        ).read_text(encoding="utf-8")
    )
    namespace: dict[str, object] = {}
    exec(asset["code"], namespace)
    function = namespace["build_search_plan"]

    dev = evaluate_controller(function, build_controller_suite("synthetic_dev_v2"), budget_policy="clip")
    confirm = evaluate_controller(
        function,
        build_controller_suite("synthetic_confirm_v3"),
        budget_policy="clip",
    )

    assert asset["actor"] == "research_agent_eoh"
    assert asset["visibility"]["external_teacher_visible"] is False
    assert asset["visibility"]["diverse_seed_factory_visible"] is False
    assert dev["objective"] == pytest.approx(asset["evaluation"]["agent_dev_objective"], abs=1e-12)
    assert confirm["objective"] == pytest.approx(
        asset["evaluation"]["agent_confirm_objective"], abs=1e-12
    )


def test_seed_diversity_confirmation_manifest_uses_new_confirm_suite() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    manifest = json.loads(
        (
            repo_root
            / "eoh_rag_workspace/experiments/manifests/tsp_search_controller_seed_diversity_confirm_v1.json"
        ).read_text(encoding="utf-8")
    )

    assert _validate_manifest(manifest) == []
    assert manifest["generations"] == [4]
    assert manifest["pop_size"] == 4
    assert manifest["seed_list"] == [9601, 9602, 9603, 9604, 9605]
    assert manifest["controller_dev_suite"] == "synthetic_dev_v2"
    assert manifest["controller_confirm_suite"] == "synthetic_confirm_v3"
    assert manifest["seed_assets"]["contains_external_teacher"] is False


def test_agent_memory_seed_file_contains_only_agent_discoveries() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    seed_path = (
        repo_root
        / "official_eoh/examples/tsp_search_controller/seeds/controller_agent_memory_seeds_v1.json"
    )
    records = json.loads(seed_path.read_text(encoding="utf-8"))
    agent_assets = [
        json.loads(
            (
                repo_root
                / f"eoh_rag_workspace/experiments/assets/tsp_search_controller_agent_discovery_v{version}.json"
            ).read_text(encoding="utf-8")
        )
        for version in (1, 2)
    ]
    external_teacher = json.loads(
        (
            repo_root
            / "eoh_rag_workspace/experiments/assets/tsp_search_controller_external_teacher_v1.json"
        ).read_text(encoding="utf-8")
    )

    assert len(records) == 14
    assert all(asset["code"] in {record["code"] for record in records} for asset in agent_assets)
    assert all(
        external_teacher["asset_id"] not in record["algorithm"] for record in records
    )
    with pytest.raises(ValueError, match="research_agent_eoh"):
        append_agent_discoveries(records[:1], [external_teacher])


def test_agent_memory_manifest_freezes_new_confirm_suite_and_hash() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    manifest = json.loads(
        (
            repo_root
            / "eoh_rag_workspace/experiments/manifests/tsp_search_controller_agent_memory_proxy_v1.json"
        ).read_text(encoding="utf-8")
    )
    seed_path = (
        repo_root
        / "official_eoh/examples/tsp_search_controller/seeds/controller_agent_memory_seeds_v1.json"
    )

    assert _validate_manifest(manifest) == []
    assert manifest["controller_confirm_suite"] == "synthetic_confirm_v4"
    assert manifest["agent_memory"]["contains_external_teacher"] is False
    assert hashlib.sha256(seed_path.read_bytes()).hexdigest().upper() == manifest[
        "agent_memory"
    ]["sha256"]
