"""Milestone 3 Phase 3A tests:
- Durable crash-recoverable PersistentRequestBudget (reserve -> sent -> crash -> unknown -> retry conservation + checkpoint crossings)
- L3 cvrp_ruin_recreate/v1 template, L3-ctrl (Worst Removal), Gate-4 6-customer 4-of-6 causal ruin probe,
  unified CW+2opt+LNS deadline, first_feasible_ms & anytime_curve, deterministic replay, & multi-problem adapters
- Session Bridge M3 fixes: 25ms consistent budget across submit/EoH/revalidate/FrozenSolver, locked KB release & hash,
  arm-controlled zero static KB clue payload, and L3 mock EoH round via Session Runtime
- Fresh M3 blind commitment isolation, external custody path enforcement, and dev_24 vs select_64 role isolation
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import time
from pathlib import Path

import pytest

from agent_skill_loop.benchmark.catalog import load_profile_suite
from agent_skill_loop.cvrp_workbench.suites import BENCHMARK_ID
from agent_skill_loop.interface_design.blind_commitment import (
    M3_BLIND_COMMITMENT_PATH,
    SEALED_M3_BLIND_SUITE_ID,
    _generator_source_sha256,
    assert_suite_allowed_for_interactive_role,
    assert_suite_not_blind,
    read_public_blind_commitment,
    seal_m3_blind_120,
    verify_sealed_against_commitment,
)
from agent_skill_loop.interface_design.contracts import (
    OUTCOME_BUDGET_EXHAUSTED_INCUMBENT,
    OUTCOME_COMPLETED,
    OUTCOME_TIMEOUT_OR_INFEASIBLE,
)
from agent_skill_loop.interface_design.dynamic_eoh import (
    DEFAULT_MOCK_CANDIDATES_BY_TEMPLATE,
    run_dynamic_eoh_evolution,
)
from agent_skill_loop.interface_design.runtime import (
    PROBLEM_ADAPTERS,
    compile_hook_function,
    evaluate_hook_on_instance_inprocess,
)
from agent_skill_loop.interface_design.session_bridge import resolve_session_time_budget_ms
from agent_skill_loop.interface_design.templates import (
    CLASSIC_L3_WORST_REMOVAL_HOOK_CODE,
    TEMPLATE_REGISTRY,
    _l3_build_anytime_curve,
    build_ruin_recreate_design,
    get_template_spec,
)
from agent_skill_loop.interface_design.validator import PROBLEM_GATE_PROBES, InterfaceValidator
from agent_skill_loop.request_budget import PersistentRequestBudget, RequestBudget
from agent_skill_loop.session_actions import collect, execute, finish_round, read_evaluation, submit_evaluation, submit_plan
from agent_skill_loop.session_ledger import SessionRequestBudget
from agent_skill_loop.session_runtime import _connect, initialize_session, read_state

REPO = Path(__file__).resolve().parents[1]


def test_persistent_request_budget_crash_recovery_and_checkpoint_crossing(tmp_path: Path) -> None:
    ledger_db = tmp_path / "agent_budget.sqlite3"
    hit_checkpoints: list[tuple[int, int]] = []

    budget1 = PersistentRequestBudget(
        ledger_db,
        max_requests=5,
        run_id="m3_run_crash_test",
        checkpoint_budgets=(2, 4, 5),
        on_checkpoint=lambda ckpt, cur: hit_checkpoints.append((ckpt, cur)),
    )
    # 1. Completed request records terminal state and response SHA-256
    s1 = budget1.reserve(purpose="planner", problem="cvrp", attempt=1, model="deepseek-chat")
    assert s1 is not None and s1.index == 1 and s1.attempt == 1
    budget1.mark_sent(s1)
    assert s1.state == "sent"
    payload = '{"action": "diagnose"}'
    ev1 = budget1.finish(s1, "complete", status=200, input_tokens=40, output_tokens=15, response_text=payload)
    assert ev1["response_sha256"] == hashlib.sha256(payload.encode("utf-8")).hexdigest()

    # 2. Simulate crash in BOTH pre-send reserved window AND sent-before-receipt window
    s2 = budget1.reserve(purpose="eoh_generation", problem="cvrp", attempt=1, model="deepseek-chat")
    assert s2 is not None and s2.index == 2
    assert hit_checkpoints == [(2, 2)]

    s3 = budget1.reserve(purpose="eoh_generation", problem="cvrp", attempt=2, model="deepseek-chat")
    assert s3 is not None and s3.index == 3
    budget1.mark_sent(s3)
    # Process dies without calling finish(s2/s3)
    del budget1

    # 3. Restart in a new process object: interrupted requests convert to consumed 'unknown' (no refund!)
    restarted_hits: list[tuple[int, int]] = []
    budget2 = PersistentRequestBudget(
        ledger_db,
        max_requests=5,
        run_id="m3_run_crash_test",
        checkpoint_budgets=(2, 4, 5),
        on_checkpoint=lambda ckpt, cur: restarted_hits.append((ckpt, cur)),
    )
    assert budget2.reconciled_unknown_count == 2
    assert budget2.used == 3
    assert budget2.remaining == 2

    records_before_retry = budget2.request_records()
    assert [r["state"] for r in records_before_retry] == ["complete", "unknown", "unknown"]
    assert records_before_retry[1]["error_code"] == "interrupted_inflight"
    assert records_before_retry[2]["sent_at_utc"] is not None
    assert records_before_retry[2]["response_sha256"] is None

    # Trying to inflate max_requests across restart must fail
    with pytest.raises(ValueError, match="cannot_increase_persisted_max_requests"):
        PersistentRequestBudget(ledger_db, max_requests=10, run_id="m3_run_crash_test")

    # Child cap delegates cleanly and respects remaining=2
    child = RequestBudget(3, parent=budget2)
    s4 = child.reserve(purpose="eoh_generation", problem="cvrp", attempt=3, model="deepseek-chat")
    assert s4 is not None and s4.index == 4
    child.mark_sent(s4)
    child.finish(s4, "complete", status=200, input_tokens=10, output_tokens=5, response_text="ok4")
    assert restarted_hits == [(4, 4)]

    s5 = child.reserve(purpose="planner", problem="cvrp", attempt=1, model="deepseek-chat")
    assert s5 is not None and s5.index == 5
    child.finish(s5, "failed", status=500, error_code="http_500")
    assert restarted_hits == [(4, 4), (5, 5)]

    # Slot 6 MUST be refused; total attempts remain strictly capped at 5
    assert child.reserve(purpose="planner", problem="cvrp", attempt=1, model="deepseek-chat") is None
    assert budget2.remaining == 0
    summary = budget2.summary()
    assert summary["attempted_requests"] == 5
    assert summary["remaining"] == 0
    assert summary["by_state"] == {"complete": 2, "unknown": 2, "failed": 1}

    # Check batch crossing condition prev_used < ckpt <= curr_used (e.g., 33 -> 39 crosses 36)
    batch_hits: list[tuple[int, int]] = []
    batch_budget = RequestBudget(50, checkpoint_budgets=(36, 100), on_checkpoint=lambda c, u: batch_hits.append((c, u)))
    assert batch_budget.check_checkpoints(33, 39) == [36]
    assert batch_budget.check_checkpoints(39, 45) == []
    assert batch_hits == [(36, 39)]


def test_l3_ruin_recreate_gates_6cust_probe_anytime_and_determinism(tmp_path: Path) -> None:
    assert ("cvrp_ruin_recreate", "v1") in TEMPLATE_REGISTRY
    assert "cvrp" in PROBLEM_ADAPTERS
    assert "cvrp" in PROBLEM_GATE_PROBES

    design_ctrl = build_ruin_recreate_design()
    # Both 500ms and 25ms must pass all 5 gates with 6-cust 4-of-6 causal ruin probe
    for budget_ms in (500.0, 25.0):
        validator = InterfaceValidator(candidate_timeout_s=20.0, instance_time_budget_ms=budget_ms)
        report = validator.validate(design_ctrl)
        assert report.passed is True, (budget_ms, [f.as_dict() for f in report.failures])
        g4 = report.diagnostics["gate4"]
        assert g4["instance_id"] == "m3_gate4_dual_action_6cust"
        assert g4["prefer_A_first_merge"] == [1, 2, 3, 4]
        assert g4["prefer_B_first_merge"] == [3, 4, 5, 6]
        assert g4["prefer_A_pre_routes"] != g4["prefer_B_pre_routes"]
        g5 = report.diagnostics["gate5"]
        assert g5["outcome_counts"][OUTCOME_TIMEOUT_OR_INFEASIBLE] == 0
        assert g5["scale_drift_pct"] == 0.0
        g5_ids = [row["instance_id"] for row in g5["timing_breakdown"]]
        assert g5_ids[:2] == ["m3_gate5_stress_n200_00", "m3_gate5_stress_n200_01"]
        assert all("select" not in str(iid) for iid in g5_ids)

    # Verify Anytime missing rule for checkpoints strictly before first_feasible_ms
    curve_unit = _l3_build_anytime_curve(
        [(18.0, 42.0), (120.0, 40.5)],
        first_feasible_ms=18.0,
        end_ms=200.0,
        budget_exhausted=True,
    )
    assert curve_unit == {"10": None, "25": 42.0, "100": 42.0, "250": None, "500": None}

    # Verify deterministic replay under fixed max_iters and anytime_curve under 500ms
    tpl = get_template_spec("cvrp_ruin_recreate", "v1")
    fn = compile_hook_function(
        CLASSIC_L3_WORST_REMOVAL_HOOK_CODE,
        hook_name=tpl.hook_name,
        expected_args=tpl.hook_signature,
    )
    dev_inst = load_profile_suite(BENCHMARK_ID, "cvrp_dev_hetero_24", split="dev_train")["instances"][0]
    r1 = evaluate_hook_on_instance_inprocess(
        template_id="cvrp_ruin_recreate",
        template_version="v1",
        hook_fn=fn,
        instance=dev_inst,
        template_options={"max_iters": 8},
        time_budget_ms=None,
    )
    r2 = evaluate_hook_on_instance_inprocess(
        template_id="cvrp_ruin_recreate",
        template_version="v1",
        hook_fn=fn,
        instance=dev_inst,
        template_options={"max_iters": 8},
        time_budget_ms=None,
    )
    assert r1["valid"] is True and r1["routes"] == r2["routes"]
    assert abs(float(r1["tour_length"]) - float(r2["tour_length"])) == 0.0
    assert r1["outcome_class"] == OUTCOME_COMPLETED
    assert r1["first_feasible_ms"] >= 0.0

    # Tight budget on n=200 must return feasible incumbent (no timeout_or_infeasible)
    sel_suite = load_profile_suite(BENCHMARK_ID, "cvrp_select_multiscale_64", split="selection")
    n200_inst = next(inst for inst in sel_suite["instances"] if int(inst["size"]) == 200)
    r_tight = evaluate_hook_on_instance_inprocess(
        template_id="cvrp_ruin_recreate",
        template_version="v1",
        hook_fn=fn,
        instance=n200_inst,
        time_budget_ms=25.0,
    )
    assert r_tight["valid"] is True
    assert r_tight["outcome_class"] in {OUTCOME_COMPLETED, OUTCOME_BUDGET_EXHAUSTED_INCUMBENT}
    assert r_tight["first_feasible_ms"] >= 0.0
    for cp_k, cp_v in r_tight["anytime_curve"].items():
        if int(cp_k) < r_tight["first_feasible_ms"]:
            assert cp_v is None

    # End-to-end L3 mock EoH evolution
    res_eoh = run_dynamic_eoh_evolution(
        design=design_ctrl,
        output_dir=tmp_path / "l3_mock_eoh",
        suite_id="cvrp_dev_hetero_24",
        split="dev_train",
        max_instances=4,
        pop_size=2,
        n_pop=1,
        max_sample_nums=2,
        instance_time_budget_ms=250.0,
        mode="mock",
        mock_responses=DEFAULT_MOCK_CANDIDATES_BY_TEMPLATE["cvrp_ruin_recreate"],
        require_evolved=True,
    )
    assert res_eoh["ok"] is True
    assert res_eoh["frozen_solver"]["template_id"] == "cvrp_ruin_recreate"
    assert res_eoh["frozen_solver"]["default_budget_ms"] == 250.0


def test_session_bridge_25ms_budget_locked_kb_no_clue_and_l3_mock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_SKILL_M2_MOCK", "1")
    monkeypatch.setenv("OPENCODE_GO_API_KEY", "mock-key")

    with pytest.raises(ValueError, match="session_time_budget_mismatch"):
        resolve_session_time_budget_ms({"time_budget_ms": 25.0}, {"instance_time_budget_ms": 500.0})

    run_dir = tmp_path / "session_m3_25ms_nokb"
    init_res = initialize_session(
        output=run_dir,
        operation_id="op_init_m3",
        eoh_model="deepseek-chat",
        eoh_endpoint="mock://local",
        eoh_api_key_env="OPENCODE_GO_API_KEY",
        eoh_max_requests=10,
        engine_wall_seconds=120.0,
        memory_enabled=False,
        seed=20261124,
        size=15,
        count=3,
        search_policy_defaults={"pop_size": 2, "n_pop": 1, "max_sample_nums": 2},
    )
    ver = init_res["state_version"]

    plan_file = tmp_path / "plan_m3_l3_25ms.json"
    plan_file.write_text(
        json.dumps(
            {
                "round_id": 1,
                "direction": "Switch to L3 cvrp_ruin_recreate/v1 under 25ms with inject_static_kb_clues=False.",
                "operations": [
                    {
                        "type": "replace",
                        "target": "score_ruin_nodes",
                        "mechanism": "Normalized removal savings plus capacity slack under 25ms deadline.",
                    }
                ],
                "preserve": "Exact feasibility and zero static KB clue injection.",
                "feedback_basis": None,
                "memory_basis": [],
                "reference_skill_ref": None,
                "hypothesis": "L3 candidate executes cleanly under unified 25ms Session budget without static KB clues.",
                "interface_selection": {
                    "template_id": "cvrp_ruin_recreate",
                    "template_version": "v1",
                    "postprocess_mode": "none",
                    "time_budget_ms": 25.0,
                    "template_options": {"inject_static_kb_clues": False},
                    "cited_kb_ids": [],
                    "rationale": "Verify M3-02 plumbing and L3 mock EoH end-to-end.",
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    sub_res = submit_plan(run=run_dir, operation_id="op_plan_m3", expected_state_version=ver, file=plan_file)
    iface_meta = sub_res["result"]["interface_selection"]
    assert iface_meta["validation_passed"] is True
    assert iface_meta["instance_time_budget_ms"] == 25.0
    assert iface_meta["kb_release_id"] == "20261123-main-co-workbench-m2"
    assert len(iface_meta["kb_manifest_sha256"]) == 64

    submit_val = json.loads((run_dir / iface_meta["validation_ref"]).read_text(encoding="utf-8"))
    assert submit_val["diagnostics"]["gate5"]["budget_ms"] == 25.0

    ver = sub_res["state_version"]
    exec_res = execute(run=run_dir, operation_id="op_exec_m3", expected_state_version=ver)
    assert exec_res["ok"] is True

    deadline = time.monotonic() + 60.0
    st = read_state(run=run_dir)
    while time.monotonic() < deadline:
        if (st.get("task") or {}).get("state") == "EXITED":
            break
        time.sleep(0.2)
        st = read_state(run=run_dir)
    assert (st.get("task") or {}).get("terminal_reason") == "SUCCEEDED", st

    eoh_dir = run_dir / "rounds" / "round_0001" / "eoh_run"
    summary = json.loads((eoh_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["template_id"] == "cvrp_ruin_recreate"
    assert summary["instance_time_budget_ms"] == 25.0
    assert summary["kb_release_id"] == "20261123-main-co-workbench-m2"
    assert summary["kb_manifest_sha256"] == iface_meta["kb_manifest_sha256"]
    assert summary["static_kb_clues_injected"] is False

    task_desc = (eoh_dir / "task_description.txt").read_text(encoding="utf-8")
    assert "KB DOMAIN CLUES" not in task_desc

    winner_vals = json.loads((eoh_dir / "winner_validation_report.json").read_text(encoding="utf-8"))
    assert winner_vals and winner_vals[-1]["validation"]["diagnostics"]["gate5"]["budget_ms"] == 25.0

    frozen = json.loads((eoh_dir / "frozen_solver_manifest.json").read_text(encoding="utf-8"))
    assert frozen["default_budget_ms"] == 25.0
    assert frozen["kb_release_id"] == "20261123-main-co-workbench-m2"
    assert frozen["template_id"] == "cvrp_ruin_recreate"

    col_res = collect(run=run_dir, operation_id="op_col_m3", expected_state_version=st["state_version"])
    ver = col_res["state_version"]
    facts = read_evaluation(run=run_dir)["result"]
    eval_file = tmp_path / "eval_m3.json"
    eval_file.write_text(
        json.dumps(
            {
                "plan_alignment": "aligned",
                "observations": [{"claim": "L3 25ms Session execution succeeded.", "evidence_refs": facts["evidence_refs"][:1]}],
                "hypotheses": [{"claim": "25ms budget propagated end-to-end.", "confidence": "high", "evidence_refs": facts["evidence_refs"][:1]}],
                "next_search_advice": {"direction": "Done"},
                "memory_action": {"kind": "disabled"},
            }
        ),
        encoding="utf-8",
    )
    se_res = submit_evaluation(run=run_dir, operation_id="op_eval_m3", expected_state_version=ver, file=eval_file)
    fin_res = finish_round(run=run_dir, operation_id="op_fin_m3", expected_state_version=se_res["state_version"], decision="complete")
    assert fin_res["run_state"] == "COMPLETED"

    with sqlite3.connect(run_dir / "session.sqlite3") as con:
        cols = {row[1] for row in con.execute("PRAGMA table_info(requests)")}
        assert {"attempt", "response_sha256", "sent_at_utc"}.issubset(cols)


def test_m3_blind_commitment_external_custody_and_split_guardrails(tmp_path: Path) -> None:
    # 1. Verify committed M3 public commitment exists, matches current generator source hash & leaks zero coords/seeds
    comm = read_public_blind_commitment(M3_BLIND_COMMITMENT_PATH, expected_suite_id=SEALED_M3_BLIND_SUITE_ID)
    assert comm["suite_id"] == SEALED_M3_BLIND_SUITE_ID
    assert comm["instance_count"] == 120
    assert comm["generator_source_sha256"] == _generator_source_sha256()
    ext_sealed = Path.home() / ".agent_skill_custody" / "m3_blind" / "cvrp_m3_blind_120_sealed.json"
    if ext_sealed.is_file():
        real_ver = verify_sealed_against_commitment(sealed_path=ext_sealed, commitment_path=M3_BLIND_COMMITMENT_PATH)
        assert real_ver["ok"] is True and real_ver["verified_instances"] == 120
    raw_comm = M3_BLIND_COMMITMENT_PATH.read_text(encoding="utf-8")
    for forbidden in ("customer_coordinates", "sealed_seed_token", '"demands"', '"depot"'):
        assert forbidden not in raw_comm

    # 2. Seal helper MUST reject in-repo custody path
    with pytest.raises(ValueError, match="blind_custody_path_must_be_outside_repository"):
        seal_m3_blind_120(
            commitment_path=tmp_path / "comm.json",
            sealed_path=tmp_path / "inside_repo_sealed.json",
        )

    # 3. External custody seal + verification + tamper detection (using OS temp outside REPO)
    with tempfile.TemporaryDirectory() as ext_tmp:
        ext_dir = Path(ext_tmp).resolve()
        assert not ext_dir.is_relative_to(REPO.resolve())
        sealed_file = ext_dir / "m3_sealed.json"
        comm_file = tmp_path / "m3_comm.json"
        res = seal_m3_blind_120(
            commitment_path=comm_file,
            sealed_path=sealed_file,
            seed_token="test-m3-custody-seed",
        )
        assert res["ok"] is True and res["instance_count"] == 120
        ver = verify_sealed_against_commitment(sealed_path=sealed_file, commitment_path=comm_file)
        assert ver["ok"] is True and ver["verified_instances"] == 120

        tampered = json.loads(sealed_file.read_text(encoding="utf-8"))
        tampered["instances"][0]["capacity"] += 1
        sealed_file.write_text(json.dumps(tampered), encoding="utf-8")
        with pytest.raises(ValueError, match="blind_suite_sha256_mismatch"):
            verify_sealed_against_commitment(sealed_path=sealed_file, commitment_path=comm_file)

    # 4. Blind & interactive selection split isolation
    for blind_sid in ("cvrp_m2_blind_120", "cvrp_m3_blind_120", "cvrp_m32_blind_120", "locked_future_blind"):
        with pytest.raises(ValueError, match="blind_suite_forbidden"):
            assert_suite_not_blind(blind_sid)

    assert_suite_allowed_for_interactive_role("cvrp_dev_hetero_24", role="interactive_sandbox")
    with pytest.raises(ValueError, match="selection_suite_forbidden_in_interactive_role"):
        assert_suite_allowed_for_interactive_role("cvrp_select_multiscale_64", role="interactive_sandbox")
    with pytest.raises(ValueError, match="selection_suite_forbidden_in_interactive_role"):
        assert_suite_allowed_for_interactive_role("custom", {"suite_role": "selection"}, role="feedback_archive")


def test_legacy_session_requests_schema_auto_migrates_on_resume(tmp_path: Path) -> None:
    run_dir = tmp_path / "legacy_session"
    init_res = initialize_session(
        output=run_dir,
        operation_id="init_legacy",
        eoh_model="deepseek-chat",
        eoh_endpoint="mock://local",
        seed=20261124,
        size=10,
        count=2,
        memory_enabled=False,
    )
    # Downgrade `requests` table to exact pre-3A schema (missing attempt, response_sha256, sent_at_utc)
    con = _connect(run_dir / "session.sqlite3")
    try:
        con.execute("DROP TABLE requests")
        con.execute(
            """
            CREATE TABLE requests (
                request_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                round_id INTEGER,
                task_id TEXT,
                sequence INTEGER NOT NULL,
                purpose TEXT NOT NULL CHECK (purpose IN ('eoh_probe','eoh_generation','eoh_repair')),
                model TEXT,
                state TEXT NOT NULL CHECK (state IN ('reserved','sent','complete','failed','unknown')),
                status INTEGER,
                input_tokens INTEGER,
                output_tokens INTEGER,
                elapsed_seconds REAL,
                error_code TEXT,
                finish_reason TEXT,
                created_at_utc TEXT NOT NULL,
                finished_at_utc TEXT,
                UNIQUE(run_id, sequence),
                FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
            )
            """
        )
        run_id = con.execute("SELECT run_id FROM runs").fetchone()[0]
        old_cols = {r[1] for r in con.execute("PRAGMA table_info(requests)")}
        assert "attempt" not in old_cols
    finally:
        con.close()

    # Re-opening via submit_plan auto-migrates missing columns before executing
    plan_file = tmp_path / "legacy_plan.json"
    plan_file.write_text(
        json.dumps(
            {
                "round_id": 1,
                "direction": "Continue legacy session",
                "operations": [{"type": "preserve", "target": "interface", "mechanism": "resume"}],
                "preserve": "compatibility",
                "feedback_basis": None,
                "memory_basis": [],
                "reference_skill_ref": None,
                "hypothesis": "Auto migration restores request columns on resume.",
            }
        ),
        encoding="utf-8",
    )
    sub = submit_plan(run=run_dir, operation_id="plan_legacy", expected_state_version=init_res["state_version"], file=plan_file)
    assert sub["ok"] is True

    # Simulate an active task writing via SessionRequestBudget into migrated DB
    con = _connect(run_dir / "session.sqlite3")
    try:
        cols_after = {r[1] for r in con.execute("PRAGMA table_info(requests)")}
        assert {"attempt", "response_sha256", "sent_at_utc"}.issubset(cols_after)
        con.execute(
            "INSERT INTO tasks(task_id,run_id,round_id,state,created_at_utc) VALUES ('t_leg',?,1,'RUNNING','2026-11-23T00:00:00Z')",
            (run_id,),
        )
    finally:
        con.close()

    sb = SessionRequestBudget(run_dir, "t_leg")
    slot = sb.reserve(purpose="eoh_generation", problem="cvrp", attempt=2, model="deepseek-chat")
    assert slot is not None
    sb.mark_sent(slot)
    sb.finish(slot, "complete", status=200, input_tokens=5, output_tokens=3, response_text="legacy ok")

    con = _connect(run_dir / "session.sqlite3")
    try:
        rec = dict(con.execute("SELECT state, attempt, sent_at_utc, response_sha256 FROM requests").fetchone())
        assert rec["state"] == "complete"
        assert rec["attempt"] == 2
        assert rec["sent_at_utc"] is not None
        assert rec["response_sha256"] == hashlib.sha256(b"legacy ok").hexdigest()
    finally:
        con.close()


def test_two_layer_shared_persistent_budget_in_live_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from eoh_frozen.smoke import fixture_provider

    monkeypatch.setenv("SESSION_SHARED_BUDGET_KEY", "fixture-secret")
    ledger_db = tmp_path / "shared_agent_budget.sqlite3"
    run_key = "shared_outer_inner_run"
    outer_budget = PersistentRequestBudget(ledger_db, max_requests=4, run_id=run_key)
    outer_slot = outer_budget.reserve(purpose="planner", problem="cvrp", attempt=1, model="deepseek-chat")
    assert outer_slot is not None
    outer_budget.mark_sent(outer_slot)
    outer_budget.finish(outer_slot, "complete", status=200, input_tokens=12, output_tokens=6, response_text="plan")
    assert outer_budget.used == 1 and outer_budget.remaining == 3

    l3_replies = iter(DEFAULT_MOCK_CANDIDATES_BY_TEMPLATE["cvrp_ruin_recreate"])

    def responder(prompt: str, idx: int) -> tuple[int, str]:
        if prompt == "1+1=?":
            return 200, "2"
        return 200, next(l3_replies, DEFAULT_MOCK_CANDIDATES_BY_TEMPLATE["cvrp_ruin_recreate"][-1])

    run_dir = tmp_path / "shared_session"
    with fixture_provider("cvrp_construct", responder=responder) as (endpoint, prompts):
        init_res = initialize_session(
            output=run_dir,
            operation_id="op_init_shared",
            eoh_model="deepseek-chat",
            eoh_endpoint=endpoint,
            eoh_api_key_env="SESSION_SHARED_BUDGET_KEY",
            eoh_max_requests=12,
            engine_wall_seconds=120.0,
            memory_enabled=False,
            seed=20261124,
            size=12,
            count=2,
            search_policy_defaults={"pop_size": 2, "n_pop": 1, "max_sample_nums": 6},
            persistent_budget={"ledger_path": str(ledger_db), "max_requests": 4, "run_id": run_key},
        )
        plan_file = tmp_path / "plan_shared.json"
        plan_file.write_text(
            json.dumps(
                {
                    "round_id": 1,
                    "direction": "Verify shared two-layer persistent budget",
                    "operations": [{"type": "replace", "target": "score_ruin_nodes", "mechanism": "Shared cap"}],
                    "preserve": "Budget conservation",
                    "feedback_basis": None,
                    "memory_basis": [],
                    "reference_skill_ref": None,
                    "hypothesis": "Inner EoH stops when outer persistent budget reaches 4 total calls.",
                    "interface_selection": {
                        "template_id": "cvrp_ruin_recreate",
                        "template_version": "v1",
                        "postprocess_mode": "none",
                        "time_budget_ms": 250.0,
                        "template_options": {"inject_static_kb_clues": False},
                        "cited_kb_ids": [],
                        "rationale": "Shared outer/inner cap integration test.",
                    },
                }
            ),
            encoding="utf-8",
        )
        sub = submit_plan(run=run_dir, operation_id="op_plan_shared", expected_state_version=init_res["state_version"], file=plan_file)
        execute(run=run_dir, operation_id="op_exec_shared", expected_state_version=sub["state_version"])

        deadline = time.monotonic() + 60.0
        st = read_state(run=run_dir)
        while time.monotonic() < deadline:
            if (st.get("task") or {}).get("state") == "EXITED":
                break
            time.sleep(0.2)
            st = read_state(run=run_dir)
        assert (st.get("task") or {}).get("state") == "EXITED", st

        # Outer budget started with 1 used out of 4; inner HTTP traffic must stop at exactly 3 calls (total=4)
        assert len(prompts) == 3

    reloaded = PersistentRequestBudget(ledger_db, max_requests=4, run_id=run_key)
    assert reloaded.used == 4
    assert reloaded.remaining == 0
    recs = reloaded.request_records()
    assert len(recs) == 4
    assert recs[0]["purpose"] == "planner"
    assert all(r["purpose"].startswith("eoh_") for r in recs[1:])
    assert all(r["response_sha256"] for r in recs)

    with sqlite3.connect(run_dir / "session.sqlite3") as con:
        s_rows = con.execute("SELECT request_id, state, response_sha256 FROM requests ORDER BY sequence ASC").fetchall()
        assert len(s_rows) == 3
        assert [r[0] for r in s_rows] == [r["request_id"] for r in recs[1:]]
        assert all(r[2] == recs[i + 1]["response_sha256"] for i, r in enumerate(s_rows))
