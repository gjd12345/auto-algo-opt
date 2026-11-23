"""Milestone 3 Phase 3C & Phase 3D tests:
- Holm-Bonferroni adjustment and per-seed paired statistical methodology
- Phase 3C 4-arm x 3-seed fair hard budget (B_total=36) ledger & zero isolation leaks (500ms & 25ms)
- Pre-blind protocol freeze & one-shot cvrp_m3_blind_120 verification (120/120 SHA-256, zero coordinate leakage)
- Section 5.3 Backbone & Anytime trajectory (evolved L3 vs L3-ctrl on blind_120)
- External top-venue & OR gold standards (EoH-S 256, CVRPLib A/B/P 74 dual exact-k, Set X 100 tiers)
- Direction-2 dual denominators & immutable release 20261123-main-co-workbench-m3
"""

from __future__ import annotations

import json
from pathlib import Path

from agent_skill_loop.interface_design.blind_eval_m3 import (
    M3_EXTRA_L3_SOLVER_ID,
    holm_bonferroni_adjust,
)
from knowledge_tools.core import read_entry, resolve_release, validate_release, validate_workspace

REPO = Path(__file__).resolve().parents[1]
PHASE3C_DIR = REPO / "experiments" / "milestone3" / "phase3c_four_arm"
PHASE3D_DIR = REPO / "experiments" / "milestone3" / "phase3d_blind_eval"


def test_holm_bonferroni_adjustment() -> None:
    adj = holm_bonferroni_adjust([0.04, 0.005, 0.02, 0.25])
    # Ordered: 0.005 (*4=0.02), 0.02 (*3=0.06), 0.04 (*2=0.08), 0.25 (*1=0.25)
    assert adj == [0.08, 0.02, 0.06, 0.25]


def test_phase3c_four_arm_reports_and_budget_invariants() -> None:
    for bid in ("standard_500ms", "tight_25ms"):
        rep_path = PHASE3C_DIR / f"phase3c_report_{bid}.json"
        assert rep_path.is_file()
        rep = json.loads(rep_path.read_text(encoding="utf-8"))
        assert len(rep["runs"]) == 12
        for run in rep["runs"]:
            assert int(run["attempted_requests"]) <= 36
            assert int(run["rejected_requests"]) >= 0
            assert float(run["select_64_completion_rate"]) == 1.0
        arm_sum = rep["arm_summary"]
        assert arm_sum["arm_m3_2_fixed_l2a"]["select_64_mean_avg"] < arm_sum["arm_m3_0_pure_eoh"]["select_64_mean_avg"]
        assert arm_sum["arm_m3_3_full_dynamic"]["select_64_mean_avg"] < arm_sum["arm_m3_1_plain_text"]["select_64_mean_avg"]

    # Every run summary passes zero-leak & <=36 budget invariants
    for summary_path in sorted(PHASE3C_DIR.glob("*_*/seed_*/arm_*/research_summary.json")):
        summ = json.loads(summary_path.read_text(encoding="utf-8"))
        assert summ["budget_summary"]["attempted_requests"] <= 36
        assert summ["budget_summary"]["remaining"] >= 0
        assert summ["budget_summary"]["rejected_requests"] >= 0


def test_phase3d_pre_blind_protocol_and_blind120_report() -> None:
    proto_path = PHASE3D_DIR / "pre_blind_protocol_m3.json"
    report_path = PHASE3D_DIR / "blind_120_evaluation_report.json"
    ext_path = PHASE3D_DIR / "external_benchmarks_report.json"
    bb_path = PHASE3D_DIR / "backbone_blind120_report.json"
    d2_path = PHASE3D_DIR / "direction2_cross_paradigm_report.json"

    for p in (proto_path, report_path, ext_path, bb_path, d2_path):
        assert p.is_file(), f"missing:{p}"
        txt = p.read_text(encoding="utf-8")
        assert "customer_coordinates" not in txt
        assert "sealed_seed_token" not in txt

    proto = json.loads(proto_path.read_text(encoding="utf-8"))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    ext = json.loads(ext_path.read_text(encoding="utf-8"))
    bb = json.loads(bb_path.read_text(encoding="utf-8"))
    d2 = json.loads(d2_path.read_text(encoding="utf-8"))

    # 1. Commitment match & blind verification
    assert report["commitment_verification"]["ok"] is True
    assert report["commitment_verification"]["verified_instances"] == 120
    assert (
        report["commitment_verification"]["suite_content_sha256"]
        == proto["blind_commitment"]["suite_content_sha256"]
    )

    # 2. Multi-seed consistency & per-seed Holm-Bonferroni tests
    a500 = report["blind_120_standard_500ms_arm_summary"]
    assert a500["arm_m3_2_fixed_l2a"]["std_across_seeds"] < 0.1
    assert a500["arm_m3_3_full_dynamic"]["std_across_seeds"] < 0.1
    assert a500["arm_m3_3_full_dynamic"]["mean_across_seeds"] < a500["arm_m3_1_plain_text"]["mean_across_seeds"]

    a25 = report["blind_120_tight_25ms_arm_summary"]
    for arm_id in ("arm_m3_2_fixed_l2a", "arm_m3_3_full_dynamic"):
        for s_row in a25[arm_id]["per_seed"].values():
            assert s_row["completion_rate"] == 1.0
            assert s_row["ok_budget_exhausted_count"] == 0

    h500 = report["hypothesis_tests_blind_120_500ms"]
    for seed in (20261124, 20261125, 20261126):
        k = f"s{seed}__m3_3_vs_c1_tworegime"
        assert h500[k]["rel_gain_vs_baseline_pct"] > 5.0
        assert h500[k]["p_holm_wilcoxon"] < 0.01

    # 3. Backbone anytime trajectory & evolved L3 vs L3-ctrl on blind_120
    l3_evo = bb["solvers"][M3_EXTRA_L3_SOLVER_ID]
    l3_ctrl = bb["solvers"]["m3_l3_ctrl_500ms"]
    assert l3_evo["overall"]["mean_tour_length"] < l3_ctrl["overall"]["mean_tour_length"]
    assert bb["paired_tests"]["backbone__r2_l3_evolved_vs_l3_ctrl_500ms"]["p_holm_wilcoxon"] < 0.01
    curve = l3_evo["anytime"]["anytime_curve_means"]
    assert float(curve["500"]) <= float(curve["100"]) <= float(curve["10"])

    # 4. External benchmarks (EoH-S 256, CVRPLib A/B/P 74 exact-k, Set X 100 tiers)
    es = ext["suites"]
    eohs_best = es["cvrp_ext_eohs_256"]["algorithms"]["m3_3c_standard_500ms_arm_m3_3_full_dynamic_s20261126"]["overall"]
    assert eohs_best["ok_count"] == 256
    assert eohs_best["mean_rel_gap"] < es["cvrp_ext_eohs_256"]["algorithms"]["cw_relocate_2opt"]["overall"]["mean_rel_gap"]

    abp_best = es["cvrp_ext_cvrplib_abp_74"]["algorithms"]["m3_3c_standard_500ms_arm_m3_2_fixed_l2a_s20261126"]["overall"]
    assert abp_best["ok_count"] == 74
    assert abp_best["exact_k_checked"] == 74 and abp_best["exact_k_mean_rel_gap"] is not None
    assert abp_best["mean_rel_gap"] < es["cvrp_ext_cvrplib_abp_74"]["algorithms"]["cw_relocate_2opt"]["overall"]["mean_rel_gap"]

    x_best = es["cvrp_ext_cvrplib_x_100"]["algorithms"]["m3_3c_standard_500ms_arm_m3_3_full_dynamic_s20261126"]
    assert x_best["overall"]["ok_count"] == 100
    assert set(x_best["by_x_tier"].keys()) == {"X-S (100-250)", "X-M (251-500)", "X-L (501-1000)"}
    assert x_best["overall"]["mean_rel_gap"] < es["cvrp_ext_cvrplib_x_100"]["algorithms"]["cw_relocate_2opt"]["overall"]["mean_rel_gap"]

    # 5. Direction-2 dual denominators & cross-paradigm oracle progression
    ov = d2["overview"]
    m3_hy = ov["m3_blind_120__m3_full_hybrid_pool_frozen"]
    assert "gap_over_sbs_pct" in m3_hy and "gap_over_vbs_pct" in m3_hy
    assert m3_hy["gap_over_vbs_pct"] >= m3_hy["gap_over_sbs_pct"]
    assert m3_hy["vbs_total"] < m3_hy["sbs_total"]


def test_phase3d_kb_cards_and_m3_release_integrity() -> None:
    ws = validate_workspace(REPO / "knowledge_workspace")
    assert ws["ok"] is True, ws["errors"][:10]

    for rel_name in (
        "20260914-main-d6433549-kb-v0",
        "20261121-main-audit-kb-v1",
        "20261122-main-co-workbench-final",
        "20261122-main-co-workbench-m15",
        "20261123-main-co-workbench-m2",
        "20261123-main-co-workbench-m3",
    ):
        chk = validate_release(REPO / "knowledge_store" / "releases" / rel_name)
        assert chk["ok"] is True, f"{rel_name}: {chk['errors'][:10]}"

    cur_dir = resolve_release(REPO / "knowledge_store" / "current")
    assert cur_dir.name == "20261123-main-co-workbench-m3"

    for cid in (
        "method-cvrp-m3-ruin-recreate-l3",
        "method-research-agent-m3-autonomous-loop",
        "evidence-cvrp-m3-four-arm-multiseed-500ms-25ms",
        "evidence-cvrp-m3-blind120-and-direction2",
        "evidence-cvrp-m3-external-eohs256-cvrplib-abp74-x100",
    ):
        entry = read_entry(cur_dir, cid)
        assert entry["id"] == cid

    blind_suite_txt = (cur_dir / "suites" / "cvrp_m3_blind_120.json").read_text(encoding="utf-8")
    assert "customer_coordinates" not in blind_suite_txt
    assert "sealed_seed_token" not in blind_suite_txt
