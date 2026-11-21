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

No provider calls are involved: this only exercises the deterministic evaluator.
"""

from __future__ import annotations

import csv
import hashlib
import json
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

import numpy as np  # noqa: E402

import agent_skill_loop.evaluator as evaluator  # noqa: E402
from agent_skill_loop.problems.cvrp import suite_hash  # noqa: E402

OUT = REPO / "experiments/cvrp_midterm/selection"
SPLIT = "dev_train"

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
PORTFOLIOS = {"core": CORE, "extended": EXTENDED}

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


def evaluate(name: str, instance: dict) -> dict:
    suite = {"problem": "cvrp_construct", "split": SPLIT, "instances": [instance]}
    suite["content_hash"] = suite_hash("cvrp_construct", SPLIT, suite["instances"])
    result = evaluator.evaluate_candidate_request(
        {"problem": "cvrp_construct", "suite": suite, "code": ALGORITHMS[name]}
    )
    return {"valid": result["valid"], "objective": result.get("objective"), "error_code": result.get("error_code")}


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


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rule_check = check_savings_rule()
    instances = build_instances()
    rows = []
    for inst in instances:
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
            if not res["valid"]:
                row[name] = None
                row[f"{name}_error"] = res["error_code"]
        winners = [n for n in ALGORITHMS if row[n] is not None]
        row["oracle_all"] = min(winners, key=lambda n: (row[n], n))
        row["vbs_all"] = row[row["oracle_all"]]
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
        return {
            "instances": len(subset),
            "members": list(members),
            "vbs": round(vbs, 4),
            "sbs": round(totals[best], 4),
            "sbs_algorithm": best,
            "sbs_gap_to_vbs": round((totals[best] - vbs) / vbs, 6),
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
        },
        "instances": len(rows),
        "portfolio_mean": {
            n: round(float(np.mean([r[n] for r in rows])), 6) for n in names
        },
        "portfolios": portfolios,
        "per_cell": per_cell,
        "main_effects": main_effects,
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
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
