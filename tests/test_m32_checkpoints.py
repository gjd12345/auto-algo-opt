from __future__ import annotations

import hashlib
import json
import pickle
import sqlite3
from pathlib import Path

import pytest

from agent_skill_loop.interface_design.contracts import InterfaceDesign
from agent_skill_loop.interface_design.dynamic_eoh import DynamicInterfaceProblem, derive_effective_batch_timeout_s
from agent_skill_loop.interface_design.model_routing import (
    ModelRoutingPolicy,
    allocate_logical_route,
    compute_attempt_cost_usd,
    extract_provider_usage,
)
from agent_skill_loop.interface_design.planner import build_design_for_template
from agent_skill_loop.interface_design.templates import get_template_spec
from agent_skill_loop.milestone_checkpoint import (
    export_sealed_checkpoints,
    initialize_milestone_schedule,
    read_milestone_status,
    register_attempt_provenance,
    set_run_wall_offset_seconds,
    settle_attempt_provenance,
    try_seal_draining_checkpoints,
)
from agent_skill_loop.request_budget import PersistentRequestBudget
from research_agent.contracts import AgentConfig
from research_agent.loop import _build_initial_baseline_solver, run_research_agent


def _make_dummy_solver(cfg: AgentConfig, tag: str, *, extra_comment: str) -> dict:
    base = _build_initial_baseline_solver(cfg).to_dict()
    base["solver_id"] = tag
    base["hook_code"] = base["hook_code"] + f"\n# {extra_comment}\n"
    base["hook_code_sha256"] = hashlib.sha256(base["hook_code"].encode("utf-8")).hexdigest()
    return base


def test_settled_prefix_barrier_36_100_200_400(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.sqlite3"
    run_id = "barrier_test_run"
    cfg = AgentConfig(
        run_id=run_id,
        output_dir=str(tmp_path),
        initial_template_id="cvrp_parallel_merge_static",
        checkpoint_budgets=(36, 100, 200, 400),
        total_request_cap=400,
        strict_checkpoint_barriers=True,
    )
    budget = PersistentRequestBudget(
        ledger,
        max_requests=400,
        run_id=run_id,
        checkpoint_budgets=(36, 100, 200, 400),
        strict_checkpoint_barriers=True,
    )
    baseline_solver = _build_initial_baseline_solver(cfg).to_dict()
    initialize_milestone_schedule(
        ledger,
        run_id=run_id,
        checkpoint_budgets=(36, 100, 200, 400),
        baseline_solver=baseline_solver,
        baseline_dev_eval={"all_feasible": True, "completion_rate": 1.0, "penalized_mean_tour_length": 15.0, "valid_only_mean_tour_length": 15.0},
        dev_suite_hash="dummy_suite_hash",
        solve_budget_ms=500.0,
    )

    checkpoints = {36, 100, 200, 400}
    for idx in range(1, 401):
        slot = budget.reserve(purpose="eoh_generation", problem="cvrp", attempt=idx, model="deepseek-v4.1-flash")
        assert slot is not None
        assert slot.index == idx
        assert slot.attempt_token is not None
        register_attempt_provenance(
            ledger,
            attempt_token=slot.attempt_token,
            run_id=run_id,
            logical_call_id=f"lc_{idx}",
            physical_request_id=slot.request_id,
            global_ordinal=idx,
            purpose="eoh_generation",
        )
        # While request idx == B is still in flight / unsettled, request B+1 MUST be blocked
        if idx in {36, 100, 200}:
            blocked = budget.reserve(purpose="eoh_generation", problem="cvrp", attempt=idx + 1, model="deepseek-v4.1-flash")
            assert blocked is None
            assert budget.denial_reason == "checkpoint_pending"

        budget.mark_sent(slot)
        budget.finish(
            slot,
            "complete",
            status=200,
            elapsed_seconds=0.05,
            input_tokens=100,
            output_tokens=50,
            cached_tokens=0,
        )
        obj = 15.0 - 0.01 * idx if idx in {36, 100, 200, 400} else 14.9
        settle_attempt_provenance(
            ledger,
            attempt_token=slot.attempt_token,
            generation_status="valid_candidate",
            eval_id=f"ev_{idx}",
            code_sha256=f"sha_{idx}",
            solver_manifest=_make_dummy_solver(cfg, f"solver_{idx}", extra_comment=f"cand {idx}"),
            validation_passed=True,
            dev_eval={"all_feasible": True, "completion_rate": 1.0, "penalized_mean_tour_length": obj, "valid_only_mean_tour_length": obj},
            dev_suite_hash="dummy_suite_hash",
            solve_budget_ms=500.0,
        )
        sealed = try_seal_draining_checkpoints(ledger, run_id, wall_elapsed_seconds=float(idx) * 0.1)
        if idx in checkpoints:
            assert sealed == [idx]
        else:
            assert sealed == []

    exported = export_sealed_checkpoints(ledger, run_id, tmp_path / "checkpoints")
    assert set(exported) == {"36", "100", "200", "400"}
    for b in (36, 100, 200, 400):
        data = json.loads(Path(exported[str(b)]).read_text(encoding="utf-8"))
        assert data["checkpoint_budget"] == b
        assert data["settled_through_ordinal"] == b
        assert data["winner_source_ordinal"] == b
        assert data["usage_cutoff"]["attempted_requests"] == b
        assert data["usage_cutoff"]["cached_tokens"] == 0


def test_crash_recovery_398_399_fail_400_winner_resume_zero_extra_requests(tmp_path: Path) -> None:
    run_dir = tmp_path / "crash_resume_400"
    cfg = AgentConfig(
        run_id="resume_400_run",
        output_dir=str(run_dir),
        problem_family="cvrp",
        max_rounds=2,
        total_request_cap=400,
        checkpoint_budgets=(400,),
        strict_checkpoint_barriers=True,
        initial_template_id="cvrp_parallel_merge_static",
        allowed_templates=("cvrp_parallel_merge_static",),
        allowed_postprocess_modes=("none",),
        mode="mock",
    )
    ledger = run_dir / "agent_budget.sqlite3"
    run_dir.mkdir(parents=True, exist_ok=True)
    budget = PersistentRequestBudget(
        ledger,
        max_requests=400,
        run_id=cfg.run_id,
        checkpoint_budgets=(400,),
        strict_checkpoint_barriers=True,
    )
    baseline_solver = _build_initial_baseline_solver(cfg).to_dict()
    initialize_milestone_schedule(
        ledger,
        run_id=cfg.run_id,
        checkpoint_budgets=(400,),
        baseline_solver=baseline_solver,
        baseline_dev_eval={"all_feasible": True, "completion_rate": 1.0, "penalized_mean_tour_length": 12.0, "valid_only_mean_tour_length": 12.0},
        dev_suite_hash="synth_hash",
        solve_budget_ms=500.0,
    )
    for idx in range(1, 399):
        slot = budget.reserve(purpose="eoh_generation", problem="cvrp", attempt=idx, model="deepseek-v4.1-flash")
        assert slot is not None and slot.attempt_token is not None
        register_attempt_provenance(
            ledger,
            attempt_token=slot.attempt_token,
            run_id=cfg.run_id,
            logical_call_id=f"lc_{idx}",
            physical_request_id=slot.request_id,
            global_ordinal=idx,
            purpose="eoh_generation",
        )
        budget.mark_sent(slot)
        budget.finish(slot, "complete", status=200, elapsed_seconds=0.01, input_tokens=10, output_tokens=5)
        settle_attempt_provenance(
            ledger,
            attempt_token=slot.attempt_token,
            generation_status="valid_candidate",
            eval_id=f"ev_{idx}",
            code_sha256=f"sha_{idx}",
            solver_manifest=_make_dummy_solver(cfg, f"cand_{idx}", extra_comment=f"c{idx}"),
            validation_passed=True,
            dev_eval={"all_feasible": True, "completion_rate": 1.0, "penalized_mean_tour_length": 10.5, "valid_only_mean_tour_length": 10.5},
            dev_suite_hash="synth_hash",
            solve_budget_ms=500.0,
        )

    # Request 399 fails
    s399 = budget.reserve(purpose="eoh_generation", problem="cvrp", attempt=399, model="deepseek-v4.1-flash")
    assert s399 is not None and s399.attempt_token is not None
    register_attempt_provenance(
        ledger,
        attempt_token=s399.attempt_token,
        run_id=cfg.run_id,
        logical_call_id="lc_399",
        physical_request_id=s399.request_id,
        global_ordinal=399,
        purpose="eoh_generation",
    )
    budget.mark_sent(s399)
    budget.finish(s399, "http_error", status=502, error_code="http_502", elapsed_seconds=0.02)
    settle_attempt_provenance(ledger, attempt_token=s399.attempt_token, generation_status="provider_failed")

    # Request 400 wins and commits dev eval in SQLite BEFORE JSON export (simulate interrupt here)
    s400 = budget.reserve(purpose="eoh_generation", problem="cvrp", attempt=400, model="deepseek-v4.1-flash")
    assert s400 is not None and s400.attempt_token is not None
    register_attempt_provenance(
        ledger,
        attempt_token=s400.attempt_token,
        run_id=cfg.run_id,
        logical_call_id="lc_400",
        physical_request_id=s400.request_id,
        global_ordinal=400,
        purpose="eoh_generation",
    )
    budget.mark_sent(s400)
    budget.finish(s400, "complete", status=200, elapsed_seconds=0.03, input_tokens=20, output_tokens=10, cached_tokens=0)
    settle_attempt_provenance(
        ledger,
        attempt_token=s400.attempt_token,
        generation_status="valid_candidate",
        eval_id="ev_400",
        code_sha256="sha_400",
        solver_manifest=_make_dummy_solver(cfg, "winner_400", extra_comment="win400"),
        validation_passed=True,
        dev_eval={"all_feasible": True, "completion_rate": 1.0, "penalized_mean_tour_length": 9.1, "valid_only_mean_tour_length": 9.1},
        dev_suite_hash="synth_hash",
        solve_budget_ms=500.0,
    )
    assert not (run_dir / "checkpoints" / "frozen_checkpoint_400.json").exists()

    # Reopen and resume via run_research_agent -> must seal & export 400 cleanly with 0 extra requests
    summary = run_research_agent(cfg, resume=True)
    reopened_budget = PersistentRequestBudget(ledger, max_requests=400, run_id=cfg.run_id, reconcile_inflight=False)
    assert len(reopened_budget.request_records()) == 400
    assert "400" in summary["frozen_checkpoints"]

    ckpt_file = run_dir / "checkpoints" / "frozen_checkpoint_400.json"
    assert ckpt_file.is_file()
    raw1 = ckpt_file.read_bytes()
    ckpt_payload = json.loads(raw1.decode("utf-8"))
    assert ckpt_payload["winner_source_ordinal"] == 400
    assert ckpt_payload["best_dev_objective"] == 9.1
    assert ckpt_payload["usage_cutoff"]["attempted_requests"] == 400

    # Re-exporting must be strictly byte-identical
    export_sealed_checkpoints(ledger, cfg.run_id, run_dir / "checkpoints")
    assert ckpt_file.read_bytes() == raw1

    mstatus = read_milestone_status(ledger, cfg.run_id)
    assert mstatus["attempted_requests"] == 400
    assert len(mstatus["checkpoints"]) == 1
    assert mstatus["checkpoints"][0]["state"] == "sealed"


def test_1_in_4_routing_and_retry_preservation_end_to_end(tmp_path: Path) -> None:
    ledger = tmp_path / "route.sqlite3"
    policy = ModelRoutingPolicy(
        enabled=True,
        weak_model="deepseek-v4.1-flash",
        strong_model="deepseek-v4-pro",
        strong_every_n=4,
    )
    selected = []
    for k in range(1, 9):
        route = allocate_logical_route(
            ledger,
            run_id="route_run",
            purpose="eoh_generation",
            policy=policy,
            created_at_utc="2026-11-23T00:00:00Z",
        )
        assert route["logical_ordinal"] == k
        selected.append((k, route["requested_model"], route["route_role"]))
        if k == 4:
            retry_route = allocate_logical_route(
                ledger,
                run_id="route_run",
                purpose="eoh_generation",
                policy=policy,
                created_at_utc="2026-11-23T00:00:01Z",
                existing_logical_call_id=route["logical_call_id"],
            )
            assert retry_route == route

    assert [(k, r) for k, _, r in selected] == [
        (1, "weak"), (2, "weak"), (3, "weak"), (4, "strong"),
        (5, "weak"), (6, "weak"), (7, "weak"), (8, "strong"),
    ]
    assert selected[3][1] == "deepseek-v4-pro"
    assert selected[7][1] == "deepseek-v4-pro"

    # Full mock agent run using strict barriers + 1-in-4 routing
    out_dir = tmp_path / "routed_agent"
    cfg = AgentConfig(
        run_id="routed_agent_run",
        output_dir=str(out_dir),
        problem_family="cvrp",
        max_rounds=2,
        total_request_cap=24,
        eoh_pop_size=2,
        eoh_n_pop=2,
        eoh_max_sample_nums=6,
        allowed_templates=("cvrp_parallel_merge_static",),
        allowed_postprocess_modes=("none",),
        initial_template_id="cvrp_parallel_merge_static",
        initial_postprocess_mode="none",
        checkpoint_budgets=(12,),
        strict_checkpoint_barriers=True,
        model_routing_policy=policy.to_dict(),
        mode="mock",
    )
    summary = run_research_agent(cfg, resume=False)
    assert summary["final_phase"] == "completed"
    req_models = summary["token_summary"]["requested_models"]
    assert "deepseek-v4-pro" in req_models
    assert "deepseek-v4.1-flash" in req_models
    assert "12" in summary["frozen_checkpoints"]


def test_zero_vs_none_usage_cost_and_2000ms_timeout() -> None:
    u_zero = extract_provider_usage({
        "model": "served-x",
        "id": "req-1",
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "prompt_tokens_details": {"cached_tokens": 0},
        },
    })
    assert u_zero["cached_tokens"] == 0
    assert u_zero["served_model"] == "served-x"

    u_missing = extract_provider_usage({"usage": {"prompt_tokens": 100, "completion_tokens": 50}})
    assert u_missing["cached_tokens"] is None

    rate_card = {
        "deepseek-v4.1-flash": {
            "input_per_m": 0.2,
            "output_per_m": 0.6,
            "cache_read_per_m": 0.05,
        }
    }
    usd, priced, reason = compute_attempt_cost_usd(
        model_alias="deepseek-v4.1-flash",
        input_tokens=1_000_000,
        output_tokens=500_000,
        cached_tokens=0,
        rate_card=rate_card,
    )
    assert priced is True and reason is None and abs(float(usd) - 0.5) < 1e-9

    usd_unpriced, priced2, reason2 = compute_attempt_cost_usd(
        model_alias="unknown-model",
        input_tokens=100,
        output_tokens=50,
        cached_tokens=None,
        rate_card=rate_card,
    )
    assert usd_unpriced is None and priced2 is False and reason2 is not None
    assert derive_effective_batch_timeout_s(24, 2000.0) >= 48.0


def test_p0_pickled_spawn_problem_claims_and_settles_generated_candidate(tmp_path: Path, monkeypatch) -> None:
    import agent_skill_loop.interface_design.session_bridge as sb_mod
    from agent_skill_loop.interface_design.session_baseline import load_dev_or_public_suite

    ledger = tmp_path / "p0_ledger.sqlite3"
    run_id = "p0_spawn_run"
    cfg = AgentConfig(
        run_id=run_id,
        output_dir=str(tmp_path),
        initial_template_id="cvrp_parallel_merge_static",
        checkpoint_budgets=(1,),
        total_request_cap=4,
        strict_checkpoint_barriers=True,
    )
    budget = PersistentRequestBudget(
        ledger,
        max_requests=4,
        run_id=run_id,
        checkpoint_budgets=(1,),
        strict_checkpoint_barriers=True,
    )
    baseline = _build_initial_baseline_solver(cfg).to_dict()
    suite = load_dev_or_public_suite("cvrp_dev_hetero_24", split="dev_train", role="diagnostic_interactive")
    insts = list(suite["instances"][:2])
    initialize_milestone_schedule(
        ledger,
        run_id=run_id,
        checkpoint_budgets=(1,),
        baseline_solver=baseline,
        baseline_dev_eval={"all_feasible": True, "completion_rate": 1.0, "penalized_mean_tour_length": 20.0, "valid_only_mean_tour_length": 20.0},
        dev_suite_hash="suite_p0",
        solve_budget_ms=500.0,
    )
    slot = budget.reserve(purpose="eoh_generation", problem="cvrp", attempt=1, model="deepseek-v4.1-flash")
    assert slot is not None and slot.attempt_token is not None
    register_attempt_provenance(
        ledger,
        attempt_token=slot.attempt_token,
        run_id=run_id,
        logical_call_id="lc_1",
        physical_request_id=slot.request_id,
        global_ordinal=1,
        purpose="eoh_generation",
    )
    budget.mark_sent(slot)
    budget.finish(slot, "complete", status=200, elapsed_seconds=0.05, input_tokens=50, output_tokens=20)

    class _DummyBridge:
        def consume_pending_attempt_token(self):
            return slot.attempt_token

    tpl = get_template_spec("cvrp_parallel_merge_static", "v1")
    design = build_design_for_template("cvrp_parallel_merge_static", "v1", postprocess_mode="none", rationale="test")
    prob = sb_mod._SessionTrackedDynamicProblem(
        session={"root": str(tmp_path), "task_id": "t1"},
        problem_id="cvrp",
        suite_hash="suite_p0",
        evaluator_hash="eval_h",
        milestone_ledger_path=ledger,
        milestone_run_id=run_id,
        strict_checkpoint_barriers=True,
        run_started_monotonic=0.0,
        bridge_ref=_DummyBridge(),
        design=design,
        instances=insts,
        suite_id="cvrp_dev_hetero_24",
    )
    unpickled = pickle.loads(pickle.dumps(prob))
    assert unpickled.bridge_ref is None

    monkeypatch.setattr(sb_mod, "solver_event", lambda *a, **kw: None)
    monkeypatch.setattr(
        DynamicInterfaceProblem,
        "evaluate_detailed",
        lambda self, code: {
            "valid": True,
            "objective": 14.5,
            "instance_objectives": [14.0, 15.0],
            "records": [
                {"valid": True, "objective": 14.0, "tour_length": 14.0},
                {"valid": True, "objective": 15.0, "tour_length": 15.0},
            ],
            "worker_wall_ms": 12.0,
        },
    )
    unpickled.evaluate_detailed(tpl.default_baseline_hook_code + "\n# spawned_improved\n")

    # Simulate parent bridge calling settle_trailing_pending("eoh_skipped", only_if_pending=True) AFTER child settled
    settle_attempt_provenance(
        ledger,
        attempt_token=slot.attempt_token,
        generation_status="eoh_skipped",
        only_if_pending=True,
    )
    # Also simulate parent running settle_pending_provenance_for_terminal_requests WHILE child holds eval_id on a pending slot
    from agent_skill_loop.milestone_checkpoint import claim_latest_pending_attempt_token, settle_pending_provenance_for_terminal_requests
    s2 = budget.reserve(purpose="eoh_generation", problem="cvrp", attempt=2, model="deepseek-v4.1-flash")
    assert s2 is not None and s2.attempt_token is not None
    register_attempt_provenance(
        ledger,
        attempt_token=s2.attempt_token,
        run_id=run_id,
        logical_call_id="lc_2",
        physical_request_id=s2.request_id,
        global_ordinal=2,
        purpose="eoh_generation",
    )
    budget.mark_sent(s2)
    budget.finish(s2, "complete", status=200, elapsed_seconds=0.05, input_tokens=50, output_tokens=20)
    claimed = claim_latest_pending_attempt_token(ledger, run_id, eval_id="ev_claimed_2")
    assert claimed == s2.attempt_token
    settle_pending_provenance_for_terminal_requests(ledger, run_id)
    con_p0 = sqlite3.connect(str(ledger))
    gen_st2 = con_p0.execute("SELECT generation_status, eval_id FROM candidate_provenance WHERE attempt_token=?", (s2.attempt_token,)).fetchone()
    con_p0.close()
    assert tuple(gen_st2) == ("pending", "ev_claimed_2")
    mstatus = read_milestone_status(ledger, run_id)
    assert len(mstatus["checkpoints"]) == 1
    assert mstatus["checkpoints"][0]["state"] == "sealed"
    assert mstatus["checkpoints"][0]["winner_source_ordinal"] == 1
    exported = export_sealed_checkpoints(ledger, run_id, tmp_path / "checkpoints")
    ckpt_data = json.loads(Path(exported["1"]).read_text(encoding="utf-8"))
    assert ckpt_data["winner_source_ordinal"] == 1
    assert ckpt_data["best_dev_objective"] == 14.5


def test_p1_stale_epoch_finish_resume_mismatch_and_monotonic_wall(tmp_path: Path) -> None:
    ledger = tmp_path / "epoch_ledger.sqlite3"
    b1 = PersistentRequestBudget(ledger, max_requests=10, run_id="ep_run", owner_epoch="epoch_old")
    s1 = b1.reserve(purpose="eoh_generation", problem="cvrp", attempt=1, model="deepseek-v4.1-flash")
    assert s1 is not None
    b1.mark_sent(s1)

    from agent_skill_loop.request_budget import BudgetExhausted
    b2 = PersistentRequestBudget(ledger, max_requests=10, run_id="ep_run", owner_epoch="epoch_new", reconcile_inflight=True)
    assert b2.reconciled_unknown_count == 1
    with pytest.raises(BudgetExhausted, match="stale_owner_superseded"):
        b1.mark_sent(s1)
    assert b1.reserve(purpose="eoh_generation", problem="cvrp", attempt=2, model="m") is None
    assert b1.denial_reason == "stale_owner_superseded"
    b1.finish(s1, "complete", status=200, input_tokens=99, output_tokens=99)
    recs = b2.request_records()
    assert recs[0]["state"] == "unknown"
    assert recs[0]["input_tokens"] is None

    # Config mismatch on resume must raise before consuming budget
    run_dir = tmp_path / "mismatch_run"
    cfg = AgentConfig(
        run_id="mismatch_run",
        output_dir=str(run_dir),
        max_rounds=1,
        total_request_cap=4,
        checkpoint_budgets=(4,),
        strict_checkpoint_barriers=True,
        use_benchmark_dev_suite=False,
        dev_instance_count=2,
        allowed_templates=("cvrp_parallel_merge_static",),
        allowed_postprocess_modes=("none",),
        mode="mock",
    )
    run_research_agent(cfg, resume=False)
    for field_name, bad_val in (("eoh_model", "some-other-model"), ("mode", "live"), ("use_benchmark_dev_suite", True)):
        bad_cfg = AgentConfig.from_dict({**cfg.to_dict(), field_name: bad_val})
        with pytest.raises(ValueError, match=f"resume_config_mismatch:{field_name}"):
            run_research_agent(bad_cfg, resume=True)

    # Monotonic wall clock across seals
    wledger = tmp_path / "wall.sqlite3"
    wb = PersistentRequestBudget(wledger, max_requests=4, run_id="wall_run", checkpoint_budgets=(1, 2), strict_checkpoint_barriers=True)
    initialize_milestone_schedule(
        wledger,
        run_id="wall_run",
        checkpoint_budgets=(1, 2),
        baseline_solver=_build_initial_baseline_solver(cfg).to_dict(),
        baseline_dev_eval={"all_feasible": True, "completion_rate": 1.0, "penalized_mean_tour_length": 15.0},
        dev_suite_hash="wh",
        solve_budget_ms=500.0,
    )
    set_run_wall_offset_seconds(wledger, "wall_run", 12.5)
    s_w1 = wb.reserve(purpose="planner", problem="cvrp", attempt=1, model="m")
    assert s_w1 is not None
    wb.mark_sent(s_w1)
    wb.finish(s_w1, "complete", status=200)
    try_seal_draining_checkpoints(wledger, "wall_run", wall_elapsed_seconds=12.5)

    s_w2 = wb.reserve(purpose="planner", problem="cvrp", attempt=2, model="m")
    assert s_w2 is not None
    wb.mark_sent(s_w2)
    wb.finish(s_w2, "complete", status=200)
    try_seal_draining_checkpoints(wledger, "wall_run", wall_elapsed_seconds=0.4)
    exp = export_sealed_checkpoints(wledger, "wall_run", tmp_path / "wckpts")
    d1 = json.loads(Path(exp["1"]).read_text(encoding="utf-8"))
    d2 = json.loads(Path(exp["2"]).read_text(encoding="utf-8"))
    assert d2["wall_elapsed_seconds_at_seal"] >= d1["wall_elapsed_seconds_at_seal"] >= 12.5


def test_p1_provider_failure_propagates_and_archives_provider_terminal_session(tmp_path: Path, monkeypatch) -> None:
    from agent_skill_loop.client import ProviderFailure
    from agent_skill_loop.session_runtime import read_state
    from research_agent.tools.session_tools import SessionRunnerTool
    from tools.run_m32_scaling import RESUMABLE_EXIT_CODE, main as m32_main

    run_dir = tmp_path / "prov_fail_run"
    cfg = AgentConfig(
        run_id="prov_fail_run",
        output_dir=str(run_dir),
        max_rounds=2,
        total_request_cap=12,
        checkpoint_budgets=(12,),
        strict_checkpoint_barriers=True,
        use_benchmark_dev_suite=False,
        dev_instance_count=2,
        allowed_templates=("cvrp_parallel_merge_static",),
        allowed_postprocess_modes=("none",),
        mode="mock",
    )
    ledger = run_dir / "agent_budget.sqlite3"
    budget = PersistentRequestBudget(ledger, max_requests=12, run_id=cfg.run_id, checkpoint_budgets=(12,), strict_checkpoint_barriers=True)
    stool = SessionRunnerTool(run_dir=run_dir, config=cfg, budget=budget)
    stool.ensure_initialized()

    # Mark session as COMPLETED with a PROVIDER_TERMINAL task while budget still has remaining requests
    con = sqlite3.connect(str(stool.session_dir / "session.sqlite3"))
    con.execute("UPDATE runs SET state='COMPLETED' WHERE run_id IS NOT NULL")
    con.execute(
        "INSERT INTO tasks(task_id, run_id, round_id, state, terminal_reason, created_at_utc) VALUES ('t_pt', (SELECT run_id FROM runs LIMIT 1), 1, 'COLLECTED', 'PROVIDER_TERMINAL', '2026-11-24T00:00:00Z')"
    )
    con.commit()
    con.close()

    assert stool._session_has_provider_terminal(stool.session_dir) is True
    # ensure_initialized must archive the poisoned session_run and start a fresh continuation session
    new_state = stool.ensure_initialized()
    assert new_state["run_state"] == "RUNNING"
    archived = list(run_dir.glob("session_run_interrupted_*"))
    assert len(archived) == 1
    assert read_state(run=archived[0])["run_state"] == "COMPLETED"

    # Also verify run-one exits RESUMABLE_EXIT_CODE (75) and preserves checkpoint on ProviderFailure
    m32_out = tmp_path / "m32_prov_exit"
    monkeypatch.setattr(
        "tools.run_m32_scaling.run_research_agent",
        lambda *a, **kw: (_ for _ in ()).throw(ProviderFailure("http_502", status=502)),
    )
    rc = m32_main([
        "--output-dir", str(m32_out),
        "run-one",
        "--track", "curve",
        "--seed", "20261124",
        "--mode", "mock",
        "--request-cap", "36",
        "--checkpoints", "36",
    ])
    assert rc == RESUMABLE_EXIT_CODE
