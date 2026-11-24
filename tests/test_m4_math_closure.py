from __future__ import annotations

from agent_skill_loop.benchmark.catalog import load_profile_suite
from agent_skill_loop.cvrp_workbench.suites import BENCHMARK_ID
from tools.run_m4_math_closure import (
    compute_exact_shapley,
    compute_hrk_radial_lower_bound,
    run_group_invariance_and_alpha,
    run_shapley_r5,
)


def test_exact_shapley_efficiency_identity_and_r5_parity() -> None:
    toy = {
        tuple((b >> i) & 1 for i in range(5)): float(sum((b >> i) & 1 for i in range(5)) * 2.0)
        for b in range(32)
    }
    res = compute_exact_shapley(toy)
    assert res["efficiency_identity_exact"] is True
    for k, v in res["shapley_values"].items():
        assert abs(v - 2.0) < 1e-9, k

    sh = run_shapley_r5(suites=(("cvrp_select_multiscale_64", "selection"),))
    s64 = sh["cvrp_select_multiscale_64"]
    assert s64["bit_for_bit_11111_max_diff"] == 0.0
    assert s64["shapley_tour_units"]["efficiency_identity_exact"] is True
    assert s64["shapley_pct_vs_cw_exog"]["efficiency_identity_exact"] is True
    assert len(s64["all_32_coalitions"]) == 32


def test_hrk_lower_bound_and_group_invariance_and_alpha_flip() -> None:
    grp = run_group_invariance_and_alpha()
    sim = grp["similarity_and_e2_invariance"]
    assert sim["cvrp_r5_max_scale_rel_drift"] <= 1e-6
    assert sim["cvrp_r5_max_e2_rel_drift"] <= 1e-6
    assert sim["tsp_max_scale_rel_drift"] <= 1e-6
    assert sim["tsp_max_e2_rel_drift"] <= 1e-6
    assert sim["obp_max_scale_abs_bins_drift"] == 0.0
    assert grp["alpha_equals_1_bifurcation_sweep"]["1.0"]["depot_start_identical_tie_at_1"] is True
    assert grp["alpha_equals_1_bifurcation_sweep"]["1.0"]["instance_count"] == 64
    assert grp["alpha_equals_1_bifurcation_sweep"]["1.0"]["depot_start_tied_instance_count"] == 64
    assert grp["alpha_equals_1_bifurcation_sweep_dev24"]["1.0"]["instance_count"] == 24
    assert grp["alpha_equals_1_bifurcation_sweep"]["0.99"]["mean_tour_length"] > grp["alpha_equals_1_bifurcation_sweep"]["1.01"]["mean_tour_length"]
    assert grp["alpha_equals_1_bifurcation_sweep"]["0.99"]["mean_empty_return_share_pct"] > grp["alpha_equals_1_bifurcation_sweep"]["1.01"]["mean_empty_return_share_pct"] > 0.0

    abp = load_profile_suite(BENCHMARK_ID, "cvrp_ext_cvrplib_abp_74", split="heldout")
    for inst in abp["instances"]:
        lb = compute_hrk_radial_lower_bound(inst, abp["distance_convention"])
        assert lb <= float(inst["reference_objective"]) + 1e-6


def test_m4_part1_cli_and_markdown_parity(tmp_path: Path) -> None:
    from pathlib import Path
    from tools.run_m4_math_closure import main as m4_main

    out_dir = tmp_path / "m4_out"
    assert m4_main(["--output-dir", str(out_dir), "full-part1"]) == 0
    md_text = (out_dir / "m4_math_closure_part1.md").read_text(encoding="utf-8")
    assert "Single-Step Sequential Pool" in md_text
    assert "Constructive Pool" in md_text
    assert "Full Pool (Constructive + 2-opt/Relocate)" in md_text
    assert "corr(eta_geom, raw_gap)" in md_text
    assert "Top Order-2 Shapley Synergy" in md_text
    assert "F1_depot_two_phase_override__x__F2_adaptive_inward_spiral_alpha" in md_text
    assert "cvrp_ext_cvrplib_abp_74" in md_text
    assert "Bifurcation Sweep (`cvrp_select_multiscale_64`, full N=64 multi-scale)" in md_text


def test_validator_evolved_hook_n200_latency_and_ast_hints() -> None:
    from agent_skill_loop.interface_design.contracts import InterfaceDesign
    from agent_skill_loop.interface_design.runtime import validate_hook_ast
    from agent_skill_loop.interface_design.templates import get_template_spec
    from agent_skill_loop.interface_design.validator import InterfaceValidator

    g1, _ = validate_hook_ast(
        "import numpy as np\ndef select_next_city(current_node, unvisited_nodes, distance_matrix):\n    sub = distance_matrix[np.ix_(unvisited_nodes, unvisited_nodes)]\n    np.fill_diagonal(sub, np.inf)\n    return -distance_matrix[current_node, unvisited_nodes]\n",
        hook_name="select_next_city",
        expected_args=("current_node", "unvisited_nodes", "distance_matrix"),
    )
    hints = {f.symbol: f.fix_hint for f in g1}
    assert "broadcast indexing" in hints["np.ix_"]
    assert "np.where(np.eye" in hints["np.fill_diagonal"]

    tpl = get_template_spec("cvrp_parallel_merge_static", "v1")
    design = InterfaceDesign(
        design_id="test_n200_probe",
        problem_family="cvrp",
        paradigm=tpl.paradigm,
        template_id=tpl.template_id,
        template_version=tpl.template_version,
        postprocess_mode="none",
        hook_name=tpl.hook_name,
        hook_signature=tpl.hook_signature,
        hook_task_description=tpl.default_task_description,
        baseline_hook_code=tpl.default_baseline_hook_code,
    )
    res = InterfaceValidator(instance_time_budget_ms=500.0).validate_evolved_hook_n200_latency(
        design,
        hook_code_override=tpl.default_baseline_hook_code,
    )
    assert res["passed"] is True
    assert res["n_instances"] == 2
    assert res["timeout_count"] == 0
