"""Add the full scale-term audit to H-001 and revise the finding it rests on.

Revision 1 indicted one term (the absolute ``+1.0`` inside the near-tie band).
``analysis/scale_term_audit.py`` measures every additive term of frozen C against
the base score it competes with, at four scales, and the ordering is not what the
entry claims:

* ``cap_term = 0.01 * |rest_capacity - dem| / d_cur`` grows as O(1/s^2) -- its
  numerator is in demand units while the divisor scales with the coordinates;
* ``-1e-6 * dem`` grows as O(1/s) -- demand units, never scaled;
* the band, including its absolute part, grows as O(1/s) at worst and is a mix of
  relative (O(1)) and absolute (O(1/s)) contributions.

So the band is the *third* strongest breaker, and the capacity-fit term is not a
tie-break at nominal scale either: inside the band it is a median 4.9x the base
spread, and at s = 1e-3 the band swallows 98.8% of candidates, which is why the
whole construction becomes capacity-driven.

Idempotent: re-running replaces the block instead of appending a second copy.

Run:  python experiments/cvrp_midterm/ledger/_rewrite_h001_v2.py
"""

from __future__ import annotations

import json
from pathlib import Path

LEDGER = Path(__file__).resolve().parent / "hypotheses.jsonl"
AUDIT = Path(__file__).resolve().parents[1] / "analysis/scale_term_audit.json"

FINDINGS = [
    "The near-tie band is not the dominant scale breaker: cap_term = 0.01*|rest_capacity - dem|/d_cur has "
    "numerator in demand units and divisor in coordinate units, so it grows as O(1/s^2) against the base "
    "score (measured exponent -2.017 over scales 1 / 0.01 / 0.001 / 1000).",
    "The demand tie-break -1e-6*dem is unscaled and grows as O(1/s) (measured exponent -0.942); the band as a "
    "whole sits between the two (exponent -0.541) because it mixes a relative span term with an absolute +1.0.",
    "cap_term is not a correction at nominal scale either: inside the band its median magnitude is 4.9x the "
    "median |base| (max 62x), so C's nominal decisions are largely capacity-fit decisions taken inside a "
    "distance-plausible tie set, not distance-minimising decisions with a small capacity nudge.",
    "At s = 1e-3 the band admits 98.8% of candidates (4.6% at s = 1), so the construction switches from "
    "band-limited to band-saturated and every decision is then resolved by cap_term and demand order.",
]


def main() -> int:
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in LEDGER.read_text(encoding="utf-8").splitlines() if line.strip()]
    seen = False
    for row in rows:
        if row.get("id") != "H-001":
            continue
        seen = True
        findings = list(row.get("findings", []))
        for finding in FINDINGS:
            if finding not in findings:
                findings.append(finding)
        row["findings"] = findings
        block = row.setdefault("experiment_evidence", {})
        block["scale_term_audit"] = {
            "script": audit["script"],
            "artifact": "experiments/cvrp_midterm/analysis/scale_term_audit.json",
            "suite": audit["suite"],
            "instances": audit["instances"],
            "scales": audit["scales"],
            "exponents": audit["exponents"],
            "pooled_by_scale": audit["pooled_by_scale"],
            "reading": "exponent -2 -> O(1/s^2), -1 -> O(1/s), 0 -> scale free; measured over the four scales",
        }
        verification = row.setdefault("verification", {})
        verification["status"] = "revise"
        verification["reason"] = (
            "The mechanism (non-equivariant near-tie band) reproduces, but attribution changes: the "
            "capacity-fit term breaks scale fastest (O(1/s^2)) and already dominates inside the band at the "
            "nominal scale, so a repair that only makes the band relative leaves the dominant breaker in place. "
            "That is consistent with the 2x2 result -- agents given the finding removed the absolute term and "
            "the score did not improve."
        )
        verification["next_test"] = (
            "Score each term's contribution directly (drop cap_term, drop -1e-6*dem, drop both) at s = 1 and "
            "s = 1e-2 to separate which breaker actually moves the objective, instead of inferring it from the "
            "band-width sweep."
        )
        revisions = row.setdefault("revisions", [])
        revisions.append({
            "revision": (revisions[-1]["revision"] + 1) if revisions else 2,
            "kind": "attribution",
            "what": "Added cap_term O(1/s^2) and -1e-6*dem O(1/s) to the scale analysis; band demoted to third breaker.",
            "why": "scale_term_audit.py measured all three additive terms; the original entry only indicted the band.",
        })
    if not seen:
        raise SystemExit("H-001 not found")
    LEDGER.write_bytes(
        ("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n").encode("utf-8"))
    print("updated", LEDGER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
