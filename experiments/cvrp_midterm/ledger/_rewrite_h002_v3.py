"""Rewrite H-002 with the v3 evidence (frozen C rule joined the pool).

The v2 record said "one fixed rule wins in all eight cells and every learned
selector is worse than fixing it".  v3 keeps that selector result but changes
what the portfolio looks like: the frozen C rule enters the pool, lowers the
VBS, and never becomes the fixed choice.  The record has to say both things.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "ledger" / "hypotheses.jsonl"
SUMMARY = ROOT / "selection" / "summary.json"
SELECTORS = ROOT / "selection" / "selectors.json"

summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
selectors = json.loads(SELECTORS.read_text(encoding="utf-8"))

portfolios = summary["portfolios"]
pairwise = summary["pairwise"]
ext = portfolios["extended_c"]
core = portfolios["core"]
ext_sel = selectors["portfolios"]["extended_c"]["selectors"]
cost = selectors["selection_cost"]

sel_by_name = {entry["selector"]: entry for entry in ext_sel}

def gap(name: str) -> float:
    return sel_by_name[name]["gap_to_vbs"]

def picks(name: str) -> dict:
    return sel_by_name[name]["picks"]


evidence_v3 = {
    "portfolio": "core+{c} and extended+{c}; the frozen C rule is read from "
                 "reports/evidence/cvrp_p0_p1_p2_20261107/p0/frozen_code/C.py and "
                 "hash-checked, never edited",
    "frozen_member": summary["design"]["frozen_member"],
    "vbs_total": ext["vbs"],
    "sbs_total": ext["sbs"],
    "sbs_algorithm": ext["sbs_algorithm"],
    "sbs_gap_to_vbs": ext["sbs_gap_to_vbs"],
    "headroom": ext["headroom"],
    "core_only": {
        "vbs_total": core["vbs"],
        "sbs_total": core["sbs"],
        "sbs_gap_to_vbs": core["sbs_gap_to_vbs"],
        "oracle_counts": core["oracle_counts"],
    },
    "oracle_counts": ext["oracle_counts"],
    "c_vs_savings": pairwise["c_vs_savings"],
    "c_vs_nn": pairwise["c_vs_nn"],
    "c_vs_dd_load": pairwise["c_vs_dd_load"],
    "selector_gap_to_vbs": {
        "fixed_best_sbs": gap("fixed_best_sbs"),
        "knn1_loo": gap("knn1_loo"),
        "ridge_loo": gap("ridge_loo"),
        "pairwise_loo": gap("pairwise_loo"),
        "ridge_loro": gap("ridge_loro"),
        "pairwise_loro": gap("pairwise_loro"),
    },
    "selector_gain_vs_fixed": {
        "ridge_loo": sel_by_name["ridge_loo"]["gain_vs_fixed"],
        "pairwise_loo": sel_by_name["pairwise_loo"]["gain_vs_fixed"],
        "ridge_loro": sel_by_name["ridge_loro"]["gain_vs_fixed"],
        "pairwise_loro": sel_by_name["pairwise_loro"]["gain_vs_fixed"],
        "knn1_loo": sel_by_name["knn1_loo"]["gain_vs_fixed"],
    },
    "mean_regret": {name: sel_by_name[name]["mean_regret"] for name in sel_by_name},
    "selection_cost": cost,
    "artifacts": {
        "matrix": "experiments/cvrp_midterm/selection/matrix.json",
        "summary": "experiments/cvrp_midterm/selection/summary.json",
        "selectors": "experiments/cvrp_midterm/selection/selectors.json",
        "tables": "experiments/cvrp_midterm/selection/RESULTS_v3.md",
        "v2_frozen": "experiments/cvrp_midterm/selection/v2_20261121/",
    },
}

findings_v3 = [
    "Adding the frozen C rule to the pool lowers the VBS from {:.4f} to {:.4f} "
    "but leaves the SBS at {:.4f} ({}): C is never the rule a portfolio should "
    "fix on.".format(core["vbs"], ext["vbs"], ext["sbs"],
                     ext["sbs_algorithm"]),
    "C wins {} of 96 instances outright, and those wins are not where savings "
    "wins: the complementarity grows from {:.2f}% to {:.2f}%.".format(
        ext["oracle_counts"].get("c", 0),
        100 * core["sbs_gap_to_vbs"], 100 * ext["sbs_gap_to_vbs"]),
    "C's high score does not transfer: on this crossed family it loses to savings "
    "on {b_better} of 96 instances (mean relative gap {mean:+.2%}), although it "
    "still beats nn on {a_vs_nn} and dd_load on {a_vs_dd}.".format(
        b_better=pairwise["c_vs_savings"]["b_better"],
        mean=pairwise["c_vs_savings"]["mean_relative_delta"],
        a_vs_nn=pairwise["c_vs_nn"]["a_better"],
        a_vs_dd=pairwise["c_vs_dd_load"]["a_better"]),
    "The selector claim stays falsified after C joins the pool: every learned "
    "selector has negative gain against fixing savings (ridge LOO {:+.2%}, "
    "pairwise LOO {:+.2%}, ridge LORO {:+.2%}, pairwise LORO {:+.2%}), and the "
    "pairwise-comparison design does not repair it.".format(
        sel_by_name["ridge_loo"]["gain_vs_fixed"],
        sel_by_name["pairwise_loo"]["gain_vs_fixed"],
        sel_by_name["ridge_loro"]["gain_vs_fixed"],
        sel_by_name["pairwise_loro"]["gain_vs_fixed"]),
    "The fixed-choice default is almost what ridge LOO learns anyway: {:d} of 96 "
    "picks land on savings, so the learner spends its capacity re-deriving the "
    "baseline.".format(picks("ridge_loo").get("savings", 0)),
]

worst_cell = max(
    (entry["extended_c"]["sbs_gap_to_vbs"], cell)
    for cell, entry in summary["per_cell"].items()
)

verification = {
    "status": "revise",
    "why": (
        "The measured complementarity is real but small and does not come from a "
        "detectable regime: with the frozen C rule in the pool the oracle saves "
        "{:.2f}% over the best fixed rule (was {:.2f}% for the four-rule core), "
        "C never becomes the fixed choice, and every learned selector — ridge, "
        "1-NN and the new pairwise-comparison design, in LOO and LORO — is worse "
        "than fixing savings. The strong form ('no single rule dominates' plus "
        "'a selector recovers part of the oracle gap') is therefore still "
        "contradicted; only the weak form (a portfolio has measurable headroom) "
        "survives.".format(100 * ext["sbs_gap_to_vbs"], 100 * core["sbs_gap_to_vbs"])
    ),
    "next_test": (
        "Stop testing static selectors on 50-customer instances. If scale grows "
        "(100/200 customers), restrict to the loose-capacity cells — the widest "
        "headroom is {:.2f}% in {} — and test a conditional local-improvement "
        "policy instead of a one-shot rule choice.".format(
            100 * worst_cell[0], worst_cell[1])
    ),
}

record = None
for line in LEDGER.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    entry = json.loads(line)
    if entry.get("id") == "H-002":
        record = entry
    else:
        record = record if record is not None else None

if record is None:
    raise SystemExit("H-002 not found")

record["evidence"]["v3_frozen_c_in_pool"] = evidence_v3
record["findings"] = record["findings"] + findings_v3
record["verification"] = verification
record["revisions"].append({
    "revision": 3,
    "status": "revise",
    "note": "Frozen C rule entered the pool and a pairwise-comparison selector "
            "was added: complementarity 1.63%->2.05%, C never becomes the fixed "
            "choice, no learned selector beats fixed savings.",
})

lines = []
for line in LEDGER.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    entry = json.loads(line)
    lines.append(json.dumps(entry if entry.get("id") != "H-002" else record,
                            ensure_ascii=False))
LEDGER.write_text("\n".join(lines) + "\n", encoding="utf-8")

print("H-002 updated: status", verification["status"])
print(json.dumps(findings_v3, indent=1, ensure_ascii=False)[:1200])
