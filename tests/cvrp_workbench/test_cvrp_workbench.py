"""Comprehensive Milestone-1 Multi-Problem (CVRP/TSP/OBP) Workbench & Knowledge Base tests."""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
from pathlib import Path

import pytest

from agent_skill_loop import evaluator
from agent_skill_loop.benchmark import (
    ALLOWED_BENCHMARK_TIERS,
    ALLOWED_DISTANCE_CONVENTIONS,
    ALLOWED_EXPOSURE_STATUSES,
    ALLOWED_SUITE_ROLES,
    ALLOWED_VEHICLE_LIMIT_POLICIES,
    benchmark_profile,
    list_benchmark_profiles,
    load_benchmark_registry,
    load_profile_suite,
)
from agent_skill_loop.benchmark.harness import load_suite
from agent_skill_loop.cvrp_workbench import (
    OBP_SOLVER_CATALOG,
    REFERENCE_7_IDS,
    SOLVER_CATALOG,
    TSP_SOLVER_CATALOG,
    UPSTREAM_CVRP_IDS,
    compile_pointwise_rule,
    compute_distance_matrix,
    evaluate_algorithm_on_instance,
    evaluate_obp_algorithm_on_instance,
    evaluate_tsp_algorithm_on_instance,
    execute_pointwise_rule,
    verify_cvrp_solution,
    verify_obp_solution,
    verify_tsp_solution,
)
from agent_skill_loop.cvrp_workbench.published_results import validate_published_records
from agent_skill_loop.cvrp_workbench.runner import aggregate_records
from agent_skill_loop.cvrp_workbench.suites import (
    BENCHMARK_ID,
    EXPECTED_HETERO_288_RAW_SHA256,
    load_shared_diagnostic_6,
)
from knowledge_tools.core import (
    read_entry,
    search_release,
    validate_release,
    validate_workspace,
)

REPO = Path(__file__).resolve().parents[2]
WB_BENCHMARKS = REPO / "benchmarks" / "cvrp_workbench"


def test_legacy_benchmark_spec_content_hash_is_unchanged():
    """Extending BenchmarkSpec with optional v1.2/v1.3 fields must not alter legacy hashes."""
    bench, _metric, _item = benchmark_profile("eohs_v1", "obp_mini")
    d = bench.as_dict()
    for new_key in (
        "selection_manifest_hash",
        "suite_role",
        "exposure_status",
        "distance_convention",
        "vehicle_limit_policy",
        "problem_family",
        "benchmark_tier",
        "published_results_path",
        "published_results_hash",
    ):
        assert new_key not in d
    legacy = load_benchmark_registry()
    assert all(b["benchmark_id"] in {"eohs_v1", "island605_bp"} for b in legacy["benchmarks"])


def test_all_13_multi_problem_suites_register_and_verify_sha256():
    expected_profiles = {
        # Tier 1: Top-Venue Protocol
        "cvrp_ext_eohs_256": ("cvrp", "top_venue_protocol", "heldout", "external_top_venue", "public_standard", "euc_2d_float", 256),
        "cvrp_ext_reevo_scale": ("cvrp", "top_venue_protocol", "heldout", "external_top_venue", "public_standard", "euc_2d_float", 48),
        "tsp_ext_eohs_128": ("tsp", "top_venue_protocol", "heldout", "external_top_venue", "public_standard", "euc_2d_float", 128),
        "obp_ext_eoh_weibull": ("obp", "top_venue_protocol", "heldout", "external_top_venue", "public_standard", "not_applicable", 173),
        # Tier 2: OR Gold Standard
        "cvrp_ext_cvrplib_abp_74": ("cvrp", "or_gold_standard", "heldout", "external_or_standard", "public_standard", "euc_2d_nint", 74),
        "cvrp_ext_cvrplib_x_100": ("cvrp", "or_gold_standard", "heldout", "external_or_standard", "public_standard", "euc_2d_nint", 100),
        "tsp_ext_tsplib_euc2d": ("tsp", "or_gold_standard", "heldout", "external_or_standard", "public_standard", "euc_2d_nint", 18),
        "obp_ext_bpplib": ("obp", "or_gold_standard", "heldout", "external_or_standard", "public_standard", "not_applicable", 70),
        # Tier 3: Local Controlled CVRP
        "cvrp_dev_hetero_24": ("cvrp", "local_controlled", "dev_train", "dev_search", "fresh_isolated", "euc_2d_float", 24),
        "cvrp_select_multiscale_64": ("cvrp", "local_controlled", "selection", "selection_tuning", "fresh_isolated", "euc_2d_float", 64),
        "cvrp_hist_p0_120": ("cvrp", "local_controlled", "heldout", "historical_regression", "historically_exposed", "euc_2d_float", 120),
        "cvrp_hist_hetero_288": ("cvrp", "local_controlled", "heldout", "historical_regression", "historically_exposed", "euc_2d_float", 288),
        "cvrp_final_accept_120": ("cvrp", "local_controlled", "heldout", "final_acceptance", "fresh_isolated", "euc_2d_float", 120),
    }
    profiles = list_benchmark_profiles(include_extensions=True)
    wb_profiles = {p["profile"]: p for p in profiles if p["benchmark_id"] == BENCHMARK_ID}
    assert set(wb_profiles) == set(expected_profiles)

    for profile, (fam, tier, split, role, exposure, dist_conv, count) in expected_profiles.items():
        bench, _metric, item = benchmark_profile(BENCHMARK_ID, profile)
        assert bench.problem_family == fam
        assert bench.benchmark_tier == tier
        assert bench.benchmark_tier in ALLOWED_BENCHMARK_TIERS
        assert bench.suite_role == role
        assert bench.exposure_status == exposure
        assert bench.distance_convention == dist_conv

        suite = load_profile_suite(BENCHMARK_ID, profile, split=split)
        assert suite["problem_family"] == fam
        assert suite["benchmark_tier"] == tier
        assert suite["split"] == split
        assert len(suite["instances"]) == count

        manifest_path = WB_BENCHMARKS / item["manifest_paths"][split]
        raw = manifest_path.read_bytes()
        assert b"\r\n" not in raw
        assert hashlib.sha256(raw).hexdigest() == suite["data_manifest_hash"]

    sel_bench, _m, _i = benchmark_profile(BENCHMARK_ID, "cvrp_select_multiscale_64")
    assert sel_bench.selection_manifest_hash is not None
    assert sel_bench.selection_manifest_hash != sel_bench.train_manifest_hash
    assert sel_bench.selection_manifest_hash != sel_bench.test_manifest_hash
    sel_path = WB_BENCHMARKS / "manifests" / "cvrp_select_multiscale_64_selection.json"
    loaded_sel = load_suite(sel_path, benchmark_id=BENCHMARK_ID, profile="cvrp_select_multiscale_64", split="selection")
    assert loaded_sel["split"] == "selection" and len(loaded_sel["instances"]) == 64

    dev24 = load_profile_suite(BENCHMARK_ID, "cvrp_dev_hetero_24", split="dev_train")
    assert len(dev24["scale_stress_instances"]) == 4
    assert all(inst["coord_scale"] == 1e-3 for inst in dev24["scale_stress_instances"])

    h288 = load_profile_suite(BENCHMARK_ID, "cvrp_hist_hetero_288", split="heldout")
    assert h288["metadata"]["canonical_raw_instances_sha256"] == EXPECTED_HETERO_288_RAW_SHA256


def test_official_cvrplib_sol_and_tsplib_opt_zero_error_recomputation():
    """Verify strict 0.0 euc_2d_nint recomputation error on 100 Set X, 74 Set A/B/P, and 18 TSPLIB."""
    # 1. CVRPLib Set X: all 100 instances + 3 size tiers
    set_x = load_profile_suite(BENCHMARK_ID, "cvrp_ext_cvrplib_x_100", split="heldout")
    assert len(set_x["instances"]) == 100
    tier_counts: dict[str, int] = {}
    for inst in set_x["instances"]:
        tier_counts[inst["x_tier"]] = tier_counts.get(inst["x_tier"], 0) + 1
        ver = verify_cvrp_solution(inst, inst["bks_routes"], distance_convention="euc_2d_nint")
        assert ver["valid"] is True, f"Set X {inst['instance_id']} BKS invalid: {ver}"
        assert ver["tour_length"] == float(inst["bks_reported_cost"]), (
            f"Set X {inst['instance_id']}: {ver['tour_length']} != {inst['bks_reported_cost']}"
        )
        assert ver["tour_length"] == float(inst["reference_objective"])
    assert tier_counts == {"X-S (100-250)": 33, "X-M (251-500)": 35, "X-L (501-1000)": 32}

    # 2. CVRPLib Set A (27) + B (23) + P (24) = 74 instances
    abp = load_profile_suite(BENCHMARK_ID, "cvrp_ext_cvrplib_abp_74", split="heldout")
    assert len(abp["instances"]) == 74
    set_counts: dict[str, int] = {}
    for inst in abp["instances"]:
        set_counts[inst["cvrplib_set"]] = set_counts.get(inst["cvrplib_set"], 0) + 1
        dmat = compute_distance_matrix(
            inst["depot"],
            inst["customer_coordinates"],
            distance_convention="euc_2d_nint",
        )
        raw_route_cost = sum(
            float(dmat[r[k], r[k + 1]])
            for r in inst["bks_routes"]
            for k in range(len(r) - 1)
        )
        assert raw_route_cost == float(inst["bks_recomputed_nint_cost"])
        assert raw_route_cost == float(inst["reference_objective"])
        ver = verify_cvrp_solution(inst, inst["bks_routes"], distance_convention="euc_2d_nint")
        assert ver["valid"] is True, f"ABP {inst['instance_id']} BKS invalid: {ver}"
        assert ver["tour_length"] == float(inst["bks_recomputed_nint_cost"])
        assert ver["tour_length"] == float(inst["bks_reported_cost"]), (
            f"ABP {inst['instance_id']}: {ver['tour_length']} != {inst['bks_reported_cost']}"
        )
    assert set_counts == {"A": 27, "B": 23, "P": 24}
    abp_by_id = {inst["instance_id"]: inst for inst in abp["instances"]}
    assert abp_by_id["B-n50-k8"]["reference_objective"] == 1312.0
    assert abp_by_id["B-n57-k7"]["reference_objective"] == 1153.0

    # 3. TSPLIB EUC_2D: all 18 instances with official .opt.tour
    tsplib = load_profile_suite(BENCHMARK_ID, "tsp_ext_tsplib_euc2d", split="heldout")
    assert len(tsplib["instances"]) == 18
    for inst in tsplib["instances"]:
        ver = verify_tsp_solution(inst, inst["opt_tour"], distance_convention="euc_2d_nint")
        assert ver["valid"] is True, f"TSPLIB {inst['instance_id']} OPT invalid: {ver}"
        assert ver["tour_length"] == float(inst["reference_objective"]), (
            f"TSPLIB {inst['instance_id']}: {ver['tour_length']} != {inst['reference_objective']}"
        )


def test_published_results_schema_and_registry_hash_binding():
    """Validate published_results/*.json schema, hashes, dual-track markers, and primary-PDF digits."""
    pub_dir = WB_BENCHMARKS / "published_results"
    idx = json.loads((pub_dir / "index.json").read_text(encoding="utf-8"))
    recs = idx["records"]
    errs = validate_published_records(recs)
    assert errs == [], errs
    assert len(recs) >= 300
    for fname, finfo in idx["files"].items():
        fpath = pub_dir / fname
        assert fpath.is_file()
        assert hashlib.sha256(fpath.read_bytes()).hexdigest() == finfo["sha256"]

    # Verify registry.json binds exact SHA-256 of published_results files
    reg = json.loads((WB_BENCHMARKS / "registry.json").read_text(encoding="utf-8"))
    bound_count = 0
    for item in reg["benchmarks"]:
        p_rel = item.get("published_results_path")
        p_hash = item.get("published_results_hash")
        if p_rel is not None:
            p_path = WB_BENCHMARKS / p_rel
            assert p_path.is_file()
            assert hashlib.sha256(p_path.read_bytes()).hexdigest() == p_hash
            bound_count += 1
    assert bound_count >= 6
    assert all(r["comparison_mode"] == "paper_reported_reference" for r in recs)

    # Check primary-PDF verified digits & honest pending flag
    eoh_cobench = [r for r in recs if r["paper_source_id"] == "src-sun-2025-cobench" and r["method_id"] == "eoh"]
    assert len(eoh_cobench) == 1 and eoh_cobench[0]["value"] == 0.840
    assert eoh_cobench[0]["verification_status"] == "verified_from_paper_table"

    hx_cvrp = [r for r in recs if r["paper_source_id"] == "src-msra-2025-heuragenix" and r["subset"] == "CVRPLib_HeurAgenix_6" and r["method_id"] == "heuragenix"]
    assert len(hx_cvrp) == 1 and hx_cvrp[0]["value"] == 6.49

    reevo_cvrp_nco = {r["subset"]: r["value"] for r in recs if r["paper_source_id"] == "src-ye-2024-reevo" and r["method_id"] == "lehd_reevo" and r["problem_family"] == "cvrp" and r["metric_name"] == "mean_opt_gap_pct"}
    assert reevo_cvrp_nco == {"NCO_CVRP200": 3.30, "NCO_CVRP500": 2.94, "NCO_CVRP1000": 4.76}

    reevo_aco = [r for r in recs if r["paper_source_id"] == "src-ye-2024-reevo" and r["method_id"] == "aco_reevo"]
    assert len(reevo_aco) == 1
    assert reevo_aco[0]["value"] is None
    assert reevo_aco[0]["verification_status"] == "pending_pdf_or_repo_table_extraction"

    # Check EoH-S Table 1 all 9 columns (including 1k/C200 = 1.13% = 0.0113) & EoH FSSP Taillard 100x5=-0.04, 100x20=0.41
    eohs_t1 = {
        r["subset"]: r["value"]
        for r in recs
        if r["paper_source_id"] == "src-feiliu-2025-eohs"
        and r["table_ref"].startswith("Table 1 ")
        and r["method_id"] == "eoh_s_set10"
    }
    assert eohs_t1 == {
        "Train_n200_500_c100": 0.0515,
        "Train_n500_1k_c100": 0.0230,
        "Train_n1k_2k_c100": 0.0314,
        "n1k_c200": 0.0113,
        "n1k_c500": 0.0124,
        "n5k_c200": 0.0033,
        "n5k_c500": 0.0025,
        "n10k_c200": 0.0014,
        "n10k_c500": 0.0010,
    }
    eoh_fssp = {
        r["subset"]: r["value"]
        for r in recs
        if r["paper_source_id"] == "src-feiliu-2024-eoh" and r["problem_family"] == "fssp"
    }
    assert eoh_fssp["Taillard_100x5"] == -0.04
    assert eoh_fssp["Taillard_100x20"] == 0.41
    assert eoh_fssp["Taillard_200x10"] == 0.12
    assert eoh_fssp["Taillard_200x20"] == 0.61
    assert eoh_fssp["Taillard_Average"] == 0.23


def test_pointwise_adapter_matches_official_evaluator_zero_error_on_shared6():
    """Shared-6 alignment: 0.0 per-instance discrepancy vs evaluator.py, R5=10.2714 with 17 early returns."""
    sh6 = load_shared_diagnostic_6()
    for alg_id in ("nn", "savings_pointwise", "c", "s2_r5_spiral", "s2_r7_iso", "s2_ctrl_best"):
        spec = SOLVER_CATALOG[alg_id]
        fn = compile_pointwise_rule(spec.code_source, alg_id)
        raw_instances = [{k: v for k, v in inst.items() if k not in ("reference_objective", "reference_kind")} for inst in sh6]
        official_vals, _ = evaluator._evaluate_cvrp_instances(fn, raw_instances)

        adapter_vals = []
        total_early = 0
        for inst, off_val in zip(sh6, official_vals):
            res = execute_pointwise_rule(fn, inst, record_trace=True)
            assert res["valid"] is True and res["status"] == "ok"
            assert math.isclose(res["tour_length"], off_val, rel_tol=0.0, abs_tol=1e-12)
            adapter_vals.append(res["tour_length"])
            total_early += res["voluntary_early_return_count"]
            early_steps = [s for s in res["trace_steps"] if s["action_type"] == "voluntary_early_return"]
            assert len(early_steps) == res["voluntary_early_return_count"]

        if alg_id == "s2_r5_spiral":
            assert round(sum(adapter_vals) / len(adapter_vals), 4) == 10.2714
            assert total_early == 17
        if alg_id == "c":
            assert round(sum(adapter_vals) / len(adapter_vals), 4) == 10.9197


def test_full_route_verifier_catches_infeasibility_and_mutation():
    dev24 = load_profile_suite(BENCHMARK_ID, "cvrp_dev_hetero_24", split="dev_train")
    inst = dev24["instances"][0]
    res = evaluate_algorithm_on_instance("cw_relocate_2opt", inst)
    assert res["valid"] is True and res["status"] == "ok"

    bad_routes = [list(r) for r in res["routes"]]
    bad_routes[0][1] = bad_routes[0][2]
    assert verify_cvrp_solution(inst, bad_routes)["error_code"] == "invalid_route"

    merged_all = [[0, *range(1, len(inst["demands"]) + 1), 0]]
    assert verify_cvrp_solution(inst, merged_all)["error_code"] == "capacity_violation"

    inst_k1 = {**inst, "k_vehicles": 1}
    assert verify_cvrp_solution(inst_k1, res["routes"], vehicle_limit_policy="strict_max_vehicles")["error_code"] == "vehicle_limit_exceeded"

    def mutating_rule(cur, depot, nodes, rest_cap, demands, dmat):
        dmat[0, 1] = -999.0
        return int(nodes[0])

    assert execute_pointwise_rule(mutating_rule, inst)["error_code"] == "candidate_mutated_input"


def test_cvrp_tsp_obp_and_upstream_solvers_produce_valid_solutions():
    dev24 = load_profile_suite(BENCHMARK_ID, "cvrp_dev_hetero_24", split="dev_train")
    abp = load_profile_suite(BENCHMARK_ID, "cvrp_ext_cvrplib_abp_74", split="heldout")
    tsp_s = load_profile_suite(BENCHMARK_ID, "tsp_ext_tsplib_euc2d", split="heldout")
    obp_s = load_profile_suite(BENCHMARK_ID, "obp_ext_bpplib", split="heldout")

    inst_float = dev24["instances"][0]
    inst_nint = abp["instances"][0]
    costs_float = {}
    for alg_id in (*REFERENCE_7_IDS, *UPSTREAM_CVRP_IDS):
        r_f = evaluate_algorithm_on_instance(alg_id, inst_float, distance_convention="euc_2d_float", time_budget_ms=500.0)
        assert r_f["valid"] is True and r_f["status"] == "ok", f"{alg_id}: {r_f}"
        costs_float[alg_id] = r_f["tour_length"]

        r_n = evaluate_algorithm_on_instance(alg_id, inst_nint, distance_convention="euc_2d_nint", time_budget_ms=500.0)
        assert r_n["valid"] is True and r_n["status"] == "ok", f"{alg_id} nint: {r_n}"
        assert float(r_n["tour_length"]).is_integer()

    assert costs_float["cw_2opt"] <= costs_float["cw_parallel_merge"] + 1e-9
    assert costs_float["cw_relocate_2opt"] <= costs_float["cw_2opt"] + 1e-9

    # TSP solvers
    tsp_inst = tsp_s["instances"][0]  # eil51
    for alg_id in TSP_SOLVER_CATALOG:
        r_t = evaluate_tsp_algorithm_on_instance(alg_id, tsp_inst, distance_convention="euc_2d_nint", time_budget_ms=500.0)
        assert r_t["valid"] is True and r_t["status"] == "ok", f"TSP {alg_id}: {r_t}"
        assert float(r_t["tour_length"]).is_integer()

    # OBP solvers
    obp_inst = obp_s["instances"][0]
    for alg_id in OBP_SOLVER_CATALOG:
        r_o = evaluate_obp_algorithm_on_instance(alg_id, obp_inst, time_budget_ms=500.0)
        assert r_o["valid"] is True and r_o["status"] == "ok", f"OBP {alg_id}: {r_o}"
        assert r_o["bins_used"] >= int(obp_inst["l1_lower_bound"])


def test_knowledge_base_top_venue_cards_dual_track_and_release_integrity():
    """Verify KB workspace, 10 top-venue sources & cards, v0/v1/current releases, dashboard, filters & CLI parity."""
    ws = validate_workspace(REPO / "knowledge_workspace")
    assert ws["ok"] is True, ws["errors"][:10]

    # Verify all 10 required authoritative sources are registered
    sources_doc = json.loads((REPO / "knowledge_workspace" / "sources.json").read_text(encoding="utf-8"))
    source_ids = {s["id"] for s in sources_doc["sources"]}
    required_sources = {
        "src-romera-paredes-2024-funsearch",
        "src-feiliu-2024-eoh",
        "src-feiliu-2025-eohs",
        "src-ye-2024-reevo",
        "src-msra-2025-heuragenix",
        "src-sun-2025-cobench",
        "src-uchoa-2017-cvrplib-x",
        "src-augerat-1995-cvrplib-abp",
        "src-reinelt-1991-tsplib",
        "src-delorme-2018-bpplib",
    }
    assert required_sources.issubset(source_ids)

    # Validate immutable historic releases + current release
    for rel_name in ("20260914-main-d6433549-kb-v0", "20261121-main-audit-kb-v1"):
        check = validate_release(REPO / "knowledge_store" / "releases" / rel_name)
        assert check["ok"] is True, check["errors"][:10]

    cur = validate_release(REPO / "knowledge_store" / "current")
    assert cur["ok"] is True, cur["errors"][:10]
    cur_path = Path(cur["release"])

    # Verify Git symlink mode 120000 for knowledge_store/current
    git_ls = subprocess.check_output(["git", "ls-files", "-s", "knowledge_store/current"], cwd=str(REPO), text=True)
    assert git_ls.startswith("120000 "), f"Unexpected git mode: {git_ls}"

    # Verify offline self-contained dashboard & lazy suite bundles in release
    assert (cur_path / "dashboard.html").is_file()
    assert (cur_path / "workbench_data" / "core.js").is_file()
    assert (cur_path / "workbench_manifest.json").is_file()
    assert (cur_path / "published_results" / "index.json").is_file()

    # Verify all 10 required new top-venue cards & strict dual-track separation
    required_10_cards = (
        "evidence-bench-eohs-multi-problem-protocol",
        "evidence-bench-eoh-funsearch-obp-tsp-fssp",
        "evidence-bench-reevo-aco-gls-nco",
        "evidence-bench-heuragenix-and-cobench",
        "evidence-bench-cvrplib-abpx-standard",
        "method-lit-ahd-funsearch",
        "method-lit-ahd-eoh",
        "method-lit-ahd-eohs",
        "method-lit-ahd-reevo",
        "method-lit-ahd-heuragenix",
    )
    for cid in required_10_cards:
        entry = read_entry(cur_path, cid)
        attrs = entry["attributes"]
        assert attrs.get("paper_reported_results"), f"{cid} missing paper_reported_results"
        assert all(r["comparison_mode"] == "paper_reported_reference" for r in attrs["paper_reported_results"])
        for b in attrs.get("evidence_bindings", []):
            assert b.get("comparison_mode") == "local_recomputed"

    # Verify summary parity with per_instance_records across CVRP, TSP, and OBP
    records_doc = json.loads((cur_path / "results" / "per_instance_records.json").read_text(encoding="utf-8"))
    summary_doc = json.loads((cur_path / "results" / "summary.json").read_text(encoding="utf-8"))
    selection_doc = json.loads((cur_path / "results" / "selection_records.json").read_text(encoding="utf-8"))

    for sid, alg_id in (
        ("cvrp_dev_hetero_24", "s2_r5_spiral"),
        ("cvrp_final_accept_120", "cw_relocate_2opt"),
        ("cvrp_ext_cvrplib_abp_74", "cw_parallel_merge"),
        ("cvrp_ext_cvrplib_x_100", "s2_r5_spiral"),
        ("cvrp_ext_eohs_256", "eohs_cvrp_set10_cpi"),
        ("tsp_ext_tsplib_euc2d", "tsp_nn_2opt"),
        ("obp_ext_bpplib", "obp_best_fit"),
    ):
        sub = [r for r in records_doc["records"] if r["suite_id"] == sid and r["algorithm_id"] == alg_id]
        assert aggregate_records(sub) == summary_doc["suites"][sid]["algorithms"][alg_id]["overall"]

    # Set X 3-tier breakdown & common_completed (N_common=59) parity in summary
    set_x_sum = summary_doc["suites"]["cvrp_ext_cvrplib_x_100"]
    x_tiers = set_x_sum["algorithms"]["s2_r5_spiral"]["by_x_tier"]
    assert set(x_tiers) == {"X-S (100-250)", "X-M (251-500)", "X-L (501-1000)"}
    assert set_x_sum["common_completed_count"] == 59
    assert round(set_x_sum["algorithms"]["eohs_cvrp_f1"]["common_completed"]["mean_rel_gap"] * 100, 2) == 27.05
    assert round(set_x_sum["algorithms"]["s2_r5_spiral"]["common_completed"]["mean_rel_gap"] * 100, 2) == 16.36
    assert round(set_x_sum["algorithms"]["cw_relocate_2opt"]["common_completed"]["mean_rel_gap"] * 100, 2) == 5.69

    # EoH-S 256 budget_exhausted_count (49/256) & 18.39% CPI parity
    eohs_256_cpi = summary_doc["suites"]["cvrp_ext_eohs_256"]["algorithms"]["eohs_cvrp_set10_cpi"]["overall"]
    assert eohs_256_cpi["ok_count"] == 256 and eohs_256_cpi["budget_exhausted_count"] == 49
    assert round(eohs_256_cpi["mean_rel_gap"] * 100, 2) == 18.39

    # Verify Direction-2 mistake records exist and are drillable
    h288_p2 = selection_doc["analyses"]["hetero_288__pointwise_plus_s2"]
    assert set(h288_p2["protocols"]) == {"cv12", "loro48", "loso3"}
    rf_decisions = h288_p2["protocols"]["cv12"]["per_instance_decisions"]["rf_reg"]
    assert len(rf_decisions) == 288 and any(d["is_mistake_vs_oracle"] for d in rf_decisions)

    # Verify --paradigm / --tier / --variant / --comparison-mode filters
    ls_hits = search_release(cur_path, "2-opt", 10, problem_family="cvrp", paradigm="local_search", problem_variant="standard_cvrp")
    assert any(h["id"] == "method-cvrp-intra-2opt" for h in ls_hits["results"])

    vrptw_hits = search_release(cur_path, "Solomon", 10, problem_family="cvrp", problem_variant="vrptw")
    assert len(vrptw_hits["results"]) >= 2

    anti_hits = search_release(cur_path, "H-004a", 5, problem_family="cvrp", knowledge_tier="failure_antipattern")
    assert anti_hits["results"][0]["id"] == "evidence-cvrp-antipattern-falsified-hypotheses"

    paper_hits = search_release(cur_path, "EoH-S", 10, comparison_mode="paper_reported_reference")
    assert any(h["id"] == "evidence-bench-eohs-multi-problem-protocol" for h in paper_hits["results"])

    local_hits = search_release(cur_path, "R5", 10, comparison_mode="local_recomputed")
    assert any(h["id"] == "method-cvrp-s2-r5-spiral" for h in local_hits["results"])


def test_frontend_zero_broken_kb_links_js_syntax_and_bundle_parity(tmp_path: Path) -> None:
    import hashlib
    import re
    import shutil
    import subprocess
    from knowledge_tools.core import resolve_release

    repo = Path(__file__).resolve().parents[2]
    cur_dir = resolve_release(repo / "knowledge_store/current")
    index_doc = json.loads((cur_dir / "index.json").read_text(encoding="utf-8"))
    valid_ids = {e["id"] for e in index_doc["entries"]}
    assert len(valid_ids) == 324

    # 1. Zero broken KB entry links across all frontend/src/*.js modules
    id_re = re.compile(r"\b(?:method|evidence|problem|impl|finding)-[a-z0-9-]+\b")
    broken: list[tuple[str, str]] = []
    js_files = sorted((repo / "frontend/src").glob("*.js"))
    assert len(js_files) >= 8
    for js_path in js_files:
        text = js_path.read_text(encoding="utf-8")
        for m in id_re.finditer(text):
            if m.group(0) not in valid_ids:
                broken.append((js_path.name, m.group(0)))
    assert broken == [], f"Broken KB IDs referenced in frontend: {broken}"

    # 2. node --check on all frontend/src/*.js AND extracted inline script + core.js from current release
    if shutil.which("node"):
        for js_path in js_files:
            subprocess.run(["node", "--check", str(js_path)], check=True)
        html_text = (cur_dir / "dashboard.html").read_text(encoding="utf-8")
        scripts = re.findall(r"<script(?:\s+[^>]*)?>([\s\S]*?)</script>", html_text)
        inline_js = max(scripts, key=len)
        extracted = tmp_path / "extracted_dashboard_inline.js"
        extracted.write_text(inline_js, encoding="utf-8")
        subprocess.run(["node", "--check", str(extracted)], check=True)
        subprocess.run(["node", "--check", str(cur_dir / "workbench_data/core.js")], check=True)

    # 3. Zero-drift parity between benchmarks/cvrp_workbench/published_results & release
    bench_pub_idx = repo / "benchmarks/cvrp_workbench/published_results/index.json"
    rel_pub_idx = cur_dir / "published_results/index.json"
    assert hashlib.sha256(bench_pub_idx.read_bytes()).hexdigest() == hashlib.sha256(rel_pub_idx.read_bytes()).hexdigest()
    assert (cur_dir / "workbench_data/core.js").is_file()
    core_text = (cur_dir / "workbench_data/core.js").read_text(encoding="utf-8")
    assert '"kb_entries":' in core_text
    assert '"h003_preview":' in core_text
