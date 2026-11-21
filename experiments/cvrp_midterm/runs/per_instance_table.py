"""Per-instance objectives for the frozen rule and every arm's best candidate.

The arm-level gap is a mean over the run's own four instances, while the shared
suite has six. A mean hides which instances moved, and after batch 1 that turned
out to be the whole story, so this script prints the per-instance numbers and the
subset mean over the four instances the runs actually used.

    python experiments/cvrp_midterm/runs/per_instance_table.py
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
RUN_SUBSET = 4  # the runs froze dev_train-0..3
BATCH = "a1"
CANDIDATES = {
    "frozen_C": FROZEN_DIR / "C.py",
    "frozen_NN": FROZEN_DIR / "NN.py",
}


def arm_best(arm: str) -> tuple[Path, int, str] | None:
    report = json.loads((HERE / f"compare_{BATCH}.json").read_text(encoding="utf-8"))
    best = None
    for item in report.get(arm, []):
        cand = item.get("best")
        if cand and (best is None or cand["objective"] < best["objective"]):
            best = {**cand, "round": item["round"]}
    if best is None:
        return None
    return (HERE / f"{BATCH}_{arm}" / "rounds" / f"round_{best['round']:04d}" / "eoh_run"
            / "skills" / best["name"] / "code.py", best["round"], best["name"])


def main() -> int:
    global BATCH
    if len(sys.argv) > 1:
        BATCH = sys.argv[1]
    instances = json.loads(SUITE.read_text(encoding="utf-8"))["instances"]
    rows: dict[str, list[float]] = {}

    with tempfile.TemporaryDirectory() as tmp:
        paths = dict(CANDIDATES)
        # Arm names differ per batch (a4/a5 call the fourth arm ``full_guidance``),
        # so read them off the comparison report instead of hard-coding a roster.
        report = json.loads((HERE / f"compare_{BATCH}.json").read_text(encoding="utf-8"))
        for arm in report:
            if arm in paths:
                continue
            found = arm_best(arm)
            if found is not None:
                paths[arm] = found[0]
        for name, src_path in paths.items():
            copy = Path(tmp) / f"{name}.py"
            copy.write_text(src_path.read_text(encoding="utf-8"), encoding="utf-8")
            fn = load_candidate(copy)
            objectives = []
            for inst in instances:
                result = simulate(fn, inst, matrix=build_matrix(inst))
                objectives.append(float(result.objective))
            rows[name] = objectives

    ids = [inst.get("id") or inst.get("instance_id") for inst in instances]
    header = f"{'rule':16s} " + " ".join(f"{i[-1]:>8s}" for i in ids) + f" {'all6':>9s} {'first4':>9s} {'last2':>9s}"
    print(f"instances: {', '.join(ids)}   (runs used the first {RUN_SUBSET})")
    print(header)
    for name, objectives in rows.items():
        cells = " ".join(f"{v:8.3f}" for v in objectives)
        all6 = float(np.mean(objectives))
        first4 = float(np.mean(objectives[:RUN_SUBSET]))
        last2 = float(np.mean(objectives[RUN_SUBSET:]))
        print(f"{name:16s} {cells} {all6:9.3f} {first4:9.3f} {last2:9.3f}")

    base = rows["frozen_C"]
    print("\nrelative to frozen C on the same six instances")
    print(f"{'rule':16s} " + " ".join(f"{i[-1]:>8s}" for i in ids) + f" {'all6':>9s} {'first4':>9s}")
    for name, objectives in rows.items():
        cells = " ".join(f"{(v - b) / b * 100:+7.2f}%" for v, b in zip(objectives, base))
        all6 = (float(np.mean(objectives)) - float(np.mean(base))) / float(np.mean(base)) * 100
        first4 = (float(np.mean(objectives[:RUN_SUBSET]))
                  - float(np.mean(base[:RUN_SUBSET]))) / float(np.mean(base[:RUN_SUBSET])) * 100
        print(f"{name:16s} {cells} {all6:+8.2f}% {first4:+8.2f}%")

    out = HERE / f"per_instance_table_{BATCH}.json"
    out.write_text(json.dumps({"instances": ids, "objectives": rows}, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    print(f"\nwrote {out.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
