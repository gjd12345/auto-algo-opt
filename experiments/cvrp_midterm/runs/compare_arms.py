"""Compare the guided and control arms of the task-A pilot.

For every round it reports the candidate objectives, the incumbent trajectory,
and a structural probe of the best candidate, so the comparison covers both
``what the search found`` and ``what kind of rule it wrote``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

import numpy as np  # noqa: E402

import agent_skill_loop.evaluator as evaluator  # noqa: E402
from experiments.cvrp_midterm.analysis import score_probe  # noqa: E402

RUNS = REPO / "experiments/cvrp_midterm/runs"
DEV_SUITE = REPO / "reports/evidence/cvrp_super_agent_reference_20261107/dev_suite.json"


def round_dir(arm: str, round_id: int) -> Path:
    return RUNS / f"a1_{arm}" / "rounds" / f"round_{round_id:04d}"


def candidates(arm: str, round_id: int) -> list[dict]:
    base = round_dir(arm, round_id) / "eoh_run" / "skills"
    out = []
    if not base.exists():
        return out
    for path in sorted(base.glob("candidate_*")):
        code = path / "code.py"
        if not code.exists():
            continue
        evaluations = list(path.glob("evaluation*.json"))
        objective = None
        for item in evaluations:
            try:
                payload = json.loads(item.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and "objective" in payload:
                objective = payload["objective"]
        out.append({"name": path.name, "path": code, "objective": objective})
    return out


def evaluate_objective(code_path: Path, instances: list[dict]) -> float | None:
    suite = {
        "problem": "cvrp_construct",
        "split": "dev_train",
        "instances": instances,
    }
    from agent_skill_loop.problems.cvrp import suite_hash
    suite["content_hash"] = suite_hash("cvrp_construct", "dev_train", instances)
    result = evaluator.evaluate_candidate_request(
        {"problem": "cvrp_construct", "suite": suite, "code": code_path.read_text(encoding="utf-8")}
    )
    return result.get("objective") if result["valid"] else None


def main() -> int:
    dev = json.loads(DEV_SUITE.read_text(encoding="utf-8"))
    instances = dev["instances"]

    report = {}
    for arm in ("guided", "control"):
        rounds = []
        for round_id in (1, 2, 3, 4):
            facts_path = round_dir(arm, round_id) / "evaluation_facts.json"
            if not facts_path.exists():
                continue
            facts = json.loads(facts_path.read_text(encoding="utf-8"))
            base = (facts.get("baseline") or {}).get("objective")
            inc = (facts.get("incumbent_after") or {}).get("objective")
            cands = candidates(arm, round_id)
            scored = []
            for cand in cands:
                objective = cand["objective"]
                if objective is None:
                    objective = evaluate_objective(cand["path"], instances)
                scored.append({"name": cand["name"], "objective": objective})
            scored = [c for c in scored if c["objective"] is not None]
            scored.sort(key=lambda c: c["objective"])
            best = scored[0] if scored else None
            probe = None
            if best is not None:
                analysis = score_probe.analyze_code(best_name := Path(best["name"]), instances[:2], margin_limit=40) if False else None
            rounds.append({
                "round": round_id,
                "terminal_reason": facts.get("terminal_reason"),
                "baseline": base,
                "incumbent_after": inc,
                "candidates": scored[:6],
                "best": best,
            })
        report[arm] = rounds

    (RUNS / "guided_vs_control.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    for arm, rounds in report.items():
        print(arm)
        for item in rounds:
            best = item["best"] or {}
            print("  round", item["round"], "incumbent", item["incumbent_after"],
                  "best_candidate", best.get("name"), best.get("objective"),
                  "n_valid", len(item["candidates"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
