"""Executable test of one mathematical hypothesis about candidate C.

Hypothesis H1 (from score_probe): the near-tie band of C,
    band = 1e-3 * (span + 1.0)
mixes a *relative* unit (span) with an *absolute* length unit (1.0).  On a unit
square 1.0 is comparable to the whole score span, so the band is not homogeneous
under coordinate scaling: shrinking the instance by 1e-3 inflates the band
relative to span by ~1000x and the near-tie branch starts to fire on almost every
step; growing it by 1e3 removes the branch entirely.

Testable predictions, no LLM involved:
  P1  C's *scale-normalised* objective changes under coordinate scaling
  P2  the fraction of steps taking the near-tie branch grows as the instance shrinks
  P3  replacing the band with a purely relative one, 1e-3*span + 1e-12, makes both
      the branch rate and the normalised objective flat in scale

All distances scale linearly, so the comparable quantity across scales is
objective/scale.  Nothing below claims a variant is "better" beyond the numbers.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))

from score_probe import build_matrix, load_candidate, simulate  # noqa: E402

FROZEN = REPO / "reports/evidence/cvrp_p0_p1_p2_20261107/p0/frozen_code"
SUITE = REPO / "reports/evidence/cvrp_super_agent_reference_20261107/dev_suite.json"

C_SRC = (FROZEN / "C.py").read_text(encoding="utf-8")


def relative_band_variant() -> str:
    before = "band = 1e-3 * (span + 1.0)"
    after = "band = 1e-3 * span + 1e-12"
    if before not in C_SRC:
        raise SystemExit("C source changed: band expression not found")
    return C_SRC.replace(before, after)


def scaled_instance(instance: dict, scale: float) -> dict:
    out = json.loads(json.dumps(instance))
    out["depot"] = [x * scale for x in instance["depot"]]
    out["customer_coordinates"] = [
        [x * scale, y * scale] for x, y in instance["customer_coordinates"]
    ]
    return out


def run(fn, instance: dict):
    return simulate(fn, instance, matrix=build_matrix(instance))


def objective(fn, instance: dict) -> float:
    return float(run(fn, instance).objective)


def branch_rate(fn, instance: dict) -> float:
    """Fraction of steps whose choice is not the plain argmin of base.

    We cannot observe the branch flag from outside, so we reconstruct base with
    the same formula and count disagreements with argmin(base).
    """
    matrix = build_matrix(instance)
    result = run(fn, instance)
    hits = total = 0
    for step in result.steps:
        if step.chosen == 0 or not step.feasible:
            continue
        d_cur = matrix[step.current][step.feasible].astype(float)
        d_dep = matrix[0][step.feasible].astype(float)
        base = d_cur - 0.6 * d_dep
        total += 1
        if int(step.feasible[int(np.argmin(base))]) != int(step.chosen):
            hits += 1
    return hits / total if total else 0.0


def route_of(fn, instance: dict) -> list[int]:
    return [int(s.chosen) for s in run(fn, instance).steps]


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        c_path = Path(tmp) / "C.py"
        c_path.write_text(C_SRC, encoding="utf-8")
        r_path = Path(tmp) / "C_rel.py"
        r_path.write_text(relative_band_variant(), encoding="utf-8")
        c = load_candidate(c_path)
        c_rel = load_candidate(r_path)

    suite = json.loads(SUITE.read_text(encoding="utf-8"))
    instances = suite["instances"]
    scales = (1.0, 0.01, 0.001, 1000.0)

    rows = []
    for scale in scales:
        obj_c, obj_rel, br_c, br_rel = [], [], [], []
        for inst in instances:
            scaled = scaled_instance(inst, scale)
            obj_c.append(objective(c, scaled) / scale)
            obj_rel.append(objective(c_rel, scaled) / scale)
            br_c.append(branch_rate(c, scaled))
            br_rel.append(branch_rate(c_rel, scaled))
        rows.append(
            {
                "scale": scale,
                "normalised_objective_C": float(np.mean(obj_c)),
                "normalised_objective_C_rel": float(np.mean(obj_rel)),
                "branch_rate_C": float(np.mean(br_c)),
                "branch_rate_C_rel": float(np.mean(br_rel)),
            }
        )

    # Decision-level divergence: same node ids are meaningful across scales, so we
    # can compare the construction sequences directly.
    same = total = 0
    for inst in instances:
        nominal = route_of(c, inst)
        shrunk = route_of(c, scaled_instance(inst, 0.001))
        for a, b in zip(nominal, shrunk):
            total += 1
            same += 1 if a == b else 0
    agreement_shrunk = same / total if total else float("nan")

    nominal = rows[0]
    base_c = nominal["normalised_objective_C"]
    base_rel = nominal["normalised_objective_C_rel"]
    report = {
        "hypothesis": "H1: C's near-tie band mixes relative (span) and absolute (1.0) length units",
        "suite": str(SUITE.relative_to(REPO)),
        "instances": len(instances),
        "rows": rows,
        "checks": {
            "P1_normalised_objective_under_scaling": {
                "C": {str(r["scale"]): r["normalised_objective_C"] - base_c for r in rows},
                "C_rel": {str(r["scale"]): r["normalised_objective_C_rel"] - base_rel for r in rows},
            },
            "P2_branch_rate_under_scaling": {
                "C": {str(r["scale"]): r["branch_rate_C"] for r in rows},
                "C_rel": {str(r["scale"]): r["branch_rate_C_rel"] for r in rows},
            },
            "P3_relative_band_is_scale_flat": {
                "branch_rate_spread_C_rel": float(
                    max(r["branch_rate_C_rel"] for r in rows) - min(r["branch_rate_C_rel"] for r in rows)
                ),
                "normalised_objective_spread_C_rel_relative": float(
                    (max(r["normalised_objective_C_rel"] for r in rows)
                     - min(r["normalised_objective_C_rel"] for r in rows)) / base_rel
                ),
                "normalised_objective_spread_C_relative": float(
                    (max(r["normalised_objective_C"] for r in rows)
                     - min(r["normalised_objective_C"] for r in rows)) / base_c
                ),
            },
            "P4_remedy_costs_on_nominal_scale": {
                "C_rel_vs_C_relative_gap": float((base_rel - base_c) / base_c),
            },
            "decision_agreement_C_nominal_vs_shrunk": agreement_shrunk,
        },
    }
    out = HERE / "band_hypothesis.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
