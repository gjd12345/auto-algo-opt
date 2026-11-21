"""Export structurally distinct Stage 2 discovered rules into selection_s2/rules_s2/.

Selection uses ONLY training-side/offline diagnostics (dev4 & ana72, zero P0 or
selection_s2 peeking) so Stage 2C cleanly tests Direction 1 -> Direction 2 feedback:
1. s2_r5_spiral : Round 5 c2 (ana72 rank 1; inward spiral + cos_theta + rho + two-phase + early return)
2. s2_r7_iso    : Round 7 c2 (balanced dev4=-0.1527; AST-safe isolation + cos_theta + rho + early return)
3. s2_r3_rho    : Round 3 c3 (dev4 rank 1=-0.1576; compact elongation rho + adaptive early return)
4. s2_ctrl_best : Control Round 7 c4 (best of 8-round / 48-request paired neutral control)
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
RUNS = REPO / "experiments/cvrp_midterm/runs"
OUT = REPO / "experiments/cvrp_midterm/selection_s2"
RULES_DIR = OUT / "rules_s2"

SPECS = [
    ("s2_r5_spiral", "s2_autonomous_math_r8", 5, "candidate_2", "autonomous_ana72_rank1_inward_spiral"),
    ("s2_r7_iso", "s2_autonomous_math_r8", 7, "candidate_2", "autonomous_r7_isolation_urgency"),
    ("s2_r3_rho", "s2_autonomous_math_r8", 3, "candidate_3", "autonomous_dev4_rank1_elongation"),
    ("s2_ctrl_best", "s2_control_r8", 7, "candidate_4", "paired_control_best_48req"),
]


def main() -> int:
    RULES_DIR.mkdir(parents=True, exist_ok=True)
    entries = []
    for name, run_name, rnd, cid, origin in SPECS:
        facts_p = RUNS / run_name / f"rounds/round_{rnd:04d}/evaluation_facts.json"
        facts = json.loads(facts_p.read_text(encoding="utf-8"))
        match = [c for c in facts["candidates"] if c.get("candidate_id") == cid and c.get("valid")]
        if not match:
            raise SystemExit(f"missing {run_name} R{rnd} {cid}")
        code = match[0]["code"]
        out_path = RULES_DIR / f"{name}.py"
        out_path.write_text(code, encoding="utf-8")
        entries.append({
            "name": name,
            "path": str(out_path.relative_to(REPO)).replace("\\", "/"),
            "origin": origin,
            "source_run": run_name,
            "round": rnd,
            "candidate_id": cid,
            "code_sha256": match[0]["code_sha256"],
        })
    (OUT / "extra_rules.json").write_text(json.dumps({"rules": entries}, indent=2), encoding="utf-8")
    print(json.dumps({"exported": [e["name"] for e in entries]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
