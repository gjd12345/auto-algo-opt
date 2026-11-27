"""Regression tests for the Wave 2 probes, anytime template, and stopping rules."""

from __future__ import annotations

import json
import math
from dataclasses import replace
from pathlib import Path
from statistics import mean, pstdev
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from agent_skill_loop.cvrp_workbench.protocol import normalize_routes
from agent_skill_loop.interface_design import runtime, templates
from agent_skill_loop.interface_design.multiscale import (
    ONLINE_C2_JOINT_PROBES,
    PROBE_DOMAIN_C2,
    evaluate_c2_joint_screen,
    generate_c2_joint_probe,
)
from agent_skill_loop.milestone_checkpoint import (
    claim_latest_pending_attempt_token,
    settle_pending_provenance_for_terminal_requests,
)
from agent_skill_loop.request_budget import PersistentRequestBudget
from research_agent.contracts import AgentConfig
from research_agent.loop import _read_stopping_provenance, evaluate_global_stopping_decision
from tools import run_m6_wave2_c2_b1 as runner


def test_c2_probe_geometry_fleet_and_demand_cv() -> None:
    assert PROBE_DOMAIN_C2 == "m6c2/cvrp/geometry-scale-joint/v1"
    assert len(ONLINE_C2_JOINT_PROBES) == 4
    profiles = {
        ("cv0", "sparse_k_over_20", "center", "uniform"): (0.0, 80, 20, [500, 500]),
        ("cv1_5", "dense_k_over_5", "corner", "clustered"): (1.5, 20, 5, [50, 50]),
    }
    seen = set()
    for spec in ONLINE_C2_JOINT_PROBES:
        size = spec["size"]
        profile = tuple(spec[key] for key in ("demand_cv_mode", "fleet_density_mode", "depot_mode", "spatial_mode"))
        seen.add((size, profile))
        cv, capacity, fleet_divisor, depot = profiles[profile]
        probe = generate_c2_joint_probe(**spec)
        assert probe == generate_c2_joint_probe(**spec)
        replica = generate_c2_joint_probe(**{**spec, "replicate": spec.get("replicate", 0) + 1})
        assert replica["instance_id"] != probe["instance_id"]
        assert replica["customer_coordinates"] != probe["customer_coordinates"]
        assert len(probe["customer_coordinates"]) == len(probe["demands"]) == size
        assert mean(probe["demands"]) == 4
        assert pstdev(probe["demands"]) / 4 == pytest.approx(cv)
        assert set(probe["demands"]) == ({4} if cv == 0 else {1, 16})
        assert probe["depot"] == depot
        assert probe["capacity"] == capacity
        assert probe["k_vehicles"] == size // fleet_divisor
        assert sum(probe["demands"]) == probe["k_vehicles"] * capacity
    assert seen == {(size, profile) for size in (100, 200) for profile in profiles}
    with pytest.raises(ValueError):
        generate_c2_joint_probe(**{**ONLINE_C2_JOINT_PROBES[0], "size": 110})


def test_c2_screen_rejects_absolute_ratio_and_deadline_failures() -> None:
    rows = [
        {**spec, "solve_ms": 5.0 if spec["size"] == 100 else 40.0, "returned_before_deadline": True}
        for spec in ONLINE_C2_JOINT_PROBES
    ]
    result = evaluate_c2_joint_screen(rows, max_solve_ms=40.0, max_ratio_200_100=8.0)
    assert result["passed"] is True
    assert result["max_observed_solve_ms"] == 40.0
    assert len(result["pairs"]) == 2
    assert evaluate_c2_joint_screen(rows, max_solve_ms=39.99)["passed"] is False
    assert evaluate_c2_joint_screen(rows, max_solve_ms=500.0, max_ratio_200_100=7.99)["passed"] is False
    missing_flag = [dict(row) for row in rows]
    missing_flag[0].pop("returned_before_deadline")
    assert evaluate_c2_joint_screen(missing_flag, max_solve_ms=500.0)["passed"] is False
    rows[0]["returned_before_deadline"] = False
    assert evaluate_c2_joint_screen(rows, max_solve_ms=500.0)["passed"] is False


class _ClockedDistances:
    """Switch the fake clock without depending on machine speed or poll count."""

    def __init__(self, tick_after_reads: int) -> None:
        self.tick_after_reads = tick_after_reads
        self.reads = 0

    def perf_counter(self) -> float:
        return 0.493 if self.reads >= self.tick_after_reads else 0.0

    def __getitem__(self, key: tuple[int, int]) -> float:
        self.reads += 1
        return float(key[0] != key[1])


def test_guarded_relocate_discards_partially_scanned_move(monkeypatch: pytest.MonkeyPatch) -> None:
    # In this unit matrix relocating any singleton into another route improves cost.
    # A deadline during the first destination scan must leave the routes intact.
    matrix = _ClockedDistances(20)
    monkeypatch.setattr(templates, "time", matrix)
    initial = [[node] for node in range(1, 21)]
    demands = np.asarray([0.0, *([1.0] * 20)])
    routes, meta = templates.apply_relocate_2opt_guarded(
        initial, matrix, demands, 2.0, budget_ms=500.0, deadline=0.5,
    )
    assert routes == normalize_routes(initial)
    assert meta["relocate_moves"] == 0
    assert meta["stop_reason"] == "anytime_safety_margin_exit"
    assert meta["voluntary_anytime_return"] is True
    assert meta["local_search_truncated"] is True
    assert meta["budget_exhausted"] is False
    assert meta["return_margin_ms"] == pytest.approx(7.0)


def test_guarded_two_opt_polls_inside_long_inner_scan(monkeypatch: pytest.MonkeyPatch) -> None:
    matrix = _ClockedDistances(20)
    monkeypatch.setattr(templates, "time", matrix)
    customers = list(range(1, 130))
    route, moves, _, stop_reason = templates._two_opt_single_route_guarded(
        customers, matrix, effective_deadline=0.4925,
    )
    assert route == customers
    assert moves == 0
    assert stop_reason == "anytime_safety_margin_exit"
    assert 20 <= matrix.reads < 3 * (len(customers) - 1)


def test_v1_source_hash_and_registered_v2_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    template_id = "cvrp_parallel_merge_static"
    v1 = templates.get_template_spec(template_id, "v1")
    v2 = templates.get_template_spec(template_id, "v2")
    assert v1.template_source_sha256 == "3bca783d3de8eaf5ec4fe559c71f92ccd98afc89d1e69adeb56a85a2d18e53ac"
    assert v1.runner is templates.run_cvrp_parallel_merge_static_v1
    assert v2.runner is templates.run_cvrp_parallel_merge_static_v2
    assert v2.template_source_sha256 != v1.template_source_sha256

    clock = 0.0
    fake_time = SimpleNamespace(perf_counter=lambda: clock)
    monkeypatch.setattr(templates, "time", fake_time)
    monkeypatch.setattr(runtime, "time", fake_time)

    def cw_score(
        distance_matrix: np.ndarray, _demands: np.ndarray, _capacity: float,
        i_idx: np.ndarray, j_idx: np.ndarray,
    ) -> np.ndarray:
        nonlocal clock
        clock = 0.493
        return distance_matrix[0, i_idx] + distance_matrix[0, j_idx] - distance_matrix[i_idx, j_idx]

    record = runtime.evaluate_hook_on_instance_inprocess(
        template_id=template_id, template_version="v2", hook_fn=cw_score,
        instance=generate_c2_joint_probe(**ONLINE_C2_JOINT_PROBES[0]),
        postprocess_mode="relocate_2opt", time_budget_ms=500.0, capture_timed_incumbents=True,
    )
    assert record["valid"] is True
    assert record["completed"] is True
    assert record["stop_reason"] == "anytime_safety_margin_exit"
    assert record["voluntary_anytime_return"] is True
    assert record["budget_exhausted"] is False
    assert record["returned_before_deadline"] is True
    assert record["returned_before_deadline_exact_k"] is False
    assert record["template_source_sha256"] == v2.template_source_sha256


def _candidate(ordinal: int, objective: float | None, *, completion: float = 1.0,
               feasible: bool = True, status: str = "valid_candidate") -> dict[str, Any]:
    return {
        "global_ordinal": ordinal,
        "purpose": "baseline_seed" if ordinal == 0 else "eoh_generation",
        "generation_status": status,
        "eligible": int(status in {"valid_candidate", "baseline_seed"}),
        "dev_all_feasible": int(feasible),
        "dev_completion_rate": completion,
        "dev_penalized_mean": objective,
    }


def test_risk_stop_posterior_uses_recent_settled_attempts_and_last_three_gains(tmp_path: Path) -> None:
    config = AgentConfig(
        run_id="risk", output_dir=str(tmp_path), total_request_cap=100,
        global_early_stop_mode="risk_bounded_beta_geom", risk_stop_window=4,
    )
    evidence = [
        _candidate(0, 1000.0, status="baseline_seed"),
        _candidate(1, 500.0),
        _candidate(2, 495.0),
        _candidate(3, 475.2),
        _candidate(87, None, status="provider_failed"),
        _candidate(88, 470.448),
        _candidate(89, 1.0, completion=0.99),
        _candidate(90, None, status="invalid_candidate"),
        _candidate(91, None, status="pending"),
        _candidate(93, 1.0),
    ]
    decision = evaluate_global_stopping_decision(config, t=92, candidate_provenance=list(reversed(evidence)))
    a, b = config.risk_stop_prior_a + 2, config.risk_stop_prior_b + 2
    expected_q = 1.0 - math.prod((b + j) / (a + b + j) for j in range(8))
    assert decision["top_tier"] is True
    assert (decision["a_t"], decision["b_t"]) == (a, b)
    assert decision["excluded_non_candidate_attempts"] == 1
    assert decision["q_t"] == pytest.approx(expected_q)
    assert decision["last_3_jump_rel_gains"] == pytest.approx([0.01, 0.04, 0.01])
    assert decision["D_t"] == pytest.approx(0.04)
    assert decision["expected_regret_bound"] == pytest.approx(expected_q * 0.04)
    assert decision["stop"] is False


def test_risk_stop_does_not_stop_after_provider_outage(tmp_path: Path) -> None:
    config = AgentConfig(
        run_id="risk_outage_20261124", output_dir=str(tmp_path), total_request_cap=100,
        global_early_stop_mode="risk_bounded_beta_geom",
    )
    evidence = [_candidate(0, 100.0, status="baseline_seed")]
    evidence.extend(
        _candidate(ordinal, None, status="provider_failed" if ordinal % 2 else "eoh_skipped")
        for ordinal in range(62, 94)
    )
    for policy in (config, replace(config, risk_stop_eps=0.01)):
        decision = evaluate_global_stopping_decision(policy, t=93, candidate_provenance=evidence)
        assert decision["window_attempts"] == 0
        assert decision["excluded_non_candidate_attempts"] == 32
        assert decision["stop"] is False


def test_global_stop_requires_eligible_incumbent_and_recovery_clearance(tmp_path: Path) -> None:
    config = AgentConfig(
        run_id="gates", output_dir=str(tmp_path), total_request_cap=100,
        global_early_stop_mode="risk_bounded_beta_geom",
    )
    evidence = [_candidate(0, 100.0, status="baseline_seed")]
    evidence.extend(_candidate(i, 100.0) for i in range(1, 33))

    def decide(**kwargs: Any) -> dict[str, Any]:
        return evaluate_global_stopping_decision(config, t=98, candidate_provenance=evidence, **kwargs)

    decision = decide()
    assert decision["stop"] is True
    assert decision["D_t"] == 0.015
    for veto in ({"pending_restart": True}, {"restart_eligible_round_id": 2}, {"last_restart_ordinal": 81}):
        vetoed = decide(**veto)
        assert vetoed["P_t"] == 1
        assert vetoed["stop"] is False
    assert decide(last_restart_ordinal=80)["stop"] is True
    for gates in ({"risk_stop_min_requests": 99}, {"risk_stop_alpha": 0.001}):
        stricter = evaluate_global_stopping_decision(
            replace(config, **gates), t=98, candidate_provenance=evidence,
        )
        assert stricter["stop"] is False

    evidence[:] = [dict(row, dev_completion_rate=0.99) for row in evidence]
    partial = decide()
    assert partial["top_tier"] is False
    assert partial["stop"] is False


def test_naive_patience_and_legacy_off_defaults(tmp_path: Path) -> None:
    legacy = AgentConfig.from_dict({"run_id": "defaults", "output_dir": str(tmp_path)})
    assert legacy.global_early_stop_mode == "off"
    assert legacy.template_version == "v1"
    assert legacy.enable_c2_joint_screen is False
    config = replace(legacy, global_early_stop_mode="naive_patience", global_early_stop_patience=2)
    evidence = [
        _candidate(0, 100.0, status="baseline_seed"),
        _candidate(16, 99.0),
        _candidate(17, 99.0),
        _candidate(18, None, status="provider_failed"),
        _candidate(19, None, status="invalid_candidate"),
    ]
    before = evaluate_global_stopping_decision(config, t=18, candidate_provenance=evidence)
    after = evaluate_global_stopping_decision(config, t=19, candidate_provenance=evidence)
    assert before["non_improving_attempts"] == 1
    assert before["stop"] is False
    assert after["non_improving_attempts"] == 2
    assert after["stop"] is True
    assert evaluate_global_stopping_decision(legacy, t=19, candidate_provenance=evidence)["stop"] is False


def test_joined_candidate_timeout_settles_without_strict_barriers(tmp_path: Path) -> None:
    budget = PersistentRequestBudget(
        tmp_path / "requests.sqlite3", 4, record_candidate_provenance=True, owner_epoch="worker-1",
    )
    slot = budget.reserve(purpose="eoh_generation", problem="cvrp")
    assert slot is not None
    budget.mark_sent(slot)
    budget.finish(slot, "complete", status=200)
    assert claim_latest_pending_attempt_token(budget.ledger_path, budget.run_id, eval_id="timed_out") == slot.attempt_token
    assert settle_pending_provenance_for_terminal_requests(budget.ledger_path, budget.run_id) == 0
    assert settle_pending_provenance_for_terminal_requests(
        budget.ledger_path, budget.run_id, finished_eval_owner_epoch="other-worker",
    ) == 0
    assert settle_pending_provenance_for_terminal_requests(
        budget.ledger_path, budget.run_id, finished_eval_owner_epoch="worker-1",
    ) == 1
    assert _read_stopping_provenance(budget, budget.used)[0]["generation_status"] == "invalid_candidate"


def test_b1_mock_early_stops_and_preserves_champions(tmp_path: Path) -> None:
    report = runner.run_b1_mock(tmp_path)
    assert report["passed"] is True
    arms = report["arms"]
    assert set(arms) == {
        "no_early_stop", "naive_patience_24", "stagnation_restart_only", "risk_bounded_adaptive_stop",
    }
    cap = report["total_request_cap"]
    mock_dir = tmp_path / "b1_mock"
    decisions = [
        json.loads(line) for line in (mock_dir / "stopping_decisions.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    modes = {
        "naive_patience_24": "naive_patience",
        "risk_bounded_adaptive_stop": "risk_bounded_beta_geom",
    }
    for arm, result in arms.items():
        spend = result["realized_request_spend"]
        champion = mock_dir / arm / result["best_solver_manifest_ref"]
        assert json.loads(champion.read_text(encoding="utf-8"))["template_version"] == "v2"
        if arm in modes:
            assert 0 < spend < cap
            assert result["phase"] == "early_stopped_global"
            assert result["stop_reason"] == f"global_early_stop_{modes[arm]}"
            triggered = [row for row in decisions if row["arm"] == arm and row["stop"]]
            assert len(triggered) == 1
            assert triggered[0]["t"] == spend
        else:
            assert spend == cap
            assert result["stop_reason"] == "request_budget_exhausted"


def test_b1_mux_contains_one_v2_job_per_arm_and_seed(tmp_path: Path) -> None:
    manifest = runner.build_mux_manifest(tmp_path)
    assert manifest["model"] == "DeepSeek-V4.1-Flash"
    assert manifest["request_cap"] == 100
    assert manifest["template_version"] == "v2"
    panes = manifest["panes"]
    assert len(panes) == len({pane["id"] for pane in panes}) == 12
    cells = set()
    for pane in panes:
        args = pane["command"]
        arm = args[args.index("--arm") + 1]
        seed = int(args[args.index("--seed") + 1])
        assert args[args.index("--stage") + 1] == "b1_cell"
        cells.add((arm, seed))
    assert cells == {
        (arm, seed)
        for arm in ("no_early_stop", "naive_patience_24", "stagnation_restart_only", "risk_bounded_adaptive_stop")
        for seed in (20261124, 20261125, 20261126)
    }


def test_b1_pareto_retains_completion_tradeoff() -> None:
    points = [
        {"requests_used": 25, "blind_120_quality": 4.0, "strict_completed_before_deadline": 119},
        {"requests_used": 26, "blind_120_quality": 4.1, "strict_completed_before_deadline": 119},
        {"requests_used": 28, "blind_120_quality": 5.0, "strict_completed_before_deadline": 120},
        {"requests_used": 100, "blind_120_quality": 3.0, "strict_completed_before_deadline": 120},
    ]
    assert runner.pareto_frontier(points) == [points[0], points[2], points[3]]


def test_b1_mux_includes_resume_and_cell_cli_flags(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    build_out = tmp_path / "out"
    manifest = runner.build_mux_manifest(build_out)
    assert all("--resume" in pane["command"] for pane in manifest["panes"])

    recorded: list[tuple[bool, Any]] = []
    monkeypatch.setattr(runner, "_output_path", lambda path: build_out)
    monkeypatch.setattr(runner, "load_local_env", lambda: None)
    monkeypatch.setattr(runner, "_seed_common_start", lambda *a, **k: {"seed": 20261124})

    def fake_run(config: AgentConfig, *, resume: bool = False, common_start: Any = None) -> dict[str, Any]:
        recorded.append((resume, common_start))
        phase = "no_champion" if len(recorded) > 1 else "completed"
        return {"run_id": config.run_id, "final_phase": phase, "realized_request_spend": 1}

    monkeypatch.setattr(runner, "run_research_agent", fake_run)
    rc_ok = runner.main([
        "--stage", "b1_cell", "--output-dir", str(build_out),
        "--arm", "no_early_stop", "--seed", "20261124", "--endpoint", "https://example.invalid/v1", "--resume",
    ])
    rc_no_champ = runner.main([
        "--stage", "b1_cell", "--output-dir", str(build_out),
        "--arm", "no_early_stop", "--seed", "20261124", "--endpoint", "https://example.invalid/v1",
    ])
    assert rc_ok == 0
    assert rc_no_champ == 2
    assert recorded == [(True, {"seed": 20261124}), (False, {"seed": 20261124})]


def test_reconcile_orphaned_inflight_unblocks_checkpoint_sealing(tmp_path: Path) -> None:
    from agent_skill_loop.milestone_checkpoint import (
        initialize_milestone_schedule,
        try_seal_draining_checkpoints,
    )

    budget = PersistentRequestBudget(
        tmp_path / "requests.sqlite3",
        3,
        run_id="orphan_test",
        checkpoint_budgets=(2,),
        strict_checkpoint_barriers=True,
        record_candidate_provenance=True,
        owner_epoch="worker-old",
    )
    initialize_milestone_schedule(
        budget.ledger_path,
        run_id="orphan_test",
        checkpoint_budgets=(2,),
        baseline_solver={"hook_code_sha256": "base", "template_id": "t"},
        baseline_dev_eval={"all_feasible": True, "completion_rate": 1.0, "penalized_mean_tour_length": 10.0},
        dev_suite_hash="dev_h",
        solve_budget_ms=500.0,
    )
    slot1 = budget.reserve(purpose="eoh_generation", problem="cvrp")
    assert slot1 is not None
    budget.mark_sent(slot1)
    slot2 = budget.reserve(purpose="eoh_generation", problem="cvrp")
    assert slot2 is not None
    budget.mark_sent(slot2)
    budget.finish(slot2, "complete", status=200)
    assert claim_latest_pending_attempt_token(budget.ledger_path, "orphan_test", eval_id="ev2") == slot2.attempt_token

    resumed_budget = PersistentRequestBudget(
        tmp_path / "requests.sqlite3",
        3,
        run_id="orphan_test",
        checkpoint_budgets=(2,),
        strict_checkpoint_barriers=True,
        record_candidate_provenance=True,
        owner_epoch="worker-new",
        reconcile_inflight=False,
    )
    resumed_budget.check_checkpoints(0, 2)
    assert try_seal_draining_checkpoints(resumed_budget.ledger_path, "orphan_test") == []
    assert resumed_budget.reconcile_orphaned_inflight() >= 2
    settle_pending_provenance_for_terminal_requests(resumed_budget.ledger_path, "orphan_test")
    assert try_seal_draining_checkpoints(resumed_budget.ledger_path, "orphan_test") == [2]


def test_read_champion_accepts_completed_below_cap_and_avoids_wal_sidecar(tmp_path: Path) -> None:
    import sqlite3
    from contextlib import closing
    from agent_skill_loop.interface_design.planner import build_interface_design

    live_dir = tmp_path / "b1_live"
    arm, seed = "no_early_stop", 20261124
    run_id = runner._run_id(arm, seed)
    cfg = runner._arm_config(live_dir, arm, seed, mode="live", endpoint="https://example.invalid/v1", api_key_env="PARATERA_API_KEY")
    run_dir = Path(cfg.output_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "agent_config.json").write_text(json.dumps(cfg.to_dict()), encoding="utf-8")

    solver = runner._build_initial_baseline_solver(cfg).to_dict()
    (run_dir / "best.json").write_text(json.dumps(solver), encoding="utf-8")
    (run_dir / "research_summary.json").write_text(json.dumps({
        "run_id": run_id,
        "final_phase": "completed",
        "realized_request_spend": 1,
        "best_solver_manifest_ref": "best.json",
    }), encoding="utf-8")
    budget = PersistentRequestBudget(run_dir / "agent_budget.sqlite3", 100, run_id=run_id, record_candidate_provenance=True)
    slot = budget.reserve(purpose="eoh_generation", problem="cvrp")
    assert slot is not None
    budget.mark_sent(slot)
    budget.finish(slot, "complete", status=200)
    runner.settle_attempt_provenance(
        budget.ledger_path,
        attempt_token=slot.attempt_token,
        generation_status="valid_candidate",
        code_sha256=solver["hook_code_sha256"],
        solver_manifest=solver,
        validation_passed=True,
        dev_eval={"all_feasible": True, "completion_rate": 1.0, "penalized_mean_tour_length": 5.0},
    )
    with closing(sqlite3.connect(budget.ledger_path)) as con:
        con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    for suffix in ("-wal", "-shm"):
        sidecar = run_dir / f"agent_budget.sqlite3{suffix}"
        if sidecar.exists():
            sidecar.unlink()

    loaded, meta = runner._read_champion(live_dir, arm, seed)
    assert loaded.hook_code_sha256 == solver["hook_code_sha256"]
    assert meta["phase"] == "completed"
    assert meta["requests_used"] == 1
    assert (run_dir / "agent_budget.sqlite3").is_file()


def test_b1_cell_lock_rejects_duplicate_launch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from agent_skill_loop.file_lock import exclusive_file_lock

    build_out = tmp_path / "out"
    monkeypatch.setattr(runner, "_output_path", lambda path: build_out)
    monkeypatch.setattr(runner, "load_local_env", lambda: None)
    run_dir = build_out / "b1_live" / runner._run_id("no_early_stop", 20261124)
    with exclusive_file_lock(run_dir / ".cell.lock", busy="held"):
        with pytest.raises(ValueError, match="b1_cell_busy:m6_b1_no_early_stop_s20261124"):
            runner.main([
                "--stage", "b1_cell", "--output-dir", str(build_out),
                "--arm", "no_early_stop", "--seed", "20261124", "--endpoint", "https://example.invalid/v1",
            ])


def test_validator_gate5_rejects_budget_exhausted_incumbent_for_v2() -> None:
    from agent_skill_loop.interface_design.planner import build_interface_design
    from agent_skill_loop.interface_design.validator import InterfaceValidator

    g3_inst = {"instance_id": "g3_0", "depot": [0, 0], "customer_coordinates": [[1, 0]], "demands": [1], "capacity": 5}
    g5_n200 = [{"instance_id": f"g5_n200_{idx}", "depot": [0, 0], "customer_coordinates": [[1, 0]], "demands": [1], "capacity": 5} for idx in range(3)]
    g5_nom = {"instance_id": "g5_nom", "depot": [0, 0], "customer_coordinates": [[1, 0]], "demands": [1], "capacity": 5}
    g5_scl = {"instance_id": "g5_scl", "coord_scale": 1e-3, "depot": [0, 0], "customer_coordinates": [[1e-3, 0]], "demands": [1], "capacity": 5}

    class _FakeEval:
        def evaluate(self, **kwargs: Any) -> dict[str, Any]:
            insts = kwargs["instances"]
            if any(str(inst["instance_id"]).startswith("g5_") for inst in insts):
                return {
                    "valid": True,
                    "records": [
                        {
                            "instance_id": inst["instance_id"],
                            "outcome_class": "budget_exhausted_feasible_incumbent" if idx == 0 else "completed",
                            "stop_reason": "budget_exhausted" if idx == 0 else "completed",
                            "returned_before_deadline": idx != 0,
                            "solve_ms": 510.0 if idx == 0 else 10.0,
                            "tour_length": 100.0 if idx == 0 else (10.0 if inst["instance_id"] == "g5_nom" else 0.01),
                        }
                        for idx, inst in enumerate(insts)
                    ],
                }
            return {
                "valid": True,
                "records": [
                    {
                        "instance_id": inst["instance_id"],
                        "outcome_class": "completed",
                        "returned_before_deadline": True,
                        "solve_ms": 5.0,
                        "tour_length": 10.0,
                        "hook_call_count": 3,
                        "merge_sequence": [(1, 2)] if kwargs.get("capture_merge_sequence") else [],
                        "pre_postprocess_routes": [[1, 2]] if kwargs.get("capture_merge_sequence") else [],
                    }
                    for inst in insts
                ],
            }

    design_v2 = build_interface_design(runner.TEMPLATE_ID, "v2", postprocess_mode="relocate_2opt")
    v2_validator = InterfaceValidator(evaluator=_FakeEval(), instance_time_budget_ms=500.0)
    rep_v2 = v2_validator.validate(
        design_v2,
        gate3_instances=[g3_inst],
        gate5_n200_instances=g5_n200,
        gate5_scale_pair=(g5_nom, g5_scl),
        hook_code_override=design_v2.baseline_hook_code,
    )
    assert any(f.gate_id == 5 and f.error_code == "v2_strict_deadline_violation" for f in rep_v2.failures)

    design_v1 = build_interface_design(runner.TEMPLATE_ID, "v1", postprocess_mode="relocate_2opt")
    v1_validator = InterfaceValidator(evaluator=_FakeEval(), instance_time_budget_ms=500.0)
    rep_v1 = v1_validator.validate(
        design_v1,
        gate3_instances=[g3_inst],
        gate5_n200_instances=g5_n200,
        gate5_scale_pair=(g5_nom, g5_scl),
        hook_code_override=design_v1.baseline_hook_code,
    )
    assert not any(f.gate_id == 5 for f in rep_v1.failures)

    # Real production evaluator path omits returned_before_deadline and must pass Gate 5 for v2 baseline
    real_rep = InterfaceValidator(instance_time_budget_ms=500.0).validate(
        design_v2, hook_code_override=design_v2.baseline_hook_code,
    )
    assert real_rep.passed is True


def test_collision_free_rng_and_session_terminal_seed_shift(tmp_path: Path) -> None:
    import hashlib
    import sqlite3
    from contextlib import closing
    from research_agent.tools.session_tools import SessionRunnerTool

    def derive(base_seed: int, round_id: int) -> int:
        return int.from_bytes(hashlib.sha256(f"{base_seed}:{round_id}".encode("utf-8")).digest()[:4], "big")

    assert derive(20261124, 2) != derive(20261125, 1)

    cfg = AgentConfig(
        run_id="term_seed",
        output_dir=str(tmp_path),
        search_seed=20261124,
        mode="mock",
        use_benchmark_dev_suite=False,
        dev_instance_count=2,
        dev_instance_size=10,
        eoh_max_sample_nums=2,
    )
    budget = PersistentRequestBudget(tmp_path / "agent_budget.sqlite3", 10, run_id=cfg.run_id)
    tool = SessionRunnerTool(run_dir=tmp_path, config=cfg, budget=budget)
    first_state = tool.ensure_initialized()
    with closing(sqlite3.connect(tool.session_dir / "session.sqlite3")) as con:
        with con:
            con.execute("UPDATE runs SET state='FAILED', active_round_id=4")
            con.execute(
                "INSERT INTO tasks(task_id, run_id, round_id, state, terminal_reason, created_at_utc) "
                "VALUES ('t1', (SELECT run_id FROM runs LIMIT 1), 4, 'EXITED', 'PROVIDER_TERMINAL', '2026-11-26T00:00:00Z')"
            )
    # Pre-seed offset marker for first_state['run_id'] to verify crash-idempotent archive handling
    (tmp_path / "session_round_offset.json").write_text(
        json.dumps({"restarts": 1, "round_offset": 4, "archived_run_ids": [first_state["run_id"]]}),
        encoding="utf-8",
    )
    new_state = tool.ensure_initialized()
    assert new_state["round_id"] == 1
    frozen = json.loads((tool.session_dir / "config_frozen.json").read_text(encoding="utf-8"))
    assert frozen["search_seed"] != cfg.search_seed
    offset_doc = json.loads((tmp_path / "session_round_offset.json").read_text(encoding="utf-8"))
    assert offset_doc["restarts"] == 1
    assert offset_doc["round_offset"] == 4
