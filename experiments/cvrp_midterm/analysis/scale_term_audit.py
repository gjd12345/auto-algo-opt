"""Audit every scale-breaking term in frozen rule C, not just the near-tie band.

The revision-1 finding only indicted ``band = 1e-3 * (span + 1.0)``: a relative
width plus an absolute length unit. That is true, but it is not the only term
that breaks coordinate equivariance, and it is not the strongest one when the
instance is shrunk:

* ``band`` absolute part            -> fixed length 1e-3     -> O(1/s) of the main term
* ``-1e-6 * dem``                   -> demand units, unscaled -> O(1/s)
* ``cap_term = 0.01 * cap_gap / d``  -> gap is in demand units,
  divisor scales with s             -> O(1/s^2)

So as s -> 0 the rule is governed by the capacity-gap term first, demand order
second, and the band width third. This script measures those ratios on the real
dev suite at four scales and fits the exponent from log-log slope; the numbers
land in ``analysis/scale_term_audit.json`` and the ledger entry for H-001.

Run:  python experiments/cvrp_midterm/analysis/scale_term_audit.py
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Callable, Mapping

import numpy as np

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / "experiments/cvrp_midterm/analysis/scale_term_audit.json"
FROZEN_C = REPO / "reports/evidence/cvrp_p0_p1_p2_20261107/p0/frozen_code/C.py"
SUITE = REPO / "reports/evidence/cvrp_super_agent_reference_20261107/dev_suite.json"
SCALES = (1.0, 0.01, 0.001, 1000.0)
W = 0.6


def load_c() -> Callable[..., int]:
    namespace: dict[str, Any] = {"np": np, "numpy": np, "__name__": "frozen_c"}
    exec(compile(FROZEN_C.read_text(encoding="utf-8"), str(FROZEN_C), "exec"), namespace)  # noqa: S102
    return namespace["select_next_node"]


def matrix_for(instance: Mapping[str, Any], scale: float) -> np.ndarray:
    points = [list(instance["depot"])] + [list(p) for p in instance["customer_coordinates"]]
    coords = np.asarray(points, dtype=float) * float(scale)
    delta = coords[:, None, :] - coords[None, :, :]
    return np.sqrt(np.sum(delta * delta, axis=2))


def term_ratios(current: int, nodes: np.ndarray, rest_capacity: float,
                demands: np.ndarray, matrix: np.ndarray) -> dict[str, float]:
    """Magnitude of each scale-breaking term relative to the base-score spread."""
    d_cur = matrix[current][nodes].astype(float)
    d_dep = matrix[0][nodes].astype(float)
    base = d_cur - W * d_dep
    dem = demands[nodes].astype(float)
    # The base term is what the rule is nominally optimising, so it sets the unit
    # that the additive terms have to compete with.
    denom = max(float(np.median(np.abs(base))), 1e-12)
    best_base = float(np.min(base))
    span = float(np.max(base) - best_base)
    band = 1e-3 * (span + 1.0)
    mask = base <= (best_base + band)
    cap_gap = np.abs(rest_capacity - dem)
    local_scale = np.maximum(d_cur, 1e-9)
    cap_term = 0.01 * (cap_gap / local_scale)
    return {
        "base_median_abs": denom,
        "band_absolute": 1e-3,
        "band_relative": 1e-3 * span,
        "band_total_vs_base": band / denom,
        "demand_term_vs_base": float(np.max(1e-6 * dem)) / denom,
        "cap_term_vs_base": float(np.max(cap_term[mask])) / denom if mask.any() else 0.0,
        "branch_rate_denominator": float(nodes.size),
        "near_tie_candidates": int(mask.sum()),
    }


def slope(xs: list[float], ys: list[float]) -> float | None:
    """Least-squares exponent of y ~ x^slope in log-log space."""
    pairs = [(math.log10(x), math.log10(y)) for x, y in zip(xs, ys) if x > 0 and y > 0]
    if len(pairs) < 2:
        return None
    mx = sum(p[0] for p in pairs) / len(pairs)
    my = sum(p[1] for p in pairs) / len(pairs)
    num = sum((p[0] - mx) * (p[1] - my) for p in pairs)
    den = sum((p[0] - mx) ** 2 for p in pairs)
    return round(num / den, 3) if den > 1e-12 else None


def audit(instance: Mapping[str, Any], fn: Callable[..., int]) -> dict[str, Any]:
    demands = np.asarray([float(d) for d in instance["demands"]], dtype=float)
    capacity = float(instance["capacity"])
    rows: dict[str, list[dict[str, float]]] = {}
    for scale in SCALES:
        matrix = matrix_for(instance, scale)
        current, remaining = 0, capacity
        unvisited = {i for i in range(1, demands.size)}
        steps: list[dict[str, float]] = []
        guard = 4 * demands.size + 8
        while unvisited and guard > 0:
            guard -= 1
            feasible = sorted(n for n in unvisited if demands[n] <= remaining + 1e-12)
            if not feasible:
                current, remaining = 0, capacity
                continue
            nodes = np.asarray(feasible, dtype=int)
            chosen = int(fn(current, 0, nodes.copy(), remaining, demands.copy(), matrix.copy()))
            if chosen not in feasible:
                break
            steps.append(term_ratios(current, nodes, remaining, demands, matrix))
            unvisited.discard(chosen)
            remaining -= demands[chosen]
            current = chosen
        rows[f"{scale:g}"] = steps

    summary: dict[str, Any] = {}
    for scale_key, steps in rows.items():
        if not steps:
            continue
        summary[scale_key] = {
            "steps": len(steps),
            "band_total_vs_base_median": round(float(np.median([s["band_total_vs_base"] for s in steps])), 6),
            "cap_term_vs_base_median": round(float(np.median([s["cap_term_vs_base"] for s in steps])), 6),
            "demand_term_vs_base_median": round(float(np.median([s["demand_term_vs_base"] for s in steps])), 6),
            "cap_term_vs_base_max": round(float(np.max([s["cap_term_vs_base"] for s in steps])), 6),
            "near_tie_share": round(
                float(sum(s["near_tie_candidates"] for s in steps))
                / float(sum(s["branch_rate_denominator"] for s in steps)), 6),
        }
    keys = [k for k in ("1", "0.01", "0.001", "1000") if k in summary]
    scales = [float(k) for k in keys]
    exponents = {
        "band_total_vs_base": slope(scales, [summary[k]["band_total_vs_base_median"] for k in keys]),
        "cap_term_vs_base": slope(scales, [summary[k]["cap_term_vs_base_median"] for k in keys]),
        "demand_term_vs_base": slope(scales, [summary[k]["demand_term_vs_base_median"] for k in keys]),
    }
    return {"by_scale": summary, "exponents": exponents}


def main() -> int:
    suite = json.loads(SUITE.read_text(encoding="utf-8"))
    instances = suite["instances"] if isinstance(suite, Mapping) else suite
    fn = load_c()
    per_instance = {str(item.get("instance_id")): audit(item, fn) for item in instances}
    pooled: dict[str, Any] = {}
    for scale_key in [f"{s:g}" for s in SCALES]:
        rows = [inst["by_scale"][scale_key] for inst in per_instance.values() if scale_key in inst["by_scale"]]
        if not rows:
            continue
        pooled[scale_key] = {
            key: round(float(np.median([row[key] for row in rows])), 6)
            for key in ("band_total_vs_base_median", "cap_term_vs_base_median",
                        "demand_term_vs_base_median", "cap_term_vs_base_max", "near_tie_share")
        }
    keys = [k for k in [f"{s:g}" for s in SCALES] if k in pooled]
    scales = [float(k) for k in keys]
    report = {
        "script": "experiments/cvrp_midterm/analysis/scale_term_audit.py",
        "rule": "experiments/../reports/evidence/cvrp_p0_p1_p2_20261107/p0/frozen_code/C.py",
        "suite": SUITE.relative_to(REPO).as_posix(),
        "instances": len(instances),
        "scales": list(SCALES),
        "pooled_by_scale": pooled,
        "exponents": {
            "band_total_vs_base": slope(scales, [pooled[k]["band_total_vs_base_median"] for k in keys]),
            "cap_term_vs_base": slope(scales, [pooled[k]["cap_term_vs_base_median"] for k in keys]),
            "demand_term_vs_base": slope(scales, [pooled[k]["demand_term_vs_base_median"] for k in keys]),
        },
        "per_instance": per_instance,
    }
    OUT.write_bytes(json.dumps(report, ensure_ascii=False, indent=2).encode("utf-8") + b"\n")
    print(json.dumps({k: report[k] for k in ("pooled_by_scale", "exponents")}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
