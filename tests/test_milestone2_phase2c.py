"""Milestone 2 Phase 2C tests:
- Pre-blind protocol freeze & SHA-256 commitment verification
- One-shot cvrp_m2_blind_120 evaluation (500ms & 25ms Protocol T1 vs T2) & zero raw coordinate leakage
- Paired Wilcoxon signed-rank & 10,000-draw Bootstrap 95% CIs
- Direction-2 cross-paradigm selection portfolios with dual denominators (SBS-VBS)/SBS and (SBS-VBS)/VBS
- Milestone 2 knowledge cards & immutable release 20261123-main-co-workbench-m2
"""

from __future__ import annotations

import json
from pathlib import Path

from agent_skill_loop.interface_design.blind_eval import (
    paired_bootstrap_comparison,
    paired_wilcoxon_signed_rank,
)
from knowledge_tools.core import read_entry, resolve_release, validate_release, validate_workspace

REPO = Path(__file__).resolve().parents[1]
PHASE2C_DIR = REPO / "experiments" / "milestone2" / "phase2c_blind_eval"


def test_paired_wilcoxon_and_bootstrap_statistics() -> None:
    cand = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0]
    base = [12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0]
    w = paired_wilcoxon_signed_rank(cand, base)
    assert w["n_pairs"] == 8
    assert w["n_nonzero"] == 8
    assert w["w_plus"] == 0.0
    assert w["w_minus"] == 36.0
    assert w["p_two_sided"] < 0.05

    b = paired_bootstrap_comparison(cand, base, n_boot=2000, seed=42)
    assert b["wtl_candidate_vs_baseline"] == {"wins": 8, "ties": 0, "losses": 0}
    assert b["rel_gain_vs_baseline_pct"] > 0.0
    assert b["rel_gain_ci95_pct"][0] > 0.0


def test_phase2c_pre_blind_protocol_and_blind120_report() -> None:
    proto_path = PHASE2C_DIR / "pre_blind_protocol.json"
    report_path = PHASE2C_DIR / "blind_120_evaluation_report.json"
    d2_path = PHASE2C_DIR / "direction2_cross_paradigm_report.json"

    assert proto_path.is_file()
    assert report_path.is_file()
    assert d2_path.is_file()

    proto = json.loads(proto_path.read_text(encoding="utf-8"))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    d2 = json.loads(d2_path.read_text(encoding="utf-8"))

    # 1. Verify commitment match & zero coordinate leakage in tracked files
    assert report["commitment_verification"]["ok"] is True
    assert report["commitment_verification"]["verified_instances"] == 120
    assert (
        report["commitment_verification"]["suite_content_sha256"]
        == proto["blind_commitment"]["suite_content_sha256"]
    )
    for tracked_file in (proto_path, report_path, d2_path):
        raw_txt = tracked_file.read_text(encoding="utf-8")
        assert "customer_coordinates" not in raw_txt
        assert "sealed_seed_token" not in raw_txt

    # 2. Verify 500ms 5-arm blind-120 ranking & H1/H2/H3 significance
    arms_500 = report["blind_120_standard_500ms_arm_summary"]
    assert arms_500["llm_diagnostic_planner"]["paired_mean_avg"] < arms_500["fixed_pointwise"]["paired_mean_avg"]
    assert arms_500["llm_diagnostic_planner"]["paired_mean_avg"] < arms_500["diagnostic_rule_planner"]["paired_mean_avg"]

    ht = report["hypothesis_tests_blind_120"]
    assert ht["H1_llm_planner_vs_fixed_pointwise_500ms_paired_avg"]["wtl_candidate_vs_baseline"]["wins"] == 120
    assert ht["H2_llm_planner_s20261123_vs_c1_tworegime_500ms"]["wtl_candidate_vs_baseline"]["wins"] == 119
    assert ht["H3_llm_planner_vs_rule_planner_500ms_paired_avg"]["wilcoxon_signed_rank"]["p_two_sided"] < 0.01
    assert ht["H5b_l2b_ctrl_vs_bare_cw_at_500ms_exact_equivalence"]["wtl_candidate_vs_baseline"]["ties"] == 120

    # 3. Verify 25ms Protocol T1 vs Protocol T2 budget adaptation on blind-120
    s25 = report["blind_120_tight_25ms_summary"]
    assert s25["m2_2b_tight_25ms_diagnostic_rule_planner_s20261122"]["ok_budget_exhausted_count"] == 0
    assert s25["m2_2b_tight_25ms_llm_diagnostic_planner_s20261122"]["ok_budget_exhausted_count"] == 0
    assert s25["m2_2b_standard_500ms_diagnostic_rule_planner_s20261122"]["ok_budget_exhausted_count"] == 40
    assert ht["H4a_protocol_t1_rule_25ms_vs_t2_rule_500ms_at_25ms"]["rel_gain_vs_baseline_pct"] > 50.0

    # 4. Verify Direction-2 dual denominators & cross-paradigm progression
    ov = d2["overview"]
    pw_bl = ov["m2_blind_120__m15_pointwise_pool_frozen"]
    ev_bl = ov["m2_blind_120__m2_evolved_cross_paradigm_pool_frozen"]
    hy_bl = ov["m2_blind_120__m2_full_hybrid_pool_frozen"]
    for item in (pw_bl, ev_bl, hy_bl):
        assert "gap_over_sbs_pct" in item and "gap_over_vbs_pct" in item
        assert item["gap_over_vbs_pct"] >= item["gap_over_sbs_pct"]
    assert ev_bl["sbs_total"] < pw_bl["vbs_total"]
    assert hy_bl["vbs_total"] < hy_bl["sbs_total"]


def test_phase2c_kb_cards_and_m2_release_integrity() -> None:
    ws = validate_workspace(REPO / "knowledge_workspace")
    assert ws["ok"] is True, ws["errors"][:10]

    # Verify all 4 historical releases + new M2 release are valid
    for rel_name in (
        "20260914-main-d6433549-kb-v0",
        "20261121-main-audit-kb-v1",
        "20261122-main-co-workbench-final",
        "20261122-main-co-workbench-m15",
        "20261123-main-co-workbench-m2",
    ):
        chk = validate_release(REPO / "knowledge_store" / "releases" / rel_name)
        assert chk["ok"] is True, f"{rel_name}: {chk['errors'][:10]}"

    cur_dir = resolve_release(REPO / "knowledge_store" / "current")
    assert cur_dir.name == "20261123-main-co-workbench-m2"

    m2_card_ids = (
        "method-cvrp-m2-l2a-generalized-savings",
        "method-cvrp-m2-l2b-dynamic-state-merge",
        "evidence-cvrp-m2-perpair-scale-normalization-antipattern",
        "evidence-cvrp-m2-diagnostic-planning-and-budget-adaptation",
        "evidence-cvrp-m2-cross-paradigm-blind120-and-selection",
    )
    for cid in m2_card_ids:
        entry = read_entry(cur_dir, cid)
        assert entry["id"] == cid

    # Ensure redacted cvrp_m2_blind_120 suite in release contains zero raw coordinates/demands/seeds
    blind_suite_txt = (cur_dir / "suites" / "cvrp_m2_blind_120.json").read_text(encoding="utf-8")
    assert "customer_coordinates" not in blind_suite_txt
    assert "sealed_seed_token" not in blind_suite_txt
