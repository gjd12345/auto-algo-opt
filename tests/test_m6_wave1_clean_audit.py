"""Unit tests for Wave 1 (A1-A4) clean audit helpers, quadrant identity, and leak guards."""

from __future__ import annotations

import pytest

from tools.run_m6_wave1_clean_audit import (
    assert_no_blind_leakage,
    compute_quadrant_decomposition,
    is_strict_completed_before_deadline,
    reevaluate_baselines_row,
)


def test_quadrant_decomposition_exact_identity() -> None:
    # 4 instances matching all 4 quadrants:
    # idx 0: both completed (cand better by 2.0)
    # idx 1: cand_only completed (cand=12, base penalized 2*10=20 -> +8.0)
    # idx 2: base_only completed (cand penalized 2*15=30, base=16 -> -14.0)
    # idx 3: both penalized (20 vs 20 -> 0.0)
    dec = compute_quadrant_decomposition(
        cand_completed=[True, True, False, False],
        cand_scored=[10.0, 12.0, 30.0, 20.0],
        base_completed=[True, False, True, False],
        base_scored=[12.0, 20.0, 16.0, 20.0],
        references=[10.0, 10.0, 15.0, 10.0],
    )
    assert dec["counts"] == {
        "both_completed": 1,
        "cand_only_completed": 1,
        "base_only_completed": 1,
        "both_penalized": 1,
    }
    assert dec["both_completed_total_gain"] == pytest.approx(2.0)
    assert dec["cand_only_completed_total_gain"] == pytest.approx(8.0)
    assert dec["base_only_completed_total_gain"] == pytest.approx(-14.0)
    assert dec["both_penalized_total_gain"] == pytest.approx(0.0)
    assert dec["base_minus_cand_total"] == pytest.approx(-4.0)
    assert dec["identity_residual"] < 1e-12


def test_strict_completed_before_deadline_rejects_exhausted_and_uncensored_overrun() -> None:
    assert is_strict_completed_before_deadline({
        "status": "ok", "valid": True, "tour_length": 15.0,
        "budget_exhausted": False, "solve_ms": 24.5, "budget_ms": 25.0,
    }) is True
    # Exhausted truncation (M3 25ms trap)
    assert is_strict_completed_before_deadline({
        "status": "ok", "valid": True, "tour_length": 15.0,
        "budget_exhausted": True, "solve_ms": 25.1, "budget_ms": 25.0,
    }) is False
    # Uncensored overrun (EoH-S/ReEvo 502ms trap)
    assert is_strict_completed_before_deadline({
        "status": "ok", "valid": True, "tour_length": 15.0,
        "budget_exhausted": False, "solve_censored": False, "solve_ms": 502.0, "budget_ms": 500.0,
    }) is False


def test_reevaluate_baselines_row_modes() -> None:
    cens_row = {
        "instance_id": "X-n101-k25",
        "size": 100,
        "reference_objective": 27591.0,
        "tour_length": 27600.0,
        "objective": 27600.0,
        "valid": True,
        "exact_vehicle_count": True,
        "status": "ok",
        "solve_ms": 503.0,
        "deadline_overrun_ms": 3.0,
        "solve_censored": True,
        "feasible_before_deadline": True,
        "returned_before_deadline": False,
        "algorithm_id": "PyVRP",
        "lane": "free_fleet",
    }
    anytime = reevaluate_baselines_row(cens_row, budget_ms=500.0, mode="anytime_feasible_before_deadline")
    strict = reevaluate_baselines_row(cens_row, budget_ms=500.0, mode="strict_returned_before_deadline")
    assert anytime["completed"] is True and anytime["scored_objective"] == 27600.0
    assert strict["completed"] is False and strict["scored_objective"] == 2.0 * 27591.0

    uncens_row = {**cens_row, "solve_censored": False, "feasible_before_deadline": False, "algorithm_id": "EoH-S"}
    clean_uncens = reevaluate_baselines_row(uncens_row, budget_ms=500.0, mode="anytime_feasible_before_deadline")
    assert clean_uncens["completed"] is False
    assert clean_uncens["uncensored_deadline_overrun"] is True
    assert clean_uncens["scored_objective"] == 2.0 * 27591.0


def test_blind_leakage_guard_rejects_raw_keys_and_allows_aggregates() -> None:
    assert_no_blind_leakage({"summary": {"by_depot_style": {"central": 10.0}, "demand_dist": "uniform"}})
    with pytest.raises(ValueError, match="forbidden_blind_key_detected"):
        assert_no_blind_leakage({"nested": [{"coordinates": [[0.1, 0.2]]}]})
    with pytest.raises(ValueError, match="forbidden_blind_key_detected"):
        assert_no_blind_leakage({"sealed_seed_token": "abc"})
