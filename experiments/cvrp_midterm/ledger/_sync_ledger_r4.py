"""Synchronize H-001 (rev 3) and H-002 (rev 4) in hypotheses.jsonl from verified JSON outputs.

Idempotent: updates existing H-001 and H-002 records in place without duplicating findings or revisions.
Run: python experiments/cvrp_midterm/ledger/_sync_ledger_r4.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "ledger/hypotheses.jsonl"
AUDIT = ROOT / "analysis/scale_term_audit.json"
SUMMARY = ROOT / "selection/summary.json"
SELECTORS = ROOT / "selection/selectors.json"


def main() -> int:
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    selectors = json.loads(SELECTORS.read_text(encoding="utf-8"))

    rows = [json.loads(line) for line in LEDGER.read_text(encoding="utf-8").splitlines() if line.strip()]
    for row in rows:
        if row.get("id") == "H-001":
            p = audit["pooled_by_scale"]
            ab = audit["ablation_normalized_objective"]
            sp = audit["ablation_scale_spread"]
            ex = audit["exponents"]
            row["findings"] = [
                "Scale non-equivariance is real and monotone in coordinate scale (+48% at 1e-2, +207% at 1e-3).",
                f"Corrected 300-step audit (all 50 customers, exact C.py:35 gate mask>=2 & cur!=0): gate rate jumps "
                f"{100*p['1']['gate_rate']:.1f}% (s=1) -> {100*p['0.01']['gate_rate']:.1f}% (s=0.01) -> "
                f"{100*p['0.001']['gate_rate']:.1f}% (s=0.001) -> {100*p['1000']['gate_rate']:.1f}% (s=1000).",
                f"band and cap_term act in series (gate x payload): at s=1 effective all-step cap_term/base median is "
                f"{p['1']['cap_term_effective_vs_base_median']:.4g} (0 on 98.3% of steps), whereas conditioned on gated steps "
                f"cap_term/base scales as O(1/s^2) (4-point log-log slope {ex['cap_term_when_gated_vs_base']:+.3f}: "
                f"{p['1']['cap_term_when_gated_vs_base_median']:.2f} -> {p['0.01']['cap_term_when_gated_vs_base_median']:.0f} -> "
                f"{p['0.001']['cap_term_when_gated_vs_base_median']:.2e}).",
                f"-1e-6*dem scales as O(1/s) (4-point slope {ex['demand_term_vs_base']:+.3f}); band/base has hybrid slope "
                f"{ex['band_total_vs_base']:+.3f} because it mixes O(1) relative span with O(1/s) absolute 1e-3.",
                f"Direct 3-term ablation across 4 scales: C_full spread={100*sp['C_full']:.2f}% (s=1: {ab['C_full']['1']:.4f}, s=1e-3: {ab['C_full']['0.001']:.4f}); "
                f"C_rel_band spread={100*sp['C_rel_band']:.2f}% (s=1: {ab['C_rel_band']['1']:.4f}); "
                f"C_no_cap spread={100*sp['C_no_cap']:.2f}% (s=1: {ab['C_no_cap']['1']:.4f}, s=1e-3: {ab['C_no_cap']['0.001']:.4f}); "
                f"C_no_dem spread={100*sp['C_no_dem']:.2f}% (s=1: {ab['C_no_dem']['1']:.4f}, s=1e-3: {ab['C_no_dem']['0.001']:.4f}); "
                f"C_no_cap_no_dem spread={100*sp['C_no_cap_no_dem']:.2f}%.",
            ]
            row.setdefault("experiment_evidence", {})["scale_term_audit"] = {
                "script": audit["script"],
                "artifact": "experiments/cvrp_midterm/analysis/scale_term_audit.json",
                "instances": audit["instances"],
                "customers_per_instance": audit["customers_per_instance"],
                "scales": audit["scales"],
                "exponents": ex,
                "pooled_by_scale": p,
                "ablation_normalized_objective": ab,
                "ablation_scale_spread": sp,
            }
            row["verification"] = {
                "status": "verified_mechanism_revise_remedy",
                "reason": (
                    "Series gate-x-payload mechanism verified by both 300-step gated audit and direct 3-term ablation: "
                    "dropping cap_term eliminates the 207% collapse completely (C_no_cap), while making band relative "
                    "suppresses it to 0.39% (C_rel_band) at a +1.92% nominal cost. Prior rev-2 audit had an off-by-one "
                    "demands bug (49 steps) and ignored C.py:35's gate, overstating nominal cap_term."
                ),
                "next_test": (
                    "Start real inter-round autonomous search from frozen C/A (not NN) and test scale-invariant "
                    "dimensionless secondary ranking on both dev and independent multi-scale held-out (n=50/100/200)."
                ),
            }
            revs = [r for r in row.get("revisions", []) if r.get("revision") not in (2, 3)]
            revs.append({
                "revision": 2,
                "kind": "attribution_superseded",
                "what": "Initial 3-term audit had off-by-one demands (49 steps) and ignored C.py:35 gate; superseded by rev 3.",
            })
            revs.append({
                "revision": 3,
                "kind": "corrected_audit_and_ablation",
                "what": "Fixed 50-customer demands indexing and exact C.py:35 gate; ran direct 3-term ablation confirming band (gate) x cap_term (O(1/s^2) payload) series mechanism.",
            })
            row["revisions"] = revs

        elif row.get("id") == "H-002":
            full = summary["portfolios"]["full_pool"]
            sel_full = {s["selector"]: s for s in selectors["portfolios"]["full_pool"]["selectors"]}
            row["evidence"]["v4_abc_in_pool"] = {
                "portfolio": "full_pool = extended + frozen {A, B, C} (all SHA-256 verified)",
                "vbs_total": full["vbs"],
                "sbs_total": full["sbs"],
                "sbs_algorithm": full["sbs_algorithm"],
                "sbs_gap_to_vbs": full["sbs_gap_to_vbs"],
                "headroom": full["headroom"],
                "oracle_counts": full["oracle_counts"],
                "mean_objective": summary["portfolio_mean"],
                "mean_solve_s": summary["mean_solve_s"],
                "mean_runtime_s": summary["mean_runtime_s"],
                "mean_rank": summary["mean_rank"],
                "selectors": {
                    k: {
                        "total_objective": v["total_objective"],
                        "gap_to_vbs": v["gap_to_vbs"],
                        "gain_vs_fixed": v["gain_vs_fixed"],
                        "gain_ci95": v.get("gain_ci95"),
                        "p_boot_one_sided": v.get("p_boot_one_sided"),
                        "wtl_vs_fixed": v.get("wtl_vs_fixed"),
                        "mean_regret": v["mean_regret"],
                        "worst_regret": v["worst_regret"],
                    }
                    for k, v in sel_full.items()
                },
                "artifacts": {
                    "matrix": "experiments/cvrp_midterm/selection/matrix.json",
                    "summary": "experiments/cvrp_midterm/selection/summary.json",
                    "selectors": "experiments/cvrp_midterm/selection/selectors.json",
                    "tables": "experiments/cvrp_midterm/selection/RESULTS_v4.md",
                },
            }
            stump = sel_full["cluster_stump_loo"]
            pw_u = sel_full["pairwise_loo_unweighted"]
            pw_w = sel_full["pairwise_loo"]
            rg = sel_full["ridge_loo"]
            row["findings"] = [
                f"Widening the pool to frozen A/B/C expands complementarity from 1.63% (core) / 2.05% (+C) to "
                f"{100*full['sbs_gap_to_vbs']:.2f}% (VBS {full['vbs']:.4f} vs SBS {full['sbs']:.4f} [{full['sbs_algorithm']}], headroom {full['headroom']:.4f}).",
                "Spatial regime split is real: A wins 3/4 uniform cells (uniform mean a=14.4702 < savings=14.5672 < b=14.7222), "
                "while B wins all 4/4 clustered cells (clustered mean b=11.8158 < savings=11.9770 < a=12.2906).",
                f"Point-estimate selector gains turn positive for the first time in full_pool: "
                f"pairwise_loo_unweighted {100*pw_u['gain_vs_fixed']:+.2f}% (95% CI [{100*pw_u['gain_ci95'][0]:+.2f}%, {100*pw_u['gain_ci95'][1]:+.2f}%], p={pw_u['p_boot_one_sided']}), "
                f"ridge_loo {100*rg['gain_vs_fixed']:+.2f}%, pairwise_loo (cost-sensitive) {100*pw_w['gain_vs_fixed']:+.2f}%.",
                f"However, 8-feature LOO/LORO 95% CIs still cross zero and worst_regret worsens from 17.62% to 25.66%, "
                f"whereas the 1-feature cluster_stump_loo achieves {100*stump['gain_vs_fixed']:+.2f}% "
                f"(95% CI [{100*stump['gain_ci95'][0]:+.2f}%, {100*stump['gain_ci95'][1]:+.2f}%], p={stump['p_boot_one_sided']}) — "
                f"showing the predictable signal at n=50 is predominantly spatial clustering.",
                f"Pure pre-compiled solve times remove AST-parsing confound: savings={summary['mean_solve_s']['savings']*1000:.2f}ms, "
                f"a={summary['mean_solve_s']['a']*1000:.2f}ms, c={summary['mean_solve_s']['c']*1000:.2f}ms, b={summary['mean_solve_s']['b']*1000:.2f}ms "
                "(C is slightly faster than B in pure solve time; its 2.62ms full eval cost was >50% AST parsing).",
            ]
            row["verification"] = {
                "status": "partial_support_scale_up",
                "why": (
                    "Adding strong generalized rules A and B unlocks real spatial complementarity (4.09% gap) and "
                    "positive out-of-fold selector gains (+0.72% to +0.94% LOO; +0.47% to +0.68% LORO), overturning "
                    "rev-3's negative claim. Yet 8-feature CIs still cross 0 at n=50/96 instances and a 1-feature "
                    "cluster_tendency stump captures nearly the entire gain."
                ),
                "next_test": (
                    "Stage 2 multi-scale heterogeneous testbed (n in {50, 100, 200} x spatial x depot x capacity x "
                    "demand distribution = 288 instances) with Random Forest, cost-sensitive pairwise, Clarke-Wright "
                    "merge reference, and Leave-One-Scale-Out (LOSO) validation."
                ),
            }
            revs = [r for r in row.get("revisions", []) if r.get("revision") != 4]
            revs.append({
                "revision": 4,
                "status": "partial_support_scale_up",
                "note": (
                    "Frozen A/B/C added to pool + pure solve timing + paired bootstrap CIs + 1-feature cluster_stump: "
                    "gap 4.09%, LOO point estimates +0.72%..+0.94% (8-feature 95% CIs cross 0; 1-feature stump captures "
                    "the uniform-A vs clustered-B split cleanly)."
                ),
            })
            row["revisions"] = revs

    LEDGER.write_bytes(("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n").encode("utf-8"))
    print("synced H-001 (rev 3) and H-002 (rev 4) in", LEDGER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
