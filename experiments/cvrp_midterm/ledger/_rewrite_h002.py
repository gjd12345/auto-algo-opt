"""Rewrite ledger record H-002 so it matches the v2 evidence.

v1 recorded the hypothesis as "verified" on a 36-instance, three-regime testbed.
Two defects invalidated that reading:
  * the savings rule used the depot distance twice, so one of the four portfolio
    members was not the rule it claimed to be;
  * the "eccentric" regime moved three factors at once (depot position, capacity
    headroom, demand range), so the regime effect could not be attributed.
The v2 run crosses three binary factors independently (96 instances, demand range
fixed) and re-scores the selection question.  The strong form of the hypothesis is
falsified: one fixed rule is best in all eight cells and no learner beats it.
"""

import json
import pathlib

LEDGER = pathlib.Path("experiments/cvrp_midterm/ledger/hypotheses.jsonl")

record = {
    "id": "H-002",
    "round": 1,
    "target_rule": "algorithm portfolio {nn, savings, dd_load, radial} on crossed CVRP regimes",
    "hypothesis": (
        "No single constructive rule dominates across instance regimes, and the regime can be "
        "detected from pre-solve features, so an instance-level selector can recover part of the "
        "oracle gap."
    ),
    "diagnostic": {
        "script": "experiments/cvrp_midterm/selection/run_matrix.py + select.py",
        "artifact": "experiments/cvrp_midterm/selection/{matrix.json,summary.json,selectors.json}",
        "tables": "experiments/cvrp_midterm/selection/RESULTS_v2.md",
        "instances": 96,
        "instances_per_cell": 12,
        "customers_per_instance": 50,
        "factors": {
            "spatial": ["uniform", "clustered"],
            "depot": ["centre", "eccentric"],
            "capacity_total": {"loose": 45, "tight": 28},
        },
        "fixed_across_factors": {"demand_range": [1, 9]},
        "features": [
            "mean_demand",
            "cv_demand",
            "capacity_ratio",
            "cluster_tendency",
            "radial_std",
            "depot_eccentricity",
            "x_spread",
            "y_spread",
        ],
    },
    "evidence": {
        "vbs_total": 1253.7384,
        "sbs_total": 1274.1252,
        "sbs_algorithm": "savings",
        "sbs_gap_to_vbs": 0.016261,
        "rule_mean_objective": {
            "savings": 13.272138,
            "radial": 13.857131,
            "dd_load": 14.202563,
            "nn": 14.396212,
            "isolate": 18.450718,
            "load_fill": 19.892657,
            "farthest": 38.005881,
        },
        "oracle_counts": {"savings": 59, "dd_load": 17, "nn": 10, "radial": 10},
        "best_fixed_per_cell": "savings in 8/8 cells",
        "per_cell_sbs_gap": {
            "uniform_eccentric_tight": 0.003222,
            "clustered_eccentric_tight": 0.009469,
            "uniform_centre_tight": 0.011658,
            "clustered_centre_tight": 0.016163,
            "uniform_eccentric_loose": 0.022865,
            "uniform_centre_loose": 0.025611,
            "clustered_eccentric_loose": 0.02735,
            "clustered_centre_loose": 0.028245,
        },
        "selector_gap_to_vbs": {
            "fixed_best_sbs": 0.016261,
            "knn1_loo": 0.031518,
            "ridge_loo": 0.018581,
            "ridge_loro": 0.021603,
        },
        "portfolio_size_effect": "core-4 and extended-6 give identical VBS/SBS; isolate and load_fill never win a single instance",
        "rule_check": {
            "rule": "S(i, j) = d(i, 0) + d(0, j) - d(i, j)",
            "cases_checked": 200,
            "brute_force_agrees": True,
            "all_savings_zero_at_depot": True,
            "is_full_clarke_wright": False,
        },
        "superseded_v1": {
            "why_invalid": [
                "savings used dep[unvisited] + dep[unvisited] - cur[unvisited]: the depot distance entered twice, so the portfolio member was not the rule it was named after",
                "the eccentric regime changed depot position, capacity headroom and demand range together, so the regime label could not be attributed to any one factor",
            ],
            "vbs_total": 474.7977,
            "sbs_total": 494.8612,
            "sbs_gap_to_vbs": 0.042257,
            "best_fixed_algorithm": "radial",
            "artifact": "experiments/cvrp_midterm/selection/v1_20261121/",
        },
    },
    "findings": [
        "Complementarity survives the correction but is small: the oracle saves 1.63% over the best fixed rule on 96 instances, not 4.23%.",
        "The regime dependence in v1 was an artifact: after crossing the factors independently, savings is the best fixed rule in all 8 cells, so there is no regime in which the portfolio needs a different member.",
        "The selector claim is falsified in its v1 form: ridge LOO is 1.86% (0.23pp worse than fixing savings), 1-NN is 3.15%, and leave-one-regime-out is 2.16%. No learned selector beats the fixed choice.",
        "Complementarity is not explained by a thin portfolio: adding two structurally different rules (isolate, load_fill) leaves VBS and SBS unchanged at 1253.7384 / 1274.1252.",
        "Where the oracle gain does appear, it is concentrated in loose-capacity cells (2.57% mean) rather than tight ones (0.92%), i.e. the headroom is in instances where a rule's myopia is cheap to fix, not in instances a feature vector identifies.",
    ],
    "guidance": (
        "Do not build a universal selector on these features: the honest use of the 1.63% headroom is a "
        "fixed rule plus a narrow, capacity-aware fallback, and the report must say the selector result is "
        "negative. If selection is revisited, the target has to change from 'pick a rule' to 'pick when to "
        "apply a local improvement', because rule choice is already saturated by savings."
    ),
    "verification": {
        "status": "revise",
        "why": (
            "The measured complementarity stands at 1.63%, but the strong form of the hypothesis ('no single "
            "rule dominates' and 'a selector recovers part of the oracle gap') is contradicted by the v2 "
            "matrix: one fixed rule wins in all eight cells and every learned selector is worse than fixing "
            "it. The v1 'verified' status rested on a mis-implemented savings rule and a confounded regime "
            "contrast, and is withdrawn."
        ),
        "next_test": (
            "If scale is extended (100/200 customers), re-test only the loose-capacity cells, and test a "
            "conditional local-improvement policy instead of a rule selector."
        ),
    },
    "revisions": [
        {
            "revision": 1,
            "status": "verified",
            "note": "36 instances, three regimes, savings rule mis-implemented; withdrawn.",
        },
        {
            "revision": 2,
            "status": "revise",
            "note": "96 instances, three factors crossed independently, savings corrected; complementarity 1.63%, no selectable structure.",
        },
    ],
}

lines = [ln for ln in LEDGER.read_text(encoding="utf-8").splitlines() if ln.strip()]
out = []
for ln in lines:
    obj = json.loads(ln)
    if obj.get("id") == "H-002":
        out.append(json.dumps(record, ensure_ascii=False))
    else:
        out.append(ln)
LEDGER.write_bytes(("\n".join(out) + "\n").encode("utf-8"))
print("H-002 replaced; records:", len(out))
for ln in out:
    obj = json.loads(ln)
    print(" ", obj["id"], obj["verification"]["status"], len(ln), "chars")
