"""Common-yardstick comparison of the task-A 2x2 arms.

Two numbers are needed for every arm, and they answer different questions:

* the run's own ``incumbent`` gap, measured inside the run on the run's suite
  and relative to the run's seed (this is what the search saw);
* a re-score of every arm's best candidate on one shared suite with one
  evaluator, together with the frozen rule on that same suite (this is what a
  reader may compare).

Mixing the two is the easiest way to invent a fake improvement, so both are
written out side by side and the frozen rule is measured by the same code path
as the candidates rather than quoted from an earlier report.

``band_shape`` records whether a candidate still carries the mixed-unit band of
H-001, the cheap relative repair, or something else, because ``H-001`` says the
cheap repair buys scale-flatness at a known nominal cost. A candidate that
adopted the repair therefore cannot be filing it as a pure win.

Run after ``compare_arms.py``:
    python experiments/cvrp_midterm/runs/tradeoff_probe.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "experiments/cvrp_midterm/analysis"))

from score_probe import build_matrix, load_candidate, simulate  # noqa: E402

FROZEN_DIR = REPO / "reports/evidence/cvrp_p0_p1_p2_20261107/p0/frozen_code"
SUITE = REPO / "reports/evidence/cvrp_super_agent_reference_20261107/dev_suite.json"
SCALES = (1.0, 0.01, 0.001, 1000.0)
BATCH = "a1"


def scaled(instance: dict, scale: float) -> dict:
    out = json.loads(json.dumps(instance))
    out["depot"] = [x * scale for x in instance["depot"]]
    out["customer_coordinates"] = [[x * scale, y * scale] for x, y in instance["customer_coordinates"]]
    return out


def sweep(fn, instances: list[dict]) -> dict:
    rows = []
    for scale in SCALES:
        objectives = []
        for inst in instances:
            result = simulate(fn, scaled(inst, scale), matrix=build_matrix(scaled(inst, scale)))
            served = [node for node in result.route if node != 0]
            expected = len(inst["customer_coordinates"])
            if len(served) != expected or len(set(served)) != expected:
                return {"feasible": False, "scale": scale, "served": len(served),
                        "unique_served": len(set(served)), "expected": expected}
            objectives.append(float(result.objective) / scale)
        rows.append({"scale": scale, "normalised_objective": float(np.mean(objectives))})
    nominal = rows[0]["normalised_objective"]
    worst = max(r["normalised_objective"] for r in rows)
    return {
        "feasible": True,
        "rows": rows,
        "nominal_objective": nominal,
        "spread_relative": (worst - min(r["normalised_objective"] for r in rows)) / nominal,
    }


def band_shape(code: str) -> str:
    """Classify the near-tie band, if the candidate has one."""
    if "band" not in code:
        return "none"
    lines = [line.strip() for line in code.splitlines() if "band =" in line]
    if not lines:
        return "none"
    joined = " ".join(lines)
    if "span + 1.0" in joined.replace(" ", " ") or "(span+1.0)" in joined.replace(" ", ""):
        return "mixed_units"
    if "span" in joined and "1e-12" in joined:
        return "relative_with_epsilon"
    if "span" in joined:
        return "relative_only"
    return "other"


def run_level(arm: str) -> dict:
    base = HERE / f"{BATCH}_{arm}"
    rounds, gaps, reasons = [], [], []
    for round_id in (1, 2, 3, 4):
        facts_path = base / "rounds" / f"round_{round_id:04d}" / "evaluation_facts.json"
        if not facts_path.exists():
            continue
        facts = json.loads(facts_path.read_text(encoding="utf-8"))
        incumbent = (facts.get("incumbent_after") or {}).get("objective")
        rounds.append({"round": round_id, "incumbent": incumbent,
                       "terminal_reason": facts.get("terminal_reason")})
        if incumbent is not None:
            gaps.append(incumbent)
        reasons.append(facts.get("terminal_reason"))
    return {
        "rounds": rounds,
        "best_incumbent": min(gaps) if gaps else None,
        "terminal_reasons": reasons,
    }


def main() -> int:
    global BATCH
    if len(sys.argv) > 1:
        BATCH = sys.argv[1]
    suite = json.loads(SUITE.read_text(encoding="utf-8"))
    instances = suite["instances"]
    report = json.loads((HERE / f"compare_{BATCH}.json").read_text(encoding="utf-8"))

    out: dict = {"shared_suite": str(SUITE.relative_to(REPO)), "instances": len(instances),
                 "scales": list(SCALES), "arms": {}}

    with tempfile.TemporaryDirectory() as tmp:
        frozen_src = (FROZEN_DIR / "C.py").read_text(encoding="utf-8")
        frozen_path = Path(tmp) / "frozen_C.py"
        frozen_path.write_text(frozen_src, encoding="utf-8")
        frozen = sweep(load_candidate(frozen_path), instances)
        frozen.update({"source": "reports/evidence/cvrp_p0_p1_p2_20261107/p0/frozen_code/C.py",
                       "band_shape": band_shape(frozen_src)})
        out["arms"]["frozen_C"] = frozen

        for arm, rounds in report.items():
            entry = {"run_level": run_level(arm)}
            best = None
            for item in rounds:
                cand = item.get("best")
                if cand and (best is None or cand["objective"] < best["objective"]):
                    best = {**cand, "round": item["round"]}
            if best is None:
                entry["status"] = "no_scored_candidate"
                out["arms"][arm] = entry
                continue
            src_path = (HERE / f"{BATCH}_{arm}" / "rounds" / f"round_{best['round']:04d}"
                        / "eoh_run" / "skills" / best["name"] / "code.py")
            src = src_path.read_text(encoding="utf-8")
            path = Path(tmp) / f"{arm}.py"
            path.write_text(src, encoding="utf-8")
            entry.update(sweep(load_candidate(path), instances))
            entry.update({
                "candidate": best["name"],
                "round": best["round"],
                "objective_on_shared_suite": best["objective"],
                "band_shape": band_shape(src),
            })
            out["arms"][arm] = entry

    frozen_nominal = out["arms"]["frozen_C"]["nominal_objective"]
    for arm, entry in out["arms"].items():
        if entry.get("feasible"):
            entry["vs_frozen_on_shared_suite"] = (
                entry["nominal_objective"] - frozen_nominal) / frozen_nominal

    (HERE / "tradeoff_probe.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"shared suite: {out['instances']} instances")
    print(f"{'arm':16s} {'run best':>10s} {'shared':>10s} {'vs frozen':>10s} {'spread':>10s}  band")
    for arm, entry in out["arms"].items():
        run_best = (entry.get("run_level") or {}).get("best_incumbent")
        run_txt = f"{run_best:+.4f}" if run_best is not None else "-"
        if not entry.get("feasible"):
            print(f"{arm:16s} {run_txt:>10s}   infeasible at scale {entry.get('scale')}")
            continue
        vs = entry.get("vs_frozen_on_shared_suite")
        vs_txt = f"{vs * 100:+.2f}%" if vs is not None else "-"
        print(f"{arm:16s} {run_txt:>10s} {entry['nominal_objective']:>10.4f} {vs_txt:>10s} "
              f"{entry['spread_relative']:>10.1e}  {entry['band_shape']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
