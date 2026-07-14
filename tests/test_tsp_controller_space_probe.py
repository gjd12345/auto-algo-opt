from __future__ import annotations

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
