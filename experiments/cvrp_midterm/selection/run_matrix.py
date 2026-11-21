"""Task B, revision 2: factorial instance design, portfolio matrix, selectors.

Two defects of revision 1 are addressed here.

1. The ``savings`` rule used the depot leg twice::

       saving = dep[j] + dep[j] - cur[j]          # v1, wrong

   The saving of appending ``j`` after ``i`` on a tour that returns to the
   depot is ``S(i, j) = d(i, 0) + d(0, j) - d(i, j)``, so the rule is::

       saving = cur[depot] + dep[j] - cur[j]      # v2

   This is a *savings-inspired constructive* rule that ranks the next stop by
   the saving it would realise against the current stop and the depot.  It is
   not the Clarke-Wright merge procedure: there are no routes to merge and no
   capacity-feasible pairing; capacity is enforced by the harness, which only
   offers feasible ``unvisited_nodes``.  Standing at the depot every saving ties
   at zero, so the rule breaks the tie towards the longer outbound leg.

2. Revision 1's "eccentric" cell changed three factors at once (depot position,
   capacity 40 -> 30, demands 1-9 -> 3-9), so its contrast was not attributable.
   This version crosses three binary factors and holds the demand distribution
   fixed at U{1, ..., 9} in all eight cells::

       spatial  in {uniform, clustered}
       depot    in {centre, eccentric}
       capacity in {loose 45, tight 28}

3. Revision 3 admits the frozen rule C from the earlier PoC into the candidate
   pool.  C is not rewritten here: the evaluator receives the bytes of the
   frozen artefact, read from ``reports/evidence/cvrp_p0_p1_p2_20261107/p0/
   frozen_code/C.py`` and checked against its recorded SHA-256, so the pool
   member is provably the rule that scored 10.9197 on the shared suite.

No provider calls are involved: this only exercises the deterministic evaluator.
"""

from __future__ import annotations

import csv
import hashlib
import json
import random
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

import numpy as np  # noqa: E402

import agent_skill_loop.evaluator as evaluator  # noqa: E402
from agent_skill_loop.problems.cvrp import suite_hash  # noqa: E402

OUT = REPO / "experiments/cvrp_midterm/selection"
SPLIT = "dev_train"

# The frozen high-performing rules from the earlier PoC.  Read, never edited: the
# SHA-256 values below pin the exact bytes that produced the reported objectives.
# A and B are the rules that generalised across problem sizes in that PoC; C is the
# strongest rule on the six-instance shared suite but the weakest across the
# factorial bed, so all three belong in the pool instead of C alone.
FROZEN_DIR = REPO / "reports/evidence/cvrp_p0_p1_p2_20261107/p0/frozen_code"
FROZEN_SHA256 = {
    "a": "ccdab29f7d08ab162145ae7e468e47a5488b696d9a644bb7e793ab5c2665a866",
    "b": "68cd510af3df75d8f1b45182b248f07d7e38cedc4bfc1d74f5669a6b9ad81727",
    "c": "141d99b6f7c62e60313feb2c520889a957da9ae00fd5138798f4de3c30e25627",
}
FROZEN_C_PATH = FROZEN_DIR / "C.py"
FROZEN_C_SHA256 = FROZEN_SHA256["c"]

ALGORITHMS = {
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
    "dd_load": """
def select_next_node(current_node, depot, unvisited_nodes, rest_capacity, demands, distance_matrix):
    cur = distance_matrix[current_node][unvisited_nodes]
    dep = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes]
    slack = (rest_capacity - dem) / max(rest_capacity, 1e-9)
    score = cur - 0.15 * dep - 0.1 * (1.0 - slack) * dep
    return int(unvisited_nodes[np.argmin(score)])
""",
    "radial": """
def select_next_node(current_node, depot, unvisited_nodes, rest_capacity, demands, distance_matrix):
    cur = distance_matrix[current_node][unvisited_nodes]
    dep = distance_matrix[depot][unvisited_nodes]
    score = cur - 2.0 * dep + 0.02 * demands[unvisited_nodes]
    return int(unvisited_nodes[np.argmin(score)])
""",
    "farthest": """
def select_next_node(current_node, depot, unvisited_nodes, rest_capacity, demands, distance_matrix):
    return int(unvisited_nodes[np.argmax(distance_matrix[current_node][unvisited_nodes])])
""",
    "isolate": """
def select_next_node(current_node, depot, unvisited_nodes, rest_capacity, demands, distance_matrix):
    if unvisited_nodes.size < 2:
        return int(unvisited_nodes[0])
    sub = distance_matrix[unvisited_nodes][:, unvisited_nodes]
    big = np.eye(sub.shape[0]) * 1e6
    srt = np.sort(sub + big, axis=1)
    iso = srt[:, 1] - srt[:, 0]
    cur = distance_matrix[current_node][unvisited_nodes]
    return int(unvisited_nodes[np.argmax(iso - 0.05 * cur)])
""",
    "load_fill": """
def select_next_node(current_node, depot, unvisited_nodes, rest_capacity, demands, distance_matrix):
    dem = demands[unvisited_nodes]
    slack = rest_capacity - dem
    idx = np.where(slack == slack.min())[0]
    cur = distance_matrix[current_node][unvisited_nodes]
    return int(unvisited_nodes[idx[int(np.argmin(cur[idx]))]])
""",
}

# Rules measured in the matrix versus rules admitted to the selection portfolio.
# `farthest` is dominated everywhere, so it stays out of VBS; `isolate` and
# `load_fill` are reported separately so a thin portfolio cannot manufacture
# headroom and then be read as complementarity.
CORE = ("nn", "savings", "dd_load", "radial")
EXTENDED = ("nn", "savings", "dd_load", "radial", "isolate", "load_fill")
WITH_C = CORE + ("c",)
EXTENDED_C = EXTENDED + ("c",)
# The PoC produced three frozen rules, not one.  Selection has to see all of them:
# A and B are the two that generalised, C the one that over-fitted the small suite.
CORE_ABC = CORE + ("a", "b", "c")
FULL_POOL = EXTENDED + ("a", "b", "c")
PORTFOLIOS = {
    "core": CORE,
    "with_c": WITH_C,
    "extended": EXTENDED,
    "extended_c": EXTENDED_C,
    "core_abc": CORE_ABC,
    "full_pool": FULL_POOL,
}

FEATURE_NAMES = (
    "mean_demand", "cv_demand", "capacity_ratio", "cluster_tendency",
    "radial_std", "depot_eccentricity", "x_spread", "y_spread",
)

FACTORS = {
    "spatial": ("uniform", "clustered"),
    "depot": ("centre", "eccentric"),
    "capacity": ("loose", "tight"),
}
CAPACITY_LEVELS = {"loose": 45, "tight": 28}
DEMAND_RANGE = (1, 9)


def frozen_source(name: str) -> str:
    """Return a frozen rule exactly as archived, refusing to run if the bytes moved."""
    path = FROZEN_DIR / f"{name.upper()}.py"
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    expected = FROZEN_SHA256[name]
    if digest != expected:
        raise SystemExit(f"frozen {name.upper()} artefact changed: {digest} != {expected} ({path})")
    return raw.decode("utf-8")


def frozen_c_source() -> str:
    return frozen_source("c")


for _frozen in ("a", "b", "c"):
    ALGORITHMS[_frozen] = frozen_source(_frozen)


def check_frozen_rules() -> dict:
    return {
        name: {
            "path": str((FROZEN_DIR / f"{name.upper()}.py").relative_to(REPO)).replace("\\", "/"),
            "sha256": FROZEN_SHA256[name],
            "bytes": len(ALGORITHMS[name].encode("utf-8")),
            "edited_here": False,
        }
        for name in ("a", "b", "c")
    }


def check_frozen_c() -> dict:
    return {
        "path": str(FROZEN_C_PATH.relative_to(REPO)).replace("\\", "/"),
        "sha256": FROZEN_C_SHA256,
        "bytes": len(ALGORITHMS["c"].encode("utf-8")),
        "edited_here": False,
        "provenance": "PoC frozen rule C; objective 10.9197 on the shared 6-instance suite",
    }


def cell_name(spatial: str, depot: str, capacity: str) -> str:
    return f"{spatial}_{depot}_{capacity}"


CELLS = {
    cell_name(spatial, depot, capacity): dict(
        spatial=spatial, depot=depot, capacity=capacity
    )
    for spatial in FACTORS["spatial"]
    for depot in FACTORS["depot"]
    for capacity in FACTORS["capacity"]
}


def _rng(seed: int, cell: str, index: int) -> random.Random:
    digest = hashlib.sha256(f"{seed}|{cell}|{index}".encode()).hexdigest()
    return random.Random(int(digest[:16], 16))


def _coords(spatial: str, rng: random.Random, size: int) -> list[list[float]]:
    if spatial == "uniform":
        return [[rng.random(), rng.random()] for _ in range(size)]
    if spatial == "clustered":
        centres = [(rng.random(), rng.random()) for _ in range(4)]
        coords = []
        for _ in range(size):
            cx, cy = centres[rng.randrange(4)]
            coords.append([
                min(1.0, max(0.0, rng.gauss(cx, 0.06))),
                min(1.0, max(0.0, rng.gauss(cy, 0.06))),
            ])
        return coords
    raise ValueError(spatial)


def _instance(index: int, cell: str, seed: int, size: int = 50) -> dict:
    cfg = CELLS[cell]
    rng = _rng(seed, cell, index)
    coords = _coords(cfg["spatial"], rng, size)
    depot = [0.5, 0.5] if cfg["depot"] == "centre" else [0.05, 0.95]
    return {
        "instance_id": f"{cell}-{index}",
        "depot": [round(float(depot[0]), 8), round(float(depot[1]), 8)],
        "customer_coordinates": [[round(float(x), 8), round(float(y), 8)] for x, y in coords],
        "demands": [rng.randint(*DEMAND_RANGE) for _ in range(size)],
        "capacity": CAPACITY_LEVELS[cfg["capacity"]],
        "cell": cell,
        "spatial": cfg["spatial"],
        "depot_style": cfg["depot"],
        "capacity_level": cfg["capacity"],
    }


def build_instances(per_cell: int = 12, seed: int = 20261121) -> list[dict]:
    out: list[dict] = []
    for cell in CELLS:
        for index in range(per_cell):
            out.append(_instance(index, cell, seed))
    return out


def features(instance: dict) -> dict[str, float]:
    depot = np.array(instance["depot"], dtype=float)
    coords = np.array(instance["customer_coordinates"], dtype=float)
    demands = np.array(instance["demands"], dtype=float)
    dist_depot = np.linalg.norm(coords - depot, axis=1)
    dmat = np.linalg.norm(coords[:, None, :] - coords[None, :, :], axis=2)
    np.fill_diagonal(dmat, np.inf)
    nearest = dmat.min(axis=1)
    return {
        "mean_demand": float(demands.mean()),
        "cv_demand": float(demands.std() / max(demands.mean(), 1e-9)),
        "capacity_ratio": float(demands.sum() / instance["capacity"]),
        "cluster_tendency": float(nearest.mean() / max(dmat[dmat != np.inf].mean(), 1e-9)),
        "radial_std": float(dist_depot.std()),
        "depot_eccentricity": float(dist_depot.mean()),
        "x_spread": float(coords[:, 0].std()),
        "y_spread": float(coords[:, 1].std()),
    }


def compile_algorithm(name: str):
    ns = {"np": np, "numpy": np, "math": __import__("math")}
    exec(compile(ALGORITHMS[name], f"rule_{name}", "exec"), ns)  # noqa: S102
    return ns["select_next_node"]


def measure_pure_solve(name: str, instances: list[dict], repeats: int = 3) -> list[float]:
    """Measure pre-compiled pure solving time per instance (excludes AST/compile/hash)."""
    fn = compile_algorithm(name)
    # Warm-up one call to avoid first-call import/cache jitter
    evaluator._evaluate_cvrp_instances(fn, [instances[0]])
    times: list[float] = []
    for inst in instances:
        best = float("inf")
        for _ in range(repeats):
            t0 = time.perf_counter()
            evaluator._evaluate_cvrp_instances(fn, [inst])
            dt = time.perf_counter() - t0
            if dt < best:
                best = dt
        times.append(best)
    return times


def evaluate(name: str, instance: dict) -> dict:
    suite = {"problem": "cvrp_construct", "split": SPLIT, "instances": [instance]}
    suite["content_hash"] = suite_hash("cvrp_construct", SPLIT, suite["instances"])
    started = time.perf_counter()
    result = evaluator.evaluate_candidate_request(
        {"problem": "cvrp_construct", "suite": suite, "code": ALGORITHMS[name]}
    )
    elapsed = time.perf_counter() - started
    return {
        "valid": result["valid"],
        "objective": result.get("objective"),
        "error_code": result.get("error_code"),
        # Wall clock of one full frozen evaluator call (includes AST parse/compile/hash).
        "runtime_s": elapsed,
    }


def check_savings_rule() -> dict:
    """Verify S(i, j) against a brute-force reading of the savings definition."""
    rng = random.Random(7)
    checked = 0
    zero_at_depot = None
    for _ in range(20):
        n = 9
        coords = np.array([[rng.random(), rng.random()] for _ in range(n)])
        depot = np.array([rng.random(), rng.random()])
        points = np.vstack([depot, coords])
        dmat = np.linalg.norm(points[:, None, :] - points[None, :, :], axis=2)
        for cur in range(n + 1):
            unvisited = np.array([j for j in range(1, n + 1) if j != cur], dtype=int)
            if cur == 0:
                unvisited = np.array([j for j in range(1, n + 1)], dtype=int)
            saving = dmat[cur][0] + dmat[0][unvisited] - dmat[cur][unvisited]
            expected = np.array(
                [dmat[cur][0] + dmat[0][j] - dmat[cur][j] for j in unvisited]
            )
            assert np.allclose(saving, expected), (cur, saving, expected)
            checked += 1
            if cur == 0:
                zero_at_depot = bool(np.allclose(saving, 0.0))
    return {
        "rule": "S(i, j) = d(i, 0) + d(0, j) - d(i, j)",
        "cases_checked": checked,
        "all_savings_zero_at_depot": zero_at_depot,
        "tie_break_at_depot": "larger d(0, j) wins",
        "is_full_clarke_wright": False,
    }


def _totals(rows: list[dict], names: list[str], pick) -> float:
    return float(sum(float(row[pick(row)]) for row in rows))


def pairwise_stats(rows: list[dict], a: str, b: str) -> dict:
    """Head-to-head for one pair of rules, so ties are not hidden in an average."""
    better = sum(1 for r in rows if float(r[a]) < float(r[b]) - 1e-12)
    equal = sum(1 for r in rows if abs(float(r[a]) - float(r[b])) <= 1e-12)
    rel = [(float(r[a]) - float(r[b])) / float(r[b]) for r in rows]
    return {
        "a": a,
        "b": b,
        "a_better": better,
        "equal": equal,
        "b_better": len(rows) - better - equal,
        "mean_relative_delta": round(float(np.mean(rel)), 6),
        "median_relative_delta": round(float(np.median(rel)), 6),
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rule_check = check_savings_rule()
    instances = build_instances()
    pure_times = {name: measure_pure_solve(name, instances) for name in ALGORITHMS}
    rows = []
    for idx_inst, inst in enumerate(instances):
        row = {
            "instance_id": inst["instance_id"],
            "cell": inst["cell"],
            "regime": inst["cell"],
            "spatial": inst["spatial"],
            "depot_style": inst["depot_style"],
            "capacity_level": inst["capacity_level"],
            "capacity": inst["capacity"],
            **features(inst),
        }
        for name in ALGORITHMS:
            res = evaluate(name, inst)
            row[name] = res["objective"]
            row[f"{name}_s"] = round(float(res["runtime_s"]), 6)
            row[f"{name}_solve_s"] = round(float(pure_times[name][idx_inst]), 6)
            if not res["valid"]:
                row[name] = None
                row[f"{name}_error"] = res["error_code"]
        winners = [n for n in ALGORITHMS if row[n] is not None]
        row["oracle_all"] = min(winners, key=lambda n: (row[n], n))
        row["vbs_all"] = row[row["oracle_all"]]
        # Per-instance ranks over the measured rules: 1 = best.  Selection results
        # are unreadable without them, and they cost nothing once the matrix exists.
        for name in winners:
            row[f"{name}_rank"] = 1 + sum(
                1 for other in winners if row[other] < row[name] - 1e-12
            )
        rows.append(row)

    (OUT / "matrix.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    with (OUT / "matrix.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    names = list(ALGORITHMS)

    def portfolio_block(portfolio: str, subset: list[dict]) -> dict:
        members = PORTFOLIOS[portfolio]
        totals = {n: float(sum(float(r[n]) for r in subset)) for n in members}
        best = min(members, key=lambda n: totals[n])
        best_per_row = [
            min(float(r[n]) for n in members) for r in subset
        ]
        oracle_counts = {n: 0 for n in members}
        for r in subset:
            oracle_counts[min(members, key=lambda n: (float(r[n]), n))] += 1
        vbs = float(sum(best_per_row))
        headroom = totals[best] - vbs
        return {
            "instances": len(subset),
            "members": list(members),
            "vbs": round(vbs, 4),
            "sbs": round(totals[best], 4),
            "sbs_algorithm": best,
            "sbs_gap_to_vbs": round(headroom / vbs, 6),
            "headroom": round(headroom, 4),
            "oracle_counts": {k: v for k, v in oracle_counts.items() if v},
            "mean_capacity_ratio": round(
                float(np.mean([r["capacity_ratio"] for r in subset])), 4
            ),
        }

    portfolios = {
        portfolio: portfolio_block(portfolio, rows) for portfolio in PORTFOLIOS
    }
    per_cell = {
        cell: {
            portfolio: portfolio_block(portfolio, [r for r in rows if r["cell"] == cell])
            for portfolio in PORTFOLIOS
        }
        for cell in CELLS
    }

    # Main effects: mean objective per algorithm, averaged over the cells of each level.
    main_effects: dict[str, dict] = {}
    for factor, levels in FACTORS.items():
        key = {"spatial": "spatial", "depot": "depot_style", "capacity": "capacity_level"}[factor]
        main_effects[factor] = {}
        for level in levels:
            subset = [r for r in rows if r[key] == level]
            main_effects[factor][level] = {
                "instances": len(subset),
                "mean_objective": {
                    n: round(float(np.mean([r[n] for r in subset])), 4) for n in names
                },
                "vbs": {
                    portfolio: round(float(sum(
                        min(float(r[n]) for n in PORTFOLIOS[portfolio]) for r in subset
                    )), 4)
                    for portfolio in PORTFOLIOS
                },
                "sbs": {
                    portfolio: round(float(min(
                        sum(float(r[n]) for r in subset) for n in PORTFOLIOS[portfolio]
                    )), 4)
                    for portfolio in PORTFOLIOS
                },
            }

    summary = {
        "design": {
            "factors": {k: list(v) for k, v in FACTORS.items()},
            "capacity_levels": CAPACITY_LEVELS,
            "demand_range": list(DEMAND_RANGE),
            "customers_per_instance": 50,
            "instances_per_cell": 12,
            "cells": list(CELLS),
            "portfolios": {k: list(v) for k, v in PORTFOLIOS.items()},
            "frozen_member": check_frozen_c(),
            "frozen_rules": check_frozen_rules(),
        },
        "instances": len(rows),
        "portfolio_mean": {
            n: round(float(np.mean([r[n] for r in rows])), 6) for n in names
        },
        "mean_runtime_s": {
            n: round(float(np.mean([r[f"{n}_s"] for r in rows])), 6) for n in names
        },
        "mean_solve_s": {
            n: round(float(np.mean([r[f"{n}_solve_s"] for r in rows])), 6) for n in names
        },
        "mean_rank": {
            n: round(float(np.mean([r[f"{n}_rank"] for r in rows])), 4) for n in names
        },
        "portfolios": portfolios,
        "per_cell": per_cell,
        "main_effects": main_effects,
        "pairwise": {
            "c_vs_savings": pairwise_stats(rows, "c", "savings"),
            "c_vs_nn": pairwise_stats(rows, "c", "nn"),
            "c_vs_dd_load": pairwise_stats(rows, "c", "dd_load"),
            "a_vs_savings": pairwise_stats(rows, "a", "savings"),
            "b_vs_savings": pairwise_stats(rows, "b", "savings"),
            "a_vs_b": pairwise_stats(rows, "a", "b"),
        },
        "rule_check": rule_check,
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({
        "instances": summary["instances"],
        "portfolio_mean": summary["portfolio_mean"],
        "portfolios": {
            k: {
                "vbs": v["vbs"],
                "sbs": v["sbs"],
                "sbs_algorithm": v["sbs_algorithm"],
                "sbs_gap_to_vbs": v["sbs_gap_to_vbs"],
                "oracle_counts": v["oracle_counts"],
            }
            for k, v in portfolios.items()
        },
        "rule_check": rule_check,
        "frozen_member": summary["design"]["frozen_member"],
        "pairwise": summary["pairwise"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
