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

ARM_ORDER = ("control", "finding_only", "operations_only")
FULL_ALIASES = ("full_guidance", "guided")
CONTRASTS = {
    "finding_at_ops_off": lambda m: m["finding_only"] - m["control"],
    "finding_at_ops_on": lambda m: m["full"] - m["operations_only"],
    "ops_at_finding_off": lambda m: m["operations_only"] - m["control"],
    "ops_at_finding_on": lambda m: m["full"] - m["finding_only"],
    "interaction": lambda m: (m["full"] - m["finding_only"])
    - (m["operations_only"] - m["control"]),
}


def discover_arms(tag: str) -> tuple[str, ...]:
    """Arms on disk for this batch, in 2x2 order.

    Batches 1-3 name the fourth arm ``guided``, batch 4+ names it
    ``full_guidance``; hardcoding either one drops an arm from every table.
    """
    found = [p.name[len(tag) + 1:] for p in HERE.glob(f"{tag}_*")
             if p.is_dir() and not p.name.startswith("_")]
    ordered = [a for a in ARM_ORDER if a in found]
    for alias in FULL_ALIASES:
        if alias in found:
            ordered.append(alias)
            break
    return tuple(ordered) + tuple(sorted(a for a in found if a not in ordered))


def role_arms(arms) -> dict:
    """Map each 2x2 role onto *all* arm names that implement it.

    A pooled run spans batches whose fourth arm is named ``guided`` (a2/a3) or
    ``full_guidance`` (a4/a5).  Taking only the first alias silently drops the
    other half of the "full" cell and turns every contrast that touches it into
    ``nan``, so a role maps to a list and the median is taken over the union.
    """
    names = list(arms)
    out = {a: [a] for a in ARM_ORDER if a in names}
    full = [alias for alias in FULL_ALIASES if alias in names]
    if full:
        out["full"] = full
    return out


def role_median(values: dict[str, list[float]], roster: dict) -> dict[str, float]:
    """Median objective per 2x2 role, pooling every arm that fills that role."""
    out = {}
    for role, names in roster.items():
        pooled = [v for name in names for v in values.get(name, [])]
        out[role] = float(np.median(pooled)) if pooled else float("nan")
    return out
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


def scores_of(arms: dict) -> dict[str, list[float]]:
    """Per-arm objective lists, rebuilt from the scored candidate rows."""
    out = {}
    for arm, entry in arms.items():
        if not isinstance(entry, dict) or "candidates" not in entry:
            continue
        out[arm] = [c["objective"] for c in entry["candidates"]
                    if c.get("objective") is not None]
    return out


def contrast(scores: dict[str, list[float]]) -> dict:
    roster = role_arms(scores)
    med = role_median(scores, roster)

    def m(role: str) -> float:
        return med.get(role, float("nan"))

    return {
        "finding_at_ops_off": m("finding_only") - m("control"),
        "finding_at_ops_on": m("full") - m("operations_only"),
        "ops_at_finding_off": m("operations_only") - m("control"),
        "ops_at_finding_on": m("full") - m("finding_only"),
        "interaction": (m("full") - m("finding_only"))
        - (m("operations_only") - m("control")),
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
    roster = role_arms(scores)
    draws: dict[str, list[float]] = {k: [] for k in CONTRASTS}
    for _ in range(reps):
        resampled = {arm: list(rng.choices(vals, k=len(vals)))
                     for arm, vals in scores.items() if vals}
        med = role_median(resampled, roster)
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

        roster = {tag: discover_arms(tag) for tag in tags}
        all_arms: list[str] = []
        for tag in tags:
            for arm in roster[tag]:
                if arm not in all_arms:
                    all_arms.append(arm)
        pooled_rows: dict[str, list[dict]] = {arm: [] for arm in all_arms}
        for tag in tags:
            tag_out: dict = {}
            for arm in roster[tag]:
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
            tag_out["comparison"] = contrast(scores_of(tag_out))
            out["per_tag"][tag] = tag_out

        for arm in all_arms:
            out["pooled"][arm] = summarise(pooled_rows[arm], frozen_objective, seed_objective)
            out["pooled"][arm]["candidates"] = sorted(
                pooled_rows[arm],
                key=lambda r: (r["objective"] is None, r["objective"] or 0.0))
        scores = {arm: [r["objective"] for r in pooled_rows[arm] if r["objective"] is not None]
                  for arm in all_arms}
        out["pooled"]["comparison"] = contrast(scores)
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
