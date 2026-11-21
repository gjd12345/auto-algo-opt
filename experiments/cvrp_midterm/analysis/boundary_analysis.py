"""Stage 2A Mathematical Structure Analysis: CVRP Boundary & Regime Tracing.

Investigates two structural mechanisms of CVRP constructive priority rules:
1. Depot-start boundary (i = 0) phase transition for linear rules
   s_alpha(i, j) = d(i, j) - alpha * d(0, j):
   - At i = 0, s_alpha(0, j) = (1 - alpha) * d(0, j).
   - alpha < 1 => inside-out (nearest to depot first);
   - alpha > 1 => outside-in (farthest from depot first);
   - alpha = 1 => identically 0, completely controlled by the tie-breaker.
   Also tests decoupled (start_mode, alpha_mid) and counterfactual depot-start
   swaps on frozen rules A, B, C, V0, and savings (keeping all i != 0 steps identical).
2. Capacity-bucketed step-by-step tracing across scales n in {50, 100, 200}
   and spatial regimes {uniform, clustered}:
   - Buckets: start (i == 0), mid (i != 0 and rest_cap/Q > 0.35),
     near_full (i != 0 and rest_cap/Q <= 0.35).
   - Quantifies route count, mean fill ratio, outbound/mid/return leg shares,
     depot-start distance, and pairwise decision disagreement rate per bucket.

Uses freshly seeded synthetic analysis instances (seed 20261123) completely
disjoint from cvrp_construct_mini, P0 held-out suites, and selection_s2.
Zero LLM/provider calls.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import sys
from pathlib import Path
from typing import Callable

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

import numpy as np  # noqa: E402

import agent_skill_loop.evaluator as evaluator  # noqa: E402

OUT = REPO / "experiments/cvrp_midterm/analysis/boundary_analysis.json"
FROZEN_P0 = REPO / "reports/evidence/cvrp_p0_p1_p2_20261107/p0/frozen_code"
FROZEN_V0 = REPO / "reports/evidence/cvrp_p0_p1_p2_20261107/p1/V0.py"

ANALYSIS_SEED = 20261123
SIZES = (50, 100, 200)
SPATIALS = ("uniform", "clustered")
INSTANCES_PER_SLICE = 12  # 3 sizes * 2 spatials * 12 = 72 analysis instances
CAPACITY = 40
ALPHAS = (0.0, 0.3, 0.6, 0.8, 0.99, 1.0, 1.01, 1.2, 1.5, 2.0)


def _rng(seed: int, tag: str, index: int) -> random.Random:
    h = hashlib.sha256(f"{seed}|{tag}|{index}".encode()).hexdigest()
    return random.Random(int(h[:16], 16))


def build_analysis_instances() -> list[dict]:
    out: list[dict] = []
    for n in SIZES:
        for spatial in SPATIALS:
            tag = f"n{n}_{spatial}"
            for idx in range(INSTANCES_PER_SLICE):
                rng = _rng(ANALYSIS_SEED, tag, idx)
                if spatial == "uniform":
                    coords = [[rng.random(), rng.random()] for _ in range(n)]
                else:
                    centres = [(rng.random(), rng.random()) for _ in range(4)]
                    coords = []
                    for _ in range(n):
                        cx, cy = centres[rng.randrange(4)]
                        coords.append([
                            min(1.0, max(0.0, rng.gauss(cx, 0.06))),
                            min(1.0, max(0.0, rng.gauss(cy, 0.06))),
                        ])
                out.append({
                    "instance_id": f"{tag}-{idx}",
                    "size": n,
                    "spatial": spatial,
                    "depot": [0.5, 0.5],
                    "customer_coordinates": [[round(x, 8), round(y, 8)] for x, y in coords],
                    "demands": [rng.randint(1, 9) for _ in range(n)],
                    "capacity": CAPACITY,
                })
    return out


def compile_code(code: str, name: str) -> Callable:
    ns = {"np": np, "numpy": np, "math": math}
    exec(compile(code, f"rule_{name}", "exec"), ns)  # noqa: S102
    return ns["select_next_node"]


def load_rules() -> dict[str, Callable]:
    rules_src = {
        "nn": """
def select_next_node(current_node, depot, unvisited_nodes, rest_capacity, demands, distance_matrix):
    return int(unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])])
""",
        "savings": """
def select_next_node(current_node, depot, unvisited_nodes, rest_capacity, demands, distance_matrix):
    cur = distance_matrix[current_node]
    dep = distance_matrix[depot]
    saving = cur[depot] + dep[unvisited_nodes] - cur[unvisited_nodes]
    top = saving.max()
    tied = unvisited_nodes[saving == top]
    if tied.size > 1:
        return int(tied[np.argmax(dep[tied])])
    return int(unvisited_nodes[np.argmax(saving)])
""",
        "a": (FROZEN_P0 / "A.py").read_text(encoding="utf-8"),
        "b": (FROZEN_P0 / "B.py").read_text(encoding="utf-8"),
        "c": (FROZEN_P0 / "C.py").read_text(encoding="utf-8"),
        "v0": FROZEN_V0.read_text(encoding="utf-8"),
    }
    return {k: compile_code(v, k) for k, v in rules_src.items()}


def make_alpha_rule(alpha: float, depot_tie: str = "far") -> Callable:
    def select_next_node(current_node, depot, unvisited_nodes, rest_capacity, demands, distance_matrix):
        d_cur = distance_matrix[current_node][unvisited_nodes].astype(float)
        d_dep = distance_matrix[depot][unvisited_nodes].astype(float)
        score = d_cur - alpha * d_dep
        best = float(np.min(score))
        tied = np.nonzero(np.abs(score - best) <= 1e-12)[0]
        if tied.size > 1:
            if depot_tie == "far":
                pick = tied[int(np.argmax(d_dep[tied]))]
            elif depot_tie == "near":
                pick = tied[int(np.argmin(d_dep[tied]))]
            else:
                pick = tied[int(np.argmin(demands[unvisited_nodes[tied]]))]
            return int(unvisited_nodes[pick])
        return int(unvisited_nodes[int(np.argmin(score))])
    return select_next_node


def make_decoupled_alpha_rule(start_mode: str, alpha_mid: float) -> Callable:
    def select_next_node(current_node, depot, unvisited_nodes, rest_capacity, demands, distance_matrix):
        d_dep = distance_matrix[depot][unvisited_nodes].astype(float)
        if current_node == depot:
            if start_mode == "far":
                return int(unvisited_nodes[int(np.argmax(d_dep))])
            if start_mode == "near":
                return int(unvisited_nodes[int(np.argmin(d_dep))])
            if start_mode == "heavy_far":
                fill = demands[unvisited_nodes].astype(float) / max(float(rest_capacity), 1e-9)
                dmax = max(float(np.max(d_dep)), 1e-9)
                sc = (1.0 + 0.35 * fill * fill) * (1.0 + 0.20 * (d_dep / dmax))
                return int(unvisited_nodes[int(np.argmax(sc))])
            raise ValueError(start_mode)
        d_cur = distance_matrix[current_node][unvisited_nodes].astype(float)
        score = d_cur - alpha_mid * d_dep
        return int(unvisited_nodes[int(np.argmin(score))])
    return select_next_node


def wrap_depot_start(base_fn: Callable, start_mode: str) -> Callable:
    """Counterfactual wrapper: replace ONLY the i == depot decision."""
    def select_next_node(current_node, depot, unvisited_nodes, rest_capacity, demands, distance_matrix):
        if current_node == depot and start_mode != "native":
            d_dep = distance_matrix[depot][unvisited_nodes].astype(float)
            if start_mode == "far":
                return int(unvisited_nodes[int(np.argmax(d_dep))])
            if start_mode == "near":
                return int(unvisited_nodes[int(np.argmin(d_dep))])
            if start_mode == "min_demand":
                return int(unvisited_nodes[int(np.argmin(demands[unvisited_nodes]))])
            if start_mode == "heavy_far":
                fill = demands[unvisited_nodes].astype(float) / max(float(rest_capacity), 1e-9)
                dmax = max(float(np.max(d_dep)), 1e-9)
                sc = (1.0 + 0.35 * fill * fill) * (1.0 + 0.20 * (d_dep / dmax))
                return int(unvisited_nodes[int(np.argmax(sc))])
            raise ValueError(start_mode)
        return base_fn(current_node, depot, unvisited_nodes, rest_capacity, demands, distance_matrix)
    return select_next_node


def trace_instance(fn: Callable, inst: dict) -> dict:
    """Simulate CVRP construction matching evaluator._evaluate_cvrp_instances and collect telemetry."""
    coords = np.vstack([
        np.asarray(inst["depot"], dtype=float),
        np.asarray(inst["customer_coordinates"], dtype=float),
    ])
    dmat = np.linalg.norm(coords[:, None, :] - coords[None, :, :], axis=2)
    demands = np.asarray([0.0] + [float(d) for d in inst["demands"]], dtype=float)
    capacity = float(inst["capacity"])
    n = len(inst["demands"])

    unvisited = set(range(1, n + 1))
    current = 0
    rest_cap = capacity

    total_dist = 0.0
    outbound_dist = 0.0
    mid_dist = 0.0
    return_dist = 0.0
    routes = 0
    route_loads: list[float] = []
    current_load = 0.0
    start_dists: list[float] = []
    bucket_counts = {"start": 0, "mid": 0, "near_full": 0}
    step_states: list[tuple[str, int, float, tuple[int, ...], int]] = []

    while unvisited:
        feasible = np.array(sorted(u for u in unvisited if demands[u] <= rest_cap), dtype=int)
        if feasible.size == 0:
            if current == 0:
                raise RuntimeError("infeasible instance")
            return_dist += float(dmat[current, 0])
            total_dist += float(dmat[current, 0])
            route_loads.append(current_load)
            current = 0
            rest_cap = capacity
            current_load = 0.0
            continue

        if current == 0:
            bucket = "start"
        elif rest_cap / capacity > 0.35:
            bucket = "mid"
        else:
            bucket = "near_full"

        nxt = int(fn(current, 0, feasible, rest_cap, demands, dmat))
        if nxt == 0:
            if current == 0:
                raise RuntimeError("early return from depot")
            return_dist += float(dmat[current, 0])
            total_dist += float(dmat[current, 0])
            route_loads.append(current_load)
            current = 0
            rest_cap = capacity
            current_load = 0.0
            continue

        bucket_counts[bucket] += 1
        step_states.append((bucket, current, rest_cap, tuple(int(x) for x in feasible), nxt))
        leg = float(dmat[current, nxt])
        total_dist += leg
        if current == 0:
            routes += 1
            outbound_dist += leg
            start_dists.append(leg)
        else:
            mid_dist += leg
        unvisited.remove(nxt)
        rest_cap -= float(demands[nxt])
        current_load += float(demands[nxt])
        current = nxt

    if current != 0:
        return_dist += float(dmat[current, 0])
        total_dist += float(dmat[current, 0])
        route_loads.append(current_load)

    return {
        "total_dist": total_dist,
        "outbound_share": outbound_dist / max(total_dist, 1e-12),
        "mid_share": mid_dist / max(total_dist, 1e-12),
        "return_share": return_dist / max(total_dist, 1e-12),
        "routes": routes,
        "mean_utilization": float(np.mean(route_loads) / capacity) if route_loads else 0.0,
        "mean_start_dist": float(np.mean(start_dists)) if start_dists else 0.0,
        "bucket_counts": bucket_counts,
        "step_states": step_states,
        "dmat": dmat,
        "demands": demands,
    }


def main() -> int:
    instances = build_analysis_instances()
    rules = load_rules()

    for rname in ("nn", "savings", "a", "b", "c", "v0"):
        tr = [trace_instance(rules[rname], inst)["total_dist"] for inst in instances[:6]]
        ev_vals, _ = evaluator._evaluate_cvrp_instances(rules[rname], instances[:6])
        ev = float(np.mean(ev_vals))
        assert abs(float(np.mean(tr)) - ev) < 1e-9, (rname, float(np.mean(tr)), ev)

    alpha_sweep: dict[str, dict] = {}
    for alpha in ALPHAS:
        ties = ("far", "near") if abs(alpha - 1.0) < 1e-12 else ("far",)
        for tie in ties:
            label = f"alpha={alpha:.2f}" if len(ties) == 1 else f"alpha=1.00_tie_{tie}"
            fn = make_alpha_rule(alpha, depot_tie=tie)
            by_slice: dict[str, dict] = {}
            all_dists, all_starts, all_ret, all_routes = [], [], [], []
            for n in SIZES:
                for spatial in SPATIALS:
                    sub = [x for x in instances if x["size"] == n and x["spatial"] == spatial]
                    traces = [trace_instance(fn, inst) for inst in sub]
                    d_mean = float(np.mean([t["total_dist"] for t in traces]))
                    s_mean = float(np.mean([t["mean_start_dist"] for t in traces]))
                    r_mean = float(np.mean([t["return_share"] for t in traces]))
                    rt_mean = float(np.mean([t["routes"] for t in traces]))
                    by_slice[f"n{n}_{spatial}"] = {
                        "mean_obj": round(d_mean, 4),
                        "mean_start_dist": round(s_mean, 4),
                        "return_share": round(r_mean, 4),
                        "mean_routes": round(rt_mean, 2),
                    }
                    all_dists.extend(t["total_dist"] for t in traces)
                    all_starts.extend(t["mean_start_dist"] for t in traces)
                    all_ret.extend(t["return_share"] for t in traces)
                    all_routes.extend(t["routes"] for t in traces)
            alpha_sweep[label] = {
                "alpha": alpha,
                "depot_tie": tie,
                "overall_mean_obj": round(float(np.mean(all_dists)), 4),
                "overall_start_dist": round(float(np.mean(all_starts)), 4),
                "overall_return_share": round(float(np.mean(all_ret)), 4),
                "overall_mean_routes": round(float(np.mean(all_routes)), 2),
                "by_slice": by_slice,
            }

    decoupled_grid: dict[str, dict] = {}
    for start_mode in ("near", "far", "heavy_far"):
        for alpha_mid in (0.6, 0.8, 1.0, 1.2):
            key = f"start={start_mode}|mid={alpha_mid:.1f}"
            fn = make_decoupled_alpha_rule(start_mode, alpha_mid)
            by_slice = {}
            all_d = []
            for n in SIZES:
                for spatial in SPATIALS:
                    sub = [x for x in instances if x["size"] == n and x["spatial"] == spatial]
                    ds = [trace_instance(fn, inst)["total_dist"] for inst in sub]
                    by_slice[f"n{n}_{spatial}"] = round(float(np.mean(ds)), 4)
                    all_d.extend(ds)
            decoupled_grid[key] = {
                "start_mode": start_mode,
                "alpha_mid": alpha_mid,
                "overall_mean_obj": round(float(np.mean(all_d)), 4),
                "by_slice": by_slice,
            }

    counterfactual_swaps: dict[str, dict] = {}
    for rname in ("a", "b", "c", "v0", "savings"):
        counterfactual_swaps[rname] = {}
        for mode in ("native", "far", "near", "heavy_far", "min_demand"):
            fn = wrap_depot_start(rules[rname], mode)
            by_slice = {}
            all_d, all_s, all_ret = [], [], []
            for n in SIZES:
                for spatial in SPATIALS:
                    sub = [x for x in instances if x["size"] == n and x["spatial"] == spatial]
                    trs = [trace_instance(fn, inst) for inst in sub]
                    by_slice[f"n{n}_{spatial}"] = round(float(np.mean([t["total_dist"] for t in trs])), 4)
                    all_d.extend(t["total_dist"] for t in trs)
                    all_s.extend(t["mean_start_dist"] for t in trs)
                    all_ret.extend(t["return_share"] for t in trs)
            counterfactual_swaps[rname][mode] = {
                "overall_mean_obj": round(float(np.mean(all_d)), 4),
                "mean_start_dist": round(float(np.mean(all_s)), 4),
                "return_share": round(float(np.mean(all_ret)), 4),
                "by_slice": by_slice,
            }

    rule_telemetry: dict[str, dict] = {}
    for rname in ("nn", "savings", "a", "b", "c", "v0"):
        by_slice = {}
        for n in SIZES:
            for spatial in SPATIALS:
                sub = [x for x in instances if x["size"] == n and x["spatial"] == spatial]
                trs = [trace_instance(rules[rname], inst) for inst in sub]
                by_slice[f"n{n}_{spatial}"] = {
                    "mean_obj": round(float(np.mean([t["total_dist"] for t in trs])), 4),
                    "mean_routes": round(float(np.mean([t["routes"] for t in trs])), 2),
                    "mean_utilization": round(float(np.mean([t["mean_utilization"] for t in trs])), 4),
                    "mean_start_dist": round(float(np.mean([t["mean_start_dist"] for t in trs])), 4),
                    "outbound_share": round(float(np.mean([t["outbound_share"] for t in trs])), 4),
                    "mid_share": round(float(np.mean([t["mid_share"] for t in trs])), 4),
                    "return_share": round(float(np.mean([t["return_share"] for t in trs])), 4),
                }
        rule_telemetry[rname] = by_slice

    pairs = [("a", "b"), ("a", "savings"), ("b", "savings"), ("a", "c"), ("b", "c"), ("c", "v0")]
    bucket_disagreement: dict[str, dict] = {}
    for r1, r2 in pairs:
        pkey = f"{r1}_vs_{r2}"
        counts = {sp: {b: [0, 0] for b in ("start", "mid", "near_full")} for sp in SPATIALS}
        for inst in instances:
            tr = trace_instance(rules["savings"], inst)
            dmat = tr["dmat"]
            dem = tr["demands"]
            sp = inst["spatial"]
            for bucket, cur, rcap, feas_t, _ in tr["step_states"]:
                feas = np.asarray(feas_t, dtype=int)
                p1 = int(rules[r1](cur, 0, feas, rcap, dem, dmat))
                p2 = int(rules[r2](cur, 0, feas, rcap, dem, dmat))
                counts[sp][bucket][1] += 1
                if p1 != p2:
                    counts[sp][bucket][0] += 1
        bucket_disagreement[pkey] = {
            sp: {
                b: {
                    "disagree": counts[sp][b][0],
                    "total": counts[sp][b][1],
                    "rate": round(counts[sp][b][0] / max(counts[sp][b][1], 1), 4),
                }
                for b in ("start", "mid", "near_full")
            }
            for sp in SPATIALS
        }

    depot_start_audit: dict[str, dict] = {}
    for rname in ("nn", "savings", "a", "b", "c", "v0"):
        ranks_dist, ranks_dem = [], []
        for inst in instances:
            coords = np.vstack([
                np.asarray(inst["depot"], dtype=float),
                np.asarray(inst["customer_coordinates"], dtype=float),
            ])
            dmat = np.linalg.norm(coords[:, None, :] - coords[None, :, :], axis=2)
            dem = np.asarray([0.0] + [float(d) for d in inst["demands"]], dtype=float)
            feas = np.arange(1, len(inst["demands"]) + 1, dtype=int)
            pick = int(rules[rname](0, 0, feas, float(inst["capacity"]), dem, dmat))
            d_dep = dmat[0, 1:]
            q = dem[1:]
            r_dist = float(np.mean(d_dep < dmat[0, pick]) + 0.5 * np.mean(d_dep == dmat[0, pick]))
            r_dem = float(np.mean(q < dem[pick]) + 0.5 * np.mean(q == dem[pick]))
            ranks_dist.append(r_dist)
            ranks_dem.append(r_dem)
        depot_start_audit[rname] = {
            "mean_dist_percentile": round(float(np.mean(ranks_dist)), 4),
            "mean_demand_percentile": round(float(np.mean(ranks_dem)), 4),
        }

    payload = {
        "script": "experiments/cvrp_midterm/analysis/boundary_analysis.py",
        "seed": ANALYSIS_SEED,
        "instances": len(instances),
        "sizes": list(SIZES),
        "spatials": list(SPATIALS),
        "capacity": CAPACITY,
        "depot_start_audit": depot_start_audit,
        "alpha_sweep": alpha_sweep,
        "decoupled_grid": decoupled_grid,
        "counterfactual_swaps": counterfactual_swaps,
        "rule_telemetry": rule_telemetry,
        "bucket_disagreement": bucket_disagreement,
    }
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print("=== DEPOT-START PERCENTILE AUDIT (0=min, 1=max) ===")
    for k, v in depot_start_audit.items():
        print(f"  {k:8s}: dist_pct={v['mean_dist_percentile']:.4f}, dem_pct={v['mean_demand_percentile']:.4f}")
    print("\n=== ALPHA SWEEP (overall mean obj across 72 instances) ===")
    for k, v in alpha_sweep.items():
        print(f"  {k:22s}: obj={v['overall_mean_obj']:.4f}, start_d={v['overall_start_dist']:.4f}, ret_share={v['overall_return_share']:.4f}")
    print("\n=== COUNTERFACTUAL DEPOT-START SWAP (overall mean obj) ===")
    for rname, modes in counterfactual_swaps.items():
        row = " | ".join(f"{m}={modes[m]['overall_mean_obj']:.4f}" for m in ("native", "far", "near", "heavy_far"))
        print(f"  {rname:8s}: {row}")
    print("\n=== BUCKET DISAGREEMENT (A vs B) ===")
    print(json.dumps(bucket_disagreement["a_vs_b"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
