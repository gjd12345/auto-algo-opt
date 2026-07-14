from __future__ import annotations

import json
from pathlib import Path

import pytest

from eoh_rag.search_control.tsp_controller import build_controller_suite, evaluate_controller
from scripts.probe_tsp_controller_space import probe_controller_space


def test_controller_space_probe_is_deterministic_and_dev_only() -> None:
    first = probe_controller_space(sample_count=8, random_seed=17)
    second = probe_controller_space(sample_count=8, random_seed=17)

    assert first == second
    assert first["actor"] == "codex_exploration"
    assert first["asset_role"] == "external_teacher_probe"
    assert first["selection_suite"] == "synthetic_dev_v1"
    assert first["confirm_suite_used"] is False
    assert first["evaluated_plan_count"] == 9
    assert first["selected_controller"]["objective"] <= first["baseline"]["objective"]


def test_frozen_external_teacher_reproduces_dev_objective() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    asset = json.loads(
        (
            repo_root
            / "eoh_rag_workspace/experiments/assets/tsp_search_controller_external_teacher_v1.json"
        ).read_text(encoding="utf-8")
    )
    controller = asset["controller"]

    def plan(problem_size: int, total_budget: int) -> list:
        del total_budget
        key = "small_plan" if problem_size <= controller["threshold"] else "large_plan"
        return controller[key]

    result = evaluate_controller(plan, build_controller_suite("synthetic_dev_v1"))

    assert asset["origin"] == "codex_exploration"
    assert asset["confirm_suite_used_for_selection"] is False
    assert result["objective"] == pytest.approx(asset["selected_dev_objective"], abs=1e-12)
