"""Append the 2x2 experiment evidence to H-001 and refresh its verdict.

The ledger entry for H-001 was written from the diagnostics alone (scale sweep).
Two batches of four-arm runs have since tested the obvious question -- does an
agent that is told about this finding actually fix the rule? -- and the answer is
no, so the entry has to carry that, otherwise it keeps implying that the finding
is "adopted but unverified" rather than "measured, and not adopted".

Idempotent: re-running replaces the block instead of appending a second copy.
"""

from __future__ import annotations

import json
from pathlib import Path

LEDGER = Path(__file__).resolve().parent / "hypotheses.jsonl"

BLOCK = {
    "batch": "a2+a3 (2026-11-21)",
    "design": "2x2 (operations x research finding), two independent replicates, "
              "4 rounds / 24 requests / 120 solver calls per arm, deepseek-flash",
    "shared_suite": "6 instances, frozen C = 10.9197, search seed NN = 12.1150",
    "best_candidate_vs_frozen_C": {
        "a2": {"control": 0.0527, "finding_only": 0.0316,
               "operations_only": 0.0177, "guided": 0.0288},
        "a3": {"control": 0.0461, "finding_only": 0.0399,
               "operations_only": 0.0305, "guided": 0.0342},
    },
    "median_candidate_vs_seed": {
        "a2": {"control": 0.0180, "finding_only": 0.0386,
               "operations_only": 0.0000, "guided": -0.0011},
        "a3": {"control": 0.0359, "finding_only": 0.0241,
               "operations_only": 0.0029, "guided": 0.0020},
    },
    "contrast_median_shift": {
        "finding_at_ops_off": {"a2": 0.2487, "a3": -0.1433, "pooled": 0.074,
                               "ci95": [-0.444, 0.464]},
        "finding_at_ops_on": {"a2": -0.0131, "a3": -0.0113, "pooled": -0.004,
                              "ci95": [-0.312, 0.503]},
        "ops_at_finding_off": {"a2": -0.2186, "a3": -0.4000, "pooled": -0.278,
                               "ci95": [-0.720, 0.168]},
        "ops_at_finding_on": {"a2": -0.4804, "a3": -0.2679, "pooled": -0.357,
                              "ci95": [-0.612, 0.232]},
        "interaction": {"a2": -0.2618, "a3": 0.1321, "pooled": -0.078,
                        "ci95": [-0.612, 0.625]},
    },
    "candidates": {"total": 217, "below_frozen_C": 0,
                   "mixed_units_band_shape": 0,
                   "note": "a1 produced 10 relative_with_epsilon candidates only "
                           "because its guidance text contained the patch itself"},
    "structural_finding": "The search seed is NN (baseline_code_sha256 90b23362), "
                          "not C, so a finding about C's near-tie band cannot be "
                          "applied to C: every arm rewrote the constructor instead. "
                          "In a1 the finding carried C's formula, which is the only "
                          "reason an agent could copy C back and patch it.",
}

VERDICT = {
    "status": "revise",
    "reason": "Mechanism still holds, and the naive remedy is still falsified. Two "
              "4-arm batches add a third result: agents given the finding do not "
              "adopt either half of the measured trade-off (they drop the absolute "
              "term, nobody restores the nominal firing width), and no candidate in "
              "217 beats frozen C. The finding changes how the rule is written, not "
              "how well it scores, and the 2x2 median shifts are indistinguishable "
              "from zero (all bootstrap intervals cross 0).",
    "next_test": "Re-run with seed = incumbent = C so that the finding and the rule "
                 "being edited refer to the same object; without that the question "
                 "'can a finding repair rule C' is untestable.",
    "evidence": "experiments/cvrp_midterm/runs/RESULTS_BATCH1.md, "
                "experiments/cvrp_midterm/runs/RESULTS_BATCH2.md, "
                "experiments/cvrp_midterm/runs/candidate_distribution.json",
}


def main() -> int:
    rows = [json.loads(line) for line in LEDGER.read_text(encoding="utf-8").splitlines() if line.strip()]
    seen = False
    for row in rows:
        if row.get("id") != "H-001":
            continue
        seen = True
        row.setdefault("experiment_evidence", {})["adoption_test"] = BLOCK
        row["verification"] = VERDICT
    if not seen:
        raise SystemExit("H-001 not found")
    LEDGER.write_bytes(
        ("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n").encode("utf-8"))
    print("updated", LEDGER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
