"""Audit every scale-breaking term in frozen rule C and run a 3-term ablation.

Three additive components break coordinate equivariance in frozen ``C.py``:

* ``band = 1e-3 * (span + 1.0)`` -> mixes relative O(1) with absolute O(1/s)
* ``-1e-6 * dem``                -> unscaled demand units, O(1/s) vs base
* ``cap_term = 0.01 * |rest_capacity - dem| / max(d_cur, 1e-9)``
  -> demand numerator / distance denominator, O(1/s^2) vs base, gated by
     ``mask.sum() >= 2 and current_node != depot`` (line 35 of C.py).

Crucially, ``band`` and ``cap_term`` act in series (gate x payload): at nominal
scale s = 1 the gate opens on only ~1.7% of steps (so effective cap_term is 0
on 98.3% of steps). As s shrinks, the absolute +1.0 inside ``band`` pries the
gate open (1.7% -> 67.7% -> 84.3%), exposing the route to the O(1/s^2) cap_term
payload.

This script:
1. Runs all 50 customers per instance (prepending depot demand 0.0 to match
   ``agent_skill_loop.evaluator`` exactly).
2. Measures gate rate, effective (all-step) and conditional (when-gated)
   term-to-base ratios at full float precision across four scales.
3. Directly ablates each breaker (C_full, C_rel_band, C_no_cap, C_no_dem,
   C_no_cap_no_dem, C_rel_band_no_cap) across all four scales.

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


def compile_rule(source: str, name: str = "rule") -> Callable[..., int]:
    namespace: dict[str, Any] = {"np": np, "numpy": np, "__name__": name}
    exec(compile(source, name, "exec"), namespace)  # noqa: S102
    return namespace["select_next_node"]


def load_c() -> Callable[..., int]:
    return compile_rule(FROZEN_C.read_text(encoding="utf-8"), str(FROZEN_C))


def build_ablation_rules() -> dict[str, Callable[..., int]]:
    src = FROZEN_C.read_text(encoding="utf-8")
    band_old = "band = 1e-3 * (span + 1.0)"
    band_rel = "band = 1e-3 * span + 1e-12"
    cap_old = "cap_term = 0.01 * (cap_gap / local_scale) * mask.astype(float)"
    cap_zero = "cap_term = np.zeros_like(base)"
    dem_old_1 = "corrected = base + cap_term - 1e-6 * dem"
    dem_new_1 = "corrected = base + cap_term"
    dem_old_2 = "val = base[idx] - 1e-6 * dem[idx]"
    dem_new_2 = "val = base[idx]"
    for needle in (band_old, cap_old, dem_old_1, dem_old_2):
        if needle not in src:
            raise SystemExit(f"expected line missing from frozen C.py: {needle}")
    variants = {
        "C_full": src,
        "C_rel_band": src.replace(band_old, band_rel),
        "C_no_cap": src.replace(cap_old, cap_zero),
        "C_no_dem": src.replace(dem_old_1, dem_new_1).replace(dem_old_2, dem_new_2),
        "C_no_cap_no_dem": (
            src.replace(cap_old, cap_zero)
               .replace(dem_old_1, dem_new_1)
               .replace(dem_old_2, dem_new_2)
        ),
        "C_rel_band_no_cap": src.replace(band_old, band_rel).replace(cap_old, cap_zero),
    }
    return {name: compile_rule(code, name) for name, code in variants.items()}


def matrix_for(instance: Mapping[str, Any], scale: float) -> np.ndarray:
    points = [list(instance["depot"])] + [list(p) for p in instance["customer_coordinates"]]
    coords = np.asarray(points, dtype=float) * float(scale)
    delta = coords[:, None, :] - coords[None, :, :]
    return np.sqrt(np.sum(delta * delta, axis=2))


def simulate_objective(fn: Callable[..., int], instance: Mapping[str, Any], scale: float) -> float:
    matrix = matrix_for(instance, scale)
    demands = np.asarray([0.0] + [float(d) for d in instance["demands"]], dtype=float)
    capacity = float(instance["capacity"])
    current, remaining = 0, capacity
    unvisited = set(range(1, demands.size))
    route = [0]
    guard = 4 * demands.size + 16
    while unvisited and guard > 0:
        guard -= 1
        feasible = sorted(n for n in unvisited if demands[n] <= remaining + 1e-12)
        if not feasible:
            route.append(0)
            current, remaining = 0, capacity
            continue
        nodes = np.asarray(feasible, dtype=int)
        chosen = int(fn(current, 0, nodes.copy(), remaining, demands.copy(), matrix.copy()))
        if chosen not in feasible:
            raise ValueError(f"invalid chosen node {chosen}")
        route.append(chosen)
        unvisited.discard(chosen)
        remaining -= demands[chosen]
        current = chosen
    if route[-1] != 0:
        route.append(0)
    total = float(sum(matrix[a, b] for a, b in zip(route, route[1:])))
    return total / float(scale)


def term_ratios(current: int, nodes: np.ndarray, rest_capacity: float,
                demands: np.ndarray, matrix: np.ndarray) -> dict[str, float | int | bool]:
    """Magnitude of each scale-breaking term relative to median |base|."""
    d_cur = matrix[current][nodes].astype(float)
    d_dep = matrix[0][nodes].astype(float)
    base = d_cur - W * d_dep
    dem = demands[nodes].astype(float)
    denom = max(float(np.median(np.abs(base))), 1e-12)
    best_base = float(np.min(base))
    span = float(np.max(base) - best_base)
    band = 1e-3 * (span + 1.0)
    mask = base <= (best_base + band)
    gated = bool(mask.sum() >= 2 and current != 0)
    cap_gap = np.abs(rest_capacity - dem)
    local_scale = np.maximum(d_cur, 1e-9)
    cap_term = 0.01 * (cap_gap / local_scale)
    cap_masked_max = float(np.max(cap_term[mask])) / denom if mask.any() else 0.0
    return {
        "base_median_abs": denom,
        "band_total_vs_base": band / denom,
        "demand_term_vs_base": float(np.max(1e-6 * dem)) / denom,
        "gated": gated,
        "cap_term_effective_vs_base": cap_masked_max if gated else 0.0,
        "cap_term_unconditional_vs_base": cap_masked_max,
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
    return round(num / den, 4) if den > 1e-12 else None


def audit(instance: Mapping[str, Any], fn: Callable[..., int]) -> dict[str, Any]:
    demands = np.asarray([0.0] + [float(d) for d in instance["demands"]], dtype=float)
    capacity = float(instance["capacity"])
    rows: dict[str, list[dict[str, Any]]] = {}
    for scale in SCALES:
        matrix = matrix_for(instance, scale)
        current, remaining = 0, capacity
        unvisited = set(range(1, demands.size))
        steps: list[dict[str, Any]] = []
        guard = 4 * demands.size + 16
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
        gated_caps = [s["cap_term_effective_vs_base"] for s in steps if s["gated"]]
        summary[scale_key] = {
            "steps": len(steps),
            "gated_steps": len(gated_caps),
            "gate_rate": float(len(gated_caps) / len(steps)),
            "band_total_vs_base_median": float(np.median([s["band_total_vs_base"] for s in steps])),
            "demand_term_vs_base_median": float(np.median([s["demand_term_vs_base"] for s in steps])),
            "cap_term_effective_vs_base_median": float(np.median([s["cap_term_effective_vs_base"] for s in steps])),
            "cap_term_when_gated_vs_base_median": float(np.median(gated_caps)) if gated_caps else 0.0,
            "cap_term_when_gated_vs_base_max": float(np.max(gated_caps)) if gated_caps else 0.0,
            "cap_term_unconditional_vs_base_median": float(np.median([s["cap_term_unconditional_vs_base"] for s in steps])),
            "near_tie_share": float(
                sum(s["near_tie_candidates"] for s in steps)
                / sum(s["branch_rate_denominator"] for s in steps)
            ),
        }
    keys = [k for k in ("1", "0.01", "0.001", "1000") if k in summary]
    scales = [float(k) for k in keys]
    exponents = {
        "band_total_vs_base": slope(scales, [summary[k]["band_total_vs_base_median"] for k in keys]),
        "cap_term_when_gated_vs_base": slope(scales, [summary[k]["cap_term_when_gated_vs_base_median"] for k in keys]),
        "demand_term_vs_base": slope(scales, [summary[k]["demand_term_vs_base_median"] for k in keys]),
    }
    return {"by_scale": summary, "exponents": exponents, "_raw_steps": rows}


def main() -> int:
    suite = json.loads(SUITE.read_text(encoding="utf-8"))
    instances = suite["instances"] if isinstance(suite, Mapping) else suite
    fn = load_c()
    per_instance_full = {str(item.get("instance_id")): audit(item, fn) for item in instances}

    pooled: dict[str, Any] = {}
    for scale_key in [f"{s:g}" for s in SCALES]:
        all_steps = [
            step
            for inst in per_instance_full.values()
            for step in inst["_raw_steps"].get(scale_key, [])
        ]
        if not all_steps:
            continue
        gated_caps = [s["cap_term_effective_vs_base"] for s in all_steps if s["gated"]]
        pooled[scale_key] = {
            "steps": len(all_steps),
            "gated_steps": len(gated_caps),
            "gate_rate": round(float(len(gated_caps) / len(all_steps)), 6),
            "band_total_vs_base_median": float(np.median([s["band_total_vs_base"] for s in all_steps])),
            "demand_term_vs_base_median": float(np.median([s["demand_term_vs_base"] for s in all_steps])),
            "cap_term_effective_vs_base_median": float(np.median([s["cap_term_effective_vs_base"] for s in all_steps])),
            "cap_term_when_gated_vs_base_median": float(np.median(gated_caps)) if gated_caps else 0.0,
            "cap_term_when_gated_vs_base_max": float(np.max(gated_caps)) if gated_caps else 0.0,
            "cap_term_unconditional_vs_base_median": float(np.median([s["cap_term_unconditional_vs_base"] for s in all_steps])),
            "near_tie_share": round(float(
                sum(s["near_tie_candidates"] for s in all_steps)
                / sum(s["branch_rate_denominator"] for s in all_steps)
            ), 6),
        }

    keys = [f"{s:g}" for s in SCALES if f"{s:g}" in pooled]
    scales = [float(k) for k in keys]

    # Direct 3-term ablation across all four scales on all 6 instances (50 customers each)
    ablation_rules = build_ablation_rules()
    ablation_by_scale: dict[str, dict[str, float]] = {}
    ablation_spread: dict[str, float] = {}
    for name, rule_fn in ablation_rules.items():
        per_scale: dict[str, float] = {}
        for scale in SCALES:
            vals = [simulate_objective(rule_fn, inst, scale) for inst in instances]
            per_scale[f"{scale:g}"] = round(float(np.mean(vals)), 6)
        ablation_by_scale[name] = per_scale
        vs = list(per_scale.values())
        ablation_spread[name] = round((max(vs) - min(vs)) / min(vs), 6)

    per_instance = {
        iid: {"by_scale": data["by_scale"], "exponents": data["exponents"]}
        for iid, data in per_instance_full.items()
    }
    report = {
        "script": "experiments/cvrp_midterm/analysis/scale_term_audit.py",
        "rule": FROZEN_C.relative_to(REPO).as_posix(),
        "suite": SUITE.relative_to(REPO).as_posix(),
        "instances": len(instances),
        "customers_per_instance": len(instances[0]["customer_coordinates"]),
        "scales": list(SCALES),
        "pooled_by_scale": pooled,
        "exponents": {
            "band_total_vs_base": slope(scales, [pooled[k]["band_total_vs_base_median"] for k in keys]),
            "cap_term_when_gated_vs_base": slope(scales, [pooled[k]["cap_term_when_gated_vs_base_median"] for k in keys]),
            "cap_term_unconditional_vs_base": slope(scales, [pooled[k]["cap_term_unconditional_vs_base_median"] for k in keys]),
            "demand_term_vs_base": slope(scales, [pooled[k]["demand_term_vs_base_median"] for k in keys]),
        },
        "ablation_normalized_objective": ablation_by_scale,
        "ablation_scale_spread": ablation_spread,
        "per_instance": per_instance,
    }
    OUT.write_bytes(json.dumps(report, ensure_ascii=False, indent=2).encode("utf-8") + b"\n")
    print(json.dumps({
        "pooled_by_scale": pooled,
        "exponents": report["exponents"],
        "ablation_normalized_objective": ablation_by_scale,
        "ablation_scale_spread": ablation_spread,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
