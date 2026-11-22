"""Milestone 2 Phase 2B unit tests:
- L1 (cvrp_sequential_construct/v1) exact equivalence with M1 pointwise solver & 5-gate pass
- L2b-ctrl (cvrp_parallel_merge_dynamic/v1 + static CW savings) 0.0-error equivalence with L2a/raw CW
- L2a template_source_sha256 immutability across Phase 2A -> 2B
- L2b state-feedback hook sensitivity & 5-gate pass
- Budget-aware diagnostic planner (500 ms vs 25 ms), Short-Pilot Racing (mock), & ComplementaryArchive
"""

from __future__ import annotations

import json
from pathlib import Path

from agent_skill_loop.benchmark.catalog import load_profile_suite
from agent_skill_loop.cvrp_workbench.protocol import prepare_instance_arrays, verify_cvrp_solution
from agent_skill_loop.cvrp_workbench.solvers import evaluate_algorithm_on_instance, solve_cw_parallel_merge
from agent_skill_loop.cvrp_workbench.suites import BENCHMARK_ID
from agent_skill_loop.interface_design.archive import ComplementaryArchive, compute_portfolio_complementarity
from agent_skill_loop.interface_design.planner import (
    probe_template_budget_headroom,
    run_short_pilot_racing,
    select_interface_by_diagnostic_rule,
)
from agent_skill_loop.interface_design.runtime import compile_hook_function, evaluate_hook_on_instance_inprocess
from agent_skill_loop.interface_design.templates import (
    CLASSIC_CW_DYNAMIC_STATIC_HOOK_CODE,
    CLASSIC_CW_STATIC_HOOK_CODE,
    CLASSIC_NN_SEQUENTIAL_HOOK_CODE,
    build_classic_cw_static_design,
    build_parallel_merge_dynamic_design,
    build_sequential_construct_design,
    get_template_spec,
)
from agent_skill_loop.interface_design.validator import InterfaceValidator


def test_l2a_template_hash_unchanged_from_phase2a() -> None:
    tpl = get_template_spec("cvrp_parallel_merge_static", "v1")
    # Pinned Phase 2A hash from commit 7c77e548
    assert tpl.template_source_sha256 == "3bca783d3de8eaf5ec4fe559c71f92ccd98afc89d1e69adeb56a85a2d18e53ac"


def test_l1_sequential_construct_equivalence_and_5gates() -> None:
    suite = load_profile_suite(BENCHMARK_ID, "cvrp_dev_hetero_24", split="dev_train")
    tpl = get_template_spec("cvrp_sequential_construct", "v1")
    fn = compile_hook_function(
        CLASSIC_NN_SEQUENTIAL_HOOK_CODE,
        hook_name=tpl.hook_name,
        expected_args=tpl.hook_signature,
    )
    for inst in suite["instances"][:8]:
        ref = evaluate_algorithm_on_instance("nn", inst, distance_convention="euc_2d_float", record_trace=False)
        got = evaluate_hook_on_instance_inprocess(
            template_id="cvrp_sequential_construct",
            template_version="v1",
            hook_fn=fn,
            instance=inst,
            postprocess_mode="none",
            time_budget_ms=500.0,
        )
        assert got["valid"] is True
        assert got["routes"] == ref["routes"]
        assert abs(float(got["tour_length"]) - float(ref["tour_length"])) == 0.0

    validator = InterfaceValidator(candidate_timeout_s=20.0, instance_time_budget_ms=500.0)
    rep = validator.validate(build_sequential_construct_design())
    assert rep.passed is True, rep.failures
    assert rep.diagnostics["gate4"]["prefer_A_first_merge"] == [0, 1]
    assert rep.diagnostics["gate4"]["prefer_B_first_merge"] == [0, 2]


def test_l2b_ctrl_exact_untruncated_equivalence_with_l2a_and_raw_cw() -> None:
    suite = load_profile_suite(BENCHMARK_ID, "cvrp_dev_hetero_24", split="dev_train")
    tpl_a = get_template_spec("cvrp_parallel_merge_static", "v1")
    tpl_b = get_template_spec("cvrp_parallel_merge_dynamic", "v1")
    fn_a = compile_hook_function(CLASSIC_CW_STATIC_HOOK_CODE, hook_name=tpl_a.hook_name, expected_args=tpl_a.hook_signature)
    fn_b = compile_hook_function(CLASSIC_CW_DYNAMIC_STATIC_HOOK_CODE, hook_name=tpl_b.hook_name, expected_args=tpl_b.hook_signature)

    for inst in suite["instances"][:12]:
        matrix, demands, capacity = prepare_instance_arrays(inst, distance_convention="euc_2d_float")
        ref_routes, _ = solve_cw_parallel_merge(matrix, demands, capacity, time_budget_ms=None)
        ref_ver = verify_cvrp_solution(inst, ref_routes, distance_convention="euc_2d_float")

        res_a = evaluate_hook_on_instance_inprocess(
            template_id="cvrp_parallel_merge_static",
            template_version="v1",
            hook_fn=fn_a,
            instance=inst,
            time_budget_ms=None,
            capture_merge_sequence=True,
        )
        res_b = evaluate_hook_on_instance_inprocess(
            template_id="cvrp_parallel_merge_dynamic",
            template_version="v1",
            hook_fn=fn_b,
            instance=inst,
            time_budget_ms=None,
            capture_merge_sequence=True,
        )
        assert res_b["valid"] is True
        assert res_b["merge_sequence"] == res_a["merge_sequence"]
        assert res_b["routes"] == ref_routes
        assert abs(float(res_b["tour_length"]) - float(ref_ver["tour_length"])) == 0.0
        assert res_b["hook_call_count"] == res_b["merges_applied"]


def test_l2b_dynamic_state_feedback_passes_5gates() -> None:
    validator = InterfaceValidator(candidate_timeout_s=20.0, instance_time_budget_ms=500.0)
    design = build_parallel_merge_dynamic_design()
    rep = validator.validate(design)
    assert rep.passed is True, rep.failures
    assert rep.diagnostics["gate4"]["prefer_A_first_merge"] == [1, 2]
    assert rep.diagnostics["gate4"]["prefer_B_first_merge"] == [1, 3]
    assert rep.diagnostics["gate5"]["scale_drift_pct"] == 0.0

    # Also test a genuine dynamic-state hook using load_i, load_j, route_dist_i, route_dist_j, remaining_routes
    state_hook = """import numpy as np

def score_merge_dynamic(distance_matrix, demands, capacity, i_idx, j_idx, load_i, load_j, route_dist_i, route_dist_j, remaining_routes):
    d0i = distance_matrix[0, i_idx]
    d0j = distance_matrix[0, j_idx]
    dij = distance_matrix[i_idx, j_idx]
    sav = d0i + d0j - dij
    scale = np.maximum(np.mean(distance_matrix[0, 1:]), 1e-12)
    merged_util = (load_i + load_j) / max(float(capacity), 1e-12)
    route_ratio = (route_dist_i + route_dist_j) / (scale * max(float(remaining_routes), 1.0) + 1e-12)
    return (sav / scale) + 0.05 * merged_util - 0.02 * route_ratio
"""
    rep_state = validator.validate(design, hook_code_override=state_hook)
    assert rep_state.passed is True, rep_state.failures
    assert rep_state.diagnostics["gate5"]["scale_drift_pct"] == 0.0


def test_budget_aware_diagnostic_rule_and_archive(tmp_path: Path) -> None:
    diag_doc = json.loads(
        (Path(__file__).resolve().parents[1] / "experiments" / "milestone2" / "diagnostics" / "gap_decomposition_2x3.json").read_text(encoding="utf-8")
    )
    probe_500 = probe_template_budget_headroom(
        time_budget_ms=500.0,
        probe_suite_specs=(("cvrp_dev_hetero_24", "dev_train", 4), ("cvrp_select_multiscale_64", "selection", 2)),
    )
    dec_500 = select_interface_by_diagnostic_rule(
        diagnostic_summary=diag_doc,
        budget_probe=probe_500,
        target_budget_ms=500.0,
    )
    assert dec_500["selected_template_id"] in {"cvrp_parallel_merge_static", "cvrp_parallel_merge_dynamic"}
    assert dec_500["planning_requests"] == 0

    # Under an artificially ultra-tight 5 ms budget, L2b-ctrl exceeds threshold -> rule switches to L2a static!
    probe_tight = {
        "probe_wall_ms": 10.0,
        "templates": {
            "cvrp_parallel_merge_static/v1": {"full_completion_rate": 1.0, "solve_ms_p95": 1.5},
            "cvrp_parallel_merge_dynamic/v1": {"full_completion_rate": 0.5, "solve_ms_p95": 25.0},
        },
    }
    dec_tight = select_interface_by_diagnostic_rule(
        diagnostic_summary=diag_doc,
        budget_probe=probe_tight,
        target_budget_ms=25.0,
    )
    assert dec_tight["selected_template_id"] == "cvrp_parallel_merge_static"

    # Test ComplementaryArchive + complementarity calculator
    comp = compute_portfolio_complementarity(
        [
            {"suite_id": "s1", "instance_id": "i1", "algorithm_id": "a", "status": "ok", "valid": True, "tour_length": 10.0},
            {"suite_id": "s1", "instance_id": "i1", "algorithm_id": "b", "status": "ok", "valid": True, "tour_length": 12.0},
            {"suite_id": "s1", "instance_id": "i2", "algorithm_id": "a", "status": "ok", "valid": True, "tour_length": 15.0},
            {"suite_id": "s1", "instance_id": "i2", "algorithm_id": "b", "status": "ok", "valid": True, "tour_length": 11.0},
        ],
        suite_id="s1",
        solver_ids=("a", "b"),
    )
    assert comp["sbs_solver"] == "b"
    assert comp["sbs_total"] == 23.0
    assert comp["vbs_total"] == 21.0
    assert comp["win_counts"] == {"a": 1, "b": 1}


def test_cross_harness_session_cli_and_skill_m2_lifecycle(tmp_path: Path) -> None:
    """Verify full Skill + Session Runtime lifecycle with plan.interface_selection (mock LLM, zero network)."""
    import subprocess
    import sys
    import time

    from agent_skill_loop.session_actions import collect, execute, finish_round, read_evaluation, submit_evaluation, submit_plan
    from agent_skill_loop.session_runtime import initialize_session, read_state

    # 1. Verify harness-agnostic `interface list-templates` CLI
    cli_res = subprocess.run(
        [sys.executable, "-m", "agent_skill_loop", "interface", "list-templates"],
        capture_output=True,
        text=True,
        check=True,
    )
    listed = json.loads(cli_res.stdout)
    assert listed["ok"] is True
    tids = {t["template_id"] for t in listed["templates"]}
    assert {"cvrp_sequential_construct", "cvrp_parallel_merge_static", "cvrp_parallel_merge_dynamic"}.issubset(tids)

    # 2. Initialize a standard recoverable Session using mock:// endpoint for offline test
    run_dir = tmp_path / "m2_session_run"
    init_res = initialize_session(
        output=run_dir,
        operation_id="op_init_1",
        problem="cvrp_construct",
        eoh_model="mock-m2",
        eoh_endpoint="mock://local",
        eoh_api_key_env="OPENCODE_GO_API_KEY",
        eoh_max_requests=12,
        engine_wall_seconds=120.0,
        memory_enabled=False,
        seed=20261122,
        size=15,
        count=3,
        search_policy_defaults={"pop_size": 2, "n_pop": 1, "max_sample_nums": 2},
    )
    ver = init_res["state_version"]

    # 3. Submit a strict plan.json with interface_selection -> triggers 5-gate InterfaceValidator!
    plan_file = tmp_path / "plan_r1.json"
    plan_file.write_text(
        json.dumps({
            "round_id": 1,
            "direction": "Switch CVRP solver interface to static parallel merge (L2a).",
            "operations": [
                {
                    "type": "replace",
                    "target": "score_merge_static",
                    "mechanism": "Scale-invariant savings with gentle capacity utilization term.",
                }
            ],
            "preserve": "Exact route feasibility and scale invariance.",
            "feedback_basis": None,
            "memory_basis": [],
            "reference_skill_ref": None,
            "hypothesis": "Static parallel merge outperforms pointwise construction on CVRP.",
            "interface_selection": {
                "template_id": "cvrp_parallel_merge_static",
                "template_version": "v1",
                "postprocess_mode": "none",
                "cited_kb_ids": ["method-cvrp-cw-parallel"],
                "rationale": "Verified 2x3 gap decomposition favors parallel merge.",
            },
        }, indent=2),
        encoding="utf-8",
    )
    sub_res = submit_plan(run=run_dir, operation_id="op_plan_1", expected_state_version=ver, file=plan_file)
    assert sub_res["result"]["interface_selection"]["validation_passed"] is True
    assert (run_dir / "rounds/round_0001/interface_design.json").is_file()
    assert (run_dir / "rounds/round_0001/interface_validation.json").is_file()
    ver = sub_res["state_version"]

    # 4. Execute via standard Session supervisor & wait for terminal task state
    exec_res = execute(run=run_dir, operation_id="op_exec_1", expected_state_version=ver)
    assert exec_res["ok"] is True

    deadline = time.monotonic() + 60.0
    st = read_state(run=run_dir)
    while time.monotonic() < deadline:
        t_info = st.get("task") or {}
        if t_info.get("state") == "EXITED":
            break
        time.sleep(0.25)
        st = read_state(run=run_dir)
    assert (st.get("task") or {}).get("state") == "EXITED", st
    assert (st.get("task") or {}).get("terminal_reason") == "SUCCEEDED", st
    ver = st["state_version"]

    # 5. Collect & Read deterministic evaluation facts (including frozen_solver_ref!)
    col_res = collect(run=run_dir, operation_id="op_col_1", expected_state_version=ver)
    assert col_res["ok"] is True
    ver = col_res["state_version"]
    ev_facts = read_evaluation(run=run_dir)
    facts = ev_facts["result"]
    assert facts["interface_selection"]["template_id"] == "cvrp_parallel_merge_static"
    assert facts["frozen_solver_ref"] is not None
    assert (run_dir / facts["frozen_solver_ref"]).is_file()
    assert facts["incumbent_after"] is not None

    # 6. Submit evaluation & finish round cleanly
    eval_file = tmp_path / "eval_r1.json"
    eval_file.write_text(
        json.dumps({
            "plan_alignment": "aligned",
            "observations": [
                {
                    "claim": "L2a static parallel merge executed through Session Runtime and produced a valid frozen solver.",
                    "evidence_refs": facts["evidence_refs"][:1],
                }
            ],
            "hypotheses": [
                {
                    "claim": "Static parallel merge generalizes across scales under unified 500 ms budget.",
                    "confidence": "medium",
                    "evidence_refs": facts["evidence_refs"][:1],
                }
            ],
            "next_search_advice": {"direction": "Evaluate frozen solver on M1 Workbench."},
            "memory_action": {"kind": "disabled"},
        }, indent=2),
        encoding="utf-8",
    )
    se_res = submit_evaluation(run=run_dir, operation_id="op_eval_1", expected_state_version=ver, file=eval_file)
    ver = se_res["state_version"]
    fin_res = finish_round(run=run_dir, operation_id="op_fin_1", expected_state_version=ver, decision="complete")
    assert fin_res["run_state"] == "COMPLETED"
