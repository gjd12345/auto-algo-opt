"""What did each 2x2 arm actually generate?

`tradeoff_probe.py` re-scores only the best candidate of a run, so it answers
"what did the arm stumble on".  The question in the task is different: does the
research finding change *generation*.  With one seed and four rounds, a single
best-of-run number cannot separate a 0.3pp effect from noise, but the ~18
candidates each arm produces can be scored on one yardstick, which turns the
comparison into a distribution comparison.

For every distinct candidate of every round in every tag (`a2`, `a3`, ...), this
script records the objective on the shared suite at the nominal scale, whether
the candidate stays feasible on all six instances, and the band shape from
`tradeoff_probe.band_shape`.  It then prints one table per tag and one pooled
per-arm table, because a replicate is a different roll of the same dice and the
arm medians are what has to be stable across tags.

Zero provider calls: everything is replayed from the candidate sources the runs
already stored.

    python experiments/cvrp_midterm/runs/candidate_distribution.py a2 a3
"""

from __future__ import annotations

import json
import random
import sys
import tempfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "experiments/cvrp_midterm/analysis"))
sys.path.insert(0, str(HERE))

from score_probe import build_matrix, load_candidate, simulate  # noqa: E402
from tradeoff_probe import FROZEN_DIR, SUITE, band_shape  # noqa: E402

ARMS = ("control", "finding_only", "operations_only", "guided")
CONTRASTS = {
    "finding_at_ops_off": lambda m: m["finding_only"] - m["control"],
    "finding_at_ops_on": lambda m: m["guided"] - m["operations_only"],
    "ops_at_finding_off": lambda m: m["operations_only"] - m["control"],
    "ops_at_finding_on": lambda m: m["guided"] - m["finding_only"],
    "interaction": lambda m: (m["guided"] - m["finding_only"])
    - (m["operations_only"] - m["control"]),
}
ROUNDS = (1, 2, 3, 4)


def suite_objective(fn, instances: list[dict]) -> float | None:
    objectives = []
    for inst in instances:
        result = simulate(fn, inst, matrix=build_matrix(inst))
        served = [node for node in result.route if node != 0]
        expected = len(inst["customer_coordinates"])
        if len(served) != expected or len(set(served)) != expected:
            return None
        objectives.append(float(result.objective))
    return float(np.mean(objectives))


def iter_candidates(tag: str, arm: str):
    base = HERE / f"{tag}_{arm}"
    for round_id in ROUNDS:
        skills = base / "rounds" / f"round_{round_id:04d}" / "eoh_run" / "skills"
        if not skills.is_dir():
            continue
        for cand_dir in sorted(skills.iterdir()):
            code = cand_dir / "code.py"
            if code.is_file() and cand_dir.name != "baseline":
                yield round_id, cand_dir.name, code


def summarise(rows: list[dict], frozen_objective: float, seed_objective: float) -> dict:
    scores = [r["objective"] for r in rows if r["objective"] is not None]
    entry: dict = {
        "n_candidates": len(rows),
        "n_scored": len(scores),
        "n_infeasible": len(rows) - len(scores),
        "n_below_frozen_C": sum(1 for s in scores if s < frozen_objective),
        "n_below_seed": sum(1 for s in scores if s < seed_objective),
        "n_mixed_units": sum(1 for r in rows if r["band_shape"] == "mixed_units"),
        "band_shapes": {k: sum(1 for r in rows if r["band_shape"] == k)
                        for k in sorted({r["band_shape"] for r in rows})},
    }
    if scores:
        arr = np.array(scores, dtype=float)
        entry.update({
            "median": float(np.median(arr)),
            "p10": float(np.quantile(arr, 0.10)),
            "p90": float(np.quantile(arr, 0.90)),
            "best": float(arr.min()),
            "worst": float(arr.max()),
            "vs_frozen_best": (float(arr.min()) - frozen_objective) / frozen_objective,
            "vs_frozen_median": (float(np.median(arr)) - frozen_objective) / frozen_objective,
            "vs_seed_median": (float(np.median(arr)) - seed_objective) / seed_objective,
        })
    return entry


def contrast(arms: dict) -> dict:
    def med(name: str) -> float:
        return arms[name].get("median", float("nan"))

    return {
        "finding_at_ops_off": med("finding_only") - med("control"),
        "finding_at_ops_on": med("guided") - med("operations_only"),
        "ops_at_finding_off": med("operations_only") - med("control"),
        "ops_at_finding_on": med("guided") - med("finding_only"),
        "interaction": (med("guided") - med("finding_only"))
        - (med("operations_only") - med("control")),
    }


def bootstrap_contrast(scores: dict[str, list[float]], reps: int = 4000,
                       seed: int = 0) -> dict:
    """Resample each arm's candidates and report a 95% interval per contrast.

    The arms are small (14-40 candidates), so a point estimate of a 0.1 difference
    in medians means nothing on its own.  Resampling candidates *within* an arm is
    the weakest assumption available: it does not pair candidates (the rounds are
    not paired across arms) and it keeps the observed spread.
    """
    rng = random.Random(seed)
    draws: dict[str, list[float]] = {k: [] for k in CONTRASTS}
    for _ in range(reps):
        med = {arm: float(np.median(rng.choices(vals, k=len(vals))))
               for arm, vals in scores.items()}
        for name, fn in CONTRASTS.items():
            draws[name].append(fn(med))
    out = {}
    for name, vals in draws.items():
        arr = np.array(vals, dtype=float)
        out[name] = {
            "lo": float(np.quantile(arr, 0.025)),
            "hi": float(np.quantile(arr, 0.975)),
            "crosses_zero": bool(np.quantile(arr, 0.025) <= 0.0 <= np.quantile(arr, 0.975)),
        }
    return out


def main() -> int:
    tags = sys.argv[1:] or ["a2", "a3"]
    instances = json.loads(SUITE.read_text(encoding="utf-8"))["instances"]

    out: dict = {"shared_suite": str(SUITE.relative_to(REPO)), "instances": len(instances),
                 "tags": tags, "per_tag": {}, "pooled": {}}

    with tempfile.TemporaryDirectory() as tmp:
        frozen_src = (FROZEN_DIR / "C.py").read_text(encoding="utf-8")
        frozen_path = Path(tmp) / "frozen_C.py"
        frozen_path.write_text(frozen_src, encoding="utf-8")
        frozen_objective = suite_objective(load_candidate(frozen_path), instances)
        seed_src = (FROZEN_DIR / "NN.py").read_text(encoding="utf-8")
        seed_path = Path(tmp) / "frozen_NN.py"
        seed_path.write_text(seed_src, encoding="utf-8")
        seed_objective = suite_objective(load_candidate(seed_path), instances)
        out["frozen_C"] = {"objective": frozen_objective, "band_shape": band_shape(frozen_src)}
        out["search_seed"] = {"objective": seed_objective, "source": "p0/frozen_code/NN.py"}

        pooled_rows: dict[str, list[dict]] = {arm: [] for arm in ARMS}
        for tag in tags:
            tag_out: dict = {}
            for arm in ARMS:
                seen: dict[str, dict] = {}
                for round_id, name, code_path in iter_candidates(tag, arm):
                    src = code_path.read_text(encoding="utf-8")
                    digest = str(abs(hash(src)))
                    if digest in seen:
                        seen[digest]["repeats"].append([round_id, name])
                        continue
                    path = Path(tmp) / f"{tag}_{arm}_{round_id}_{name}.py"
                    path.write_text(src, encoding="utf-8")
                    try:
                        objective = suite_objective(load_candidate(path), instances)
                    except Exception as exc:  # a candidate that cannot load is data too
                        objective = None
                        err = type(exc).__name__
                    else:
                        err = None
                    row = {
                        "tag": tag,
                        "round": round_id,
                        "name": name,
                        "bytes": len(src),
                        "objective": objective,
                        "load_error": err,
                        "band_shape": band_shape(src),
                        "repeats": [],
                        "source": str(code_path.relative_to(REPO)),
                    }
                    seen[digest] = row
                rows = list(seen.values())
                tag_out[arm] = summarise(rows, frozen_objective, seed_objective)
                tag_out[arm]["candidates"] = sorted(
                    rows, key=lambda r: (r["objective"] is None, r["objective"] or 0.0))
                pooled_rows[arm].extend(rows)
            tag_out["comparison"] = contrast(tag_out)
            out["per_tag"][tag] = tag_out

        for arm in ARMS:
            out["pooled"][arm] = summarise(pooled_rows[arm], frozen_objective, seed_objective)
            out["pooled"][arm]["candidates"] = sorted(
                pooled_rows[arm],
                key=lambda r: (r["objective"] is None, r["objective"] or 0.0))
        out["pooled"]["comparison"] = contrast(out["pooled"])
        scores = {arm: [r["objective"] for r in pooled_rows[arm] if r["objective"] is not None]
                  for arm in ARMS}
        out["pooled"]["bootstrap"] = bootstrap_contrast(scores)

    (HERE / "candidate_distribution.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"shared suite {out['instances']} instances; frozen C = {frozen_objective:.4f} "
          f"({out['frozen_C']['band_shape']}); search seed NN = {seed_objective:.4f}")

    def table(label: str, arms: dict) -> None:
        print(f"\n== {label}")
        print(f"{'arm':16s} {'n':>3s} {'infeas':>6s} {'<C':>4s} {'<seed':>6s} "
              f"{'median':>9s} {'best':>9s} {'median vs C':>12s} {'vs seed':>9s}  shapes")
        for arm, e in arms.items():
            if not isinstance(e, dict) or "n_candidates" not in e:
                continue
            med = f"{e['median']:.4f}" if "median" in e else "-"
            best = f"{e['best']:.4f}" if "best" in e else "-"
            vs = f"{e['vs_frozen_median'] * 100:+.2f}%" if "vs_frozen_median" in e else "-"
            vseed = f"{e['vs_seed_median'] * 100:+.2f}%" if "vs_seed_median" in e else "-"
            print(f"{arm:16s} {e['n_candidates']:>3d} {e['n_infeasible']:>6d} "
                  f"{e['n_below_frozen_C']:>4d} {e['n_below_seed']:>6d} "
                  f"{med:>9s} {best:>9s} {vs:>12s} {vseed:>9s}  {e['band_shapes']}")
        boot = arms.get("bootstrap")
        if boot:
            print("  95% bootstrap interval (candidates resampled within arm):")
            for name, ci in boot.items():
                mark = "crosses 0" if ci["crosses_zero"] else "excludes 0"
                print(f"    {name:20s} [{ci['lo']:+.3f}, {ci['hi']:+.3f}]  {mark}")
        c = arms["comparison"]
        print(f"  finding (ops off / on): {c['finding_at_ops_off']:+.4f} / "
              f"{c['finding_at_ops_on']:+.4f}")
        print(f"  ops (finding off / on): {c['ops_at_finding_off']:+.4f} / "
              f"{c['ops_at_finding_on']:+.4f}")
        print(f"  interaction:            {c['interaction']:+.4f}")

    for tag, arms in out["per_tag"].items():
        table(tag, arms)
    table("pooled " + "+".join(tags), out["pooled"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
