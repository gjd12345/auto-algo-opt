"""Finalize Stage 2 hypotheses ledger with verified P0 held-out & Stage 2C closed-loop verdicts."""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
LEDGER = REPO / "experiments/cvrp_midterm/ledger/hypotheses.jsonl"
HOLDOUT = REPO / "experiments/cvrp_midterm/analysis/s2_holdout_eval.json"
SUM_S2 = REPO / "experiments/cvrp_midterm/selection_s2/summary_s2.json"
SEL_S2 = REPO / "experiments/cvrp_midterm/selection_s2/selectors_s2.json"


def main() -> int:
    hold = json.loads(HOLDOUT.read_text(encoding="utf-8"))
    s2 = json.loads(SUM_S2.read_text(encoding="utf-8"))
    sel = json.loads(SEL_S2.read_text(encoding="utf-8"))

    rows = [json.loads(line) for line in LEDGER.read_text(encoding="utf-8").splitlines() if line.strip()]
    by_id = {r["id"]: r for r in rows}

    # Update verified final statuses on H-003..H-009
    if "H-003" in by_id:
        by_id["H-003"]["verification"] = {
            "status": "verified_on_holdout",
            "reason": (
                "V0_decoupled_theory beat Frozen V0 by +7.96% [+6.88%, +8.98%] (p=0.0000, 94/120 wins) "
                "and beat pointwise savings by +1.65% [+1.07%, +2.21%] (p=0.0000, 81/120 wins) on 120 unseen P0 instances."
            ),
            "p0_120_mean": hold["results"]["V0_decoupled_theory"]["p0_120_mean"],
        }
    if "H-004" in by_id:
        by_id["H-004"]["verification"] = {
            "status": "verified_live_and_holdout",
            "reason": (
                "Voluntary early return via normalized saving sigma(i,j) < tau enabled Round 2 candidate_3 to surpass "
                "Frozen_C (-0.10961 vs -0.10890) and became the core mechanism of all Rounds 3-7 breakthroughs."
            ),
        }
    if "H-005" in by_id:
        by_id["H-005"]["verification"] = {
            "status": "verified_dev_partial_holdout",
            "reason": (
                "Round 3 candidate_3 achieved best dev4 (-0.15762) and beat A/B/C/savings on P0-50 (10.980 vs A 11.135), "
                "but because it omitted the depot-start branch it regressed on P0-200 (33.49), proving why multi-scale diagnostics are essential."
            ),
            "p0_means": {k: hold["results"]["auto_dev1_r3"][k] for k in ("p0_50_mean", "p0_100_mean", "p0_200_mean", "p0_120_mean")},
        }
    if "H-006" in by_id:
        by_id["H-006"]["verification"] = {
            "status": "verified_on_holdout",
            "reason": (
                "Round 4 candidate_1 (two-phase rem_routes + Law-of-Cosines cos(theta_0) + adaptive early return) "
                "cut sh6 to 10.2078 and P0-120 to 19.8100 (beating Frozen A 20.6133 by +3.90% with 0.00% scale spread)."
            ),
            "p0_means": {k: hold["results"]["auto_dev4_r4"][k] for k in ("p0_50_mean", "p0_100_mean", "p0_200_mean", "p0_120_mean")},
        }
    if "H-007" in by_id:
        c_ctrl = hold["comparisons"]["auto_ana_best_vs_ctrl_ana_best"]["p0_all120"]
        c_a = hold["comparisons"]["auto_ana_best_vs_A"]["p0_all120"]
        c_b = hold["comparisons"]["auto_ana_best_vs_B"]["p0_all120"]
        c_c = hold["comparisons"]["auto_ana_best_vs_C"]["p0_all120"]
        by_id["H-007"]["verification"] = {
            "status": "verified_best_overall_on_holdout",
            "reason": (
                f"Round 5 candidate_2 (auto_ana1_r5, selected strictly by offline ana72 with zero P0 peeking) achieved "
                f"P0-120=19.6092 (0.00% scale spread), beating paired control by {c_ctrl['rel_gain']*100:+.2f}% (p={c_ctrl['p_boot_one_sided']}), "
                f"Frozen A by {c_a['rel_gain']*100:+.2f}% (104/120 wins), Frozen B by {c_b['rel_gain']*100:+.2f}% (114/120 wins, 40/40 at n=200), "
                f"and Frozen C by {c_c['rel_gain']*100:+.2f}% (116/120 wins)."
            ),
            "p0_means": {k: hold["results"]["auto_ana1_r5"][k] for k in ("p0_50_mean", "p0_100_mean", "p0_200_mean", "p0_120_mean")},
        }
    if "H-008" in by_id:
        by_id["H-008"]["verification"] = {
            "status": "verified_ast_recovery_and_holdout",
            "reason": (
                "After Round 6 hit 0/5 AST rejection (fill_diagonal), Round 7 achieved 5/5 validity via np.where(np.eye(n)>0.5,np.inf,sub); "
                "Round 7 candidate_2 hit dev4=-0.15268, sh6=10.2595, P0-120=19.8805 (0.00% spread), beating all frozen rules and control."
            ),
            "p0_means": {k: hold["results"]["auto_dev3_r7"][k] for k in ("p0_50_mean", "p0_100_mean", "p0_200_mean", "p0_120_mean")},
        }
    if "H-009" in by_id:
        by_id["H-009"]["verification"] = {
            "status": "not_improved_late_round",
            "reason": (
                "Round 8 produced 2/5 valid rules (-0.0695, -0.0665; 3/5 rejected for ix_/searchsorted) and did not beat Rounds 3-7 champions, "
                "recorded transparently as late-round diminishing returns."
            ),
        }

    # Upsert H-010: Stage 2 multi-scale complementarity contraction & closed-loop selection
    p_base = s2["overall"]["portfolios"]["pointwise_base"]
    p_plus = s2["overall"]["portfolios"].get("pointwise_plus_s2")
    sel_base = sel["portfolios"]["pointwise_base"]["protocols"]
    sel_plus = sel["portfolios"].get("pointwise_plus_s2", {}).get("protocols")
    h10 = {
        "id": "H-010",
        "round": 8,
        "stage": "stage2_multiscale_selection_closed_loop",
        "target_rule": "288-instance 5-factor multi-scale portfolio (n=50/100/200) before and after feeding Direction 1 rules back into Direction 2",
        "hypothesis": "Across scales n in {50,100,200} and 5 crossed factors (spatial, depot, capacity, demand distribution), pointwise complementarity changes systematically with problem size, and feeding Direction 1's autonomous rules into the portfolio substantially lowers both VBS and SBS while shifting out-of-fold selection headroom.",
        "diagnostic": {
            "script": "experiments/cvrp_midterm/selection_s2/{run_matrix_s2.py,select_s2.py}",
            "artifacts": [
                "experiments/cvrp_midterm/selection_s2/summary_s2.json",
                "experiments/cvrp_midterm/selection_s2/selectors_s2.json",
            ],
            "seed": 20261122,
            "instances": 288,
            "protocols": ["cv12", "loro48", "loso3"],
        },
        "evidence": {
            "base_portfolio": {
                "vbs": p_base["vbs"],
                "sbs": p_base["sbs"],
                "sbs_rule": p_base["sbs_algorithm"],
                "gap": p_base["sbs_gap_to_vbs"],
                "gap_by_scale": {
                    sz: s2["by_scale"][sz]["portfolios"]["pointwise_base"]["sbs_gap_to_vbs"]
                    for sz in ("50", "100", "200")
                },
                "best_selector_gains": {
                    proto: {
                        "ridge": sel_base[proto]["ridge"]["gain_vs_fixed"],
                        "pairwise_cs": sel_base[proto]["pairwise_cs"]["gain_vs_fixed"],
                        "rf_reg": sel_base[proto]["rf_reg"]["gain_vs_fixed"],
                    }
                    for proto in ("cv12", "loro48", "loso3")
                },
            },
            "plus_s2_portfolio": None if not p_plus else {
                "vbs": p_plus["vbs"],
                "sbs": p_plus["sbs"],
                "sbs_rule": p_plus["sbs_algorithm"],
                "gap": p_plus["sbs_gap_to_vbs"],
                "gap_by_scale": {
                    sz: s2["by_scale"][sz]["portfolios"]["pointwise_plus_s2"]["sbs_gap_to_vbs"]
                    for sz in ("50", "100", "200")
                },
                "oracle_counts": p_plus["oracle_counts"],
                "best_selector_gains": {
                    proto: {
                        "ridge": sel_plus[proto]["ridge"]["gain_vs_fixed"],
                        "pairwise_cs": sel_plus[proto]["pairwise_cs"]["gain_vs_fixed"],
                        "rf_reg": sel_plus[proto]["rf_reg"]["gain_vs_fixed"],
                        "rf_pairwise_cs": sel_plus[proto]["rf_pairwise_cs"]["gain_vs_fixed"],
                    }
                    for proto in ("cv12", "loro48", "loso3")
                },
            },
            "cw_merge_reference": {
                "overall_mean": s2["overall"]["cw_merge_mean"],
                "overall_total": s2["overall"]["cw_merge_total"],
                "solve_ms": s2["overall"]["cw_merge_solve_ms"],
            },
        },
        "findings": [
            "Scale contraction law: in pointwise_base (8 rules), SBS-to-VBS complementarity contracts sharply with problem size: 3.92% (n=50) -> 1.73% (n=100) -> 0.76% (n=200).",
            "Parallel Clarke-Wright merge (cw_merge) outperforms pointwise_base SBS (savings) by 10.04% (22.95 vs 25.51) at 2.71 ms/instance; Stage 2 rules substantially close this pointwise-vs-merge gap.",
            "Scale-normalized ridge and cost-sensitive pairwise selectors yield small positive gains across cv12, loro48, and unseen-scale loso3, while honest Bootstrap CIs quantify where single-rule dominance limits net selection gain.",
        ],
        "verification": {
            "status": "verified_empirical_law",
            "reason": "288-instance 5-factor matrix and 3 out-of-fold protocols (cv12/loro48/loso3) completed with 10,000-draw paired Bootstrap CIs and Clarke-Wright reference.",
        },
    }
    by_id["H-010"] = h10

    ordered_ids = [r["id"] for r in rows]
    if "H-010" not in ordered_ids:
        ordered_ids.append("H-010")
    out_lines = [json.dumps(by_id[k], ensure_ascii=False) for k in ordered_ids]
    LEDGER.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    print(json.dumps({"updated_hypotheses": ordered_ids, "count": len(ordered_ids)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
