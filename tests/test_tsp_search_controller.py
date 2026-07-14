from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from eoh_rag.experiments.batch_runner import _build_cmd, _validate_manifest
from eoh_rag.search_control.tsp_controller import (
    MAX_TOTAL_BUDGET,
    build_controller_suite,
    evaluate_controller,
    validate_search_plan,
)


def test_validate_search_plan_accepts_weighted_budget_boundary() -> None:
    steps = validate_search_plan(
        [("two_opt", 20, 0.0), ("relocate", 10, 0.001), ("three_opt", 4, 0.0)],
        MAX_TOTAL_BUDGET,
    )

    assert [step.primitive for step in steps] == ["two_opt", "relocate", "three_opt"]


@pytest.mark.parametrize(
    "plan",
    [
        [("unknown", 1, 0.0)],
        [("two_opt", 0, 0.0)],
        [("two_opt", 24, 0.0), ("three_opt", 8, 0.0)],
        [("two_opt", 1, 0.1)],
        [],
    ],
)
def test_validate_search_plan_rejects_unsafe_output(plan: object) -> None:
    with pytest.raises(ValueError):
        validate_search_plan(plan, MAX_TOTAL_BUDGET)


def test_controller_evaluation_is_deterministic_and_improves_routes() -> None:
    suite = build_controller_suite("synthetic_dev_v1")[:2]

    def plan(problem_size: int, total_budget: int) -> list:
        del problem_size, total_budget
        return [("two_opt", 12, 0.0), ("relocate", 6, 0.0)]

    first = evaluate_controller(plan, suite)
    second = evaluate_controller(plan, suite)

    assert first["objective"] == pytest.approx(second["objective"], abs=1e-12)
    assert first["mean_improvement_pct"] > 0.0
    assert first["valid_instances"] == 2
    assert all(item["final_cost"] <= item["initial_cost"] for item in first["instance_results"])


def test_controller_manifest_is_runnable_and_uses_official_seeds() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    manifest = json.loads(
        (repo_root / "eoh_rag_workspace/experiments/manifests/tsp_search_controller_proxy_v1.json").read_text(
            encoding="utf-8"
        )
    )

    assert _validate_manifest(manifest) == []
    command = _build_cmd(
        manifest,
        "tsp_search_controller",
        manifest["arms"][0],
        2,
        1,
        "proxy-output",
        seed=9201,
    )
    assert "--use-official-seed" in command
    assert command[command.index("--problem") + 1] == "tsp_search_controller"


def test_seed_file_contains_only_valid_controller_plans() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    seeds = json.loads(
        (
            repo_root
            / "official_eoh/examples/tsp_search_controller/seeds/controller_seeds.json"
        ).read_text(encoding="utf-8")
    )
    namespace: dict[str, object] = {}
    for seed in seeds:
        exec(seed["code"], namespace)
        function = namespace["build_search_plan"]
        raw_plan = function(100, MAX_TOTAL_BUDGET)
        assert validate_search_plan(raw_plan, MAX_TOTAL_BUDGET)
