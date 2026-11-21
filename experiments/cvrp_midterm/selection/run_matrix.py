"""Task B prototype: instance regimes, algorithm portfolio, and selectors.

Builds three CVRP regimes, scores a small hand-written portfolio on every
instance with the real candidate evaluator, then asks whether the per-instance
best can be predicted from features measured *before* solving.

No provider calls are involved: this only exercises the deterministic evaluator.
"""

from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

import numpy as np  # noqa: E402

import agent_skill_loop.evaluator as evaluator  # noqa: E402

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
    saving = dep[unvisited_nodes] + dep[unvisited_nodes] - cur[unvisited_nodes]
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
}

FEATURE_NAMES = (
    "mean_demand", "cv_demand", "capacity_ratio", "cluster_tendency",
    "radial_std", "depot_eccentricity", "x_spread", "y_spread",
)


def _instance(index: int, regime: str, rng: random.Random, size: int, capacity: int, demands_lo: int, demands_hi: int):
    if regime == "uniform":
        depot = [0.5, 0.5]
        coords = [[rng.random(), rng.random()] for _ in range(size)]
    elif regime == "clustered":
        centres = [(rng.random(), rng.random()) for _ in range(4)]
        coords = []
        for _ in range(size):
            cx, cy = centres[rng.randrange(4)]
            coords.append([min(1.0, max(0.0, rng.gauss(cx, 0.06))), min(1.0, max(0.0, rng.gauss(cy, 0.06)))])
        depot = [0.5, 0.5]
    elif regime == "eccentric":
        depot = [0.05, 0.95]
        coords = [[rng.random(), rng.random()] for _ in range(size)]
    else:
        raise ValueError(regime)
    return {
        "instance_id": f"{regime}-{index}",
        "depot": [round(float(depot[0]), 8), round(float(depot[1]), 8)],
        "customer_coordinates": [[round(float(x), 8), round(float(y), 8)] for x, y in coords],
        "demands": [rng.randint(demands_lo, demands_hi) for _ in range(size)],
        "capacity": capacity,
    }


REGIMES = {
    "uniform": dict(size=50, capacity=40, demands=(1, 9)),
    "clustered": dict(size=50, capacity=40, demands=(1, 9)),
    "eccentric": dict(size=50, capacity=30, demands=(3, 9)),
}


def build_instances(per_regime: int = 12, seed: int = 20261121) -> list[dict]:
    out: list[dict] = []
    for regime, cfg in REGIMES.items():
        rng = random.Random(seed + sum(map(ord, regime)))
        for index in range(per_regime):
            item = _instance(index, regime, rng, cfg["size"], cfg["capacity"], *cfg["demands"])
            item["regime"] = regime
            out.append(item)
    return out


def features(instance: dict) -> dict[str, float]:
    depot = np.array(instance["depot"], dtype=float)
    coords = np.array(instance["customer_coordinates"], dtype=float)
    demands = np.array(instance["demands"], dtype=float)
    dist_depot = np.linalg.norm(coords - depot, axis=1)
    n = len(coords)
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
        "_n": float(n),
    }


def evaluate(name: str, instance: dict) -> dict:
    suite = {
        "problem": "cvrp_construct",
        "split": SPLIT,
        "instances": [instance],
    }
    suite["content_hash"] = __import__("agent_skill_loop.problems.cvrp", fromlist=["suite_hash"]).suite_hash(
        "cvrp_construct", SPLIT, suite["instances"]
    )
    result = evaluator.evaluate_candidate_request(
        {"problem": "cvrp_construct", "suite": suite, "code": ALGORITHMS[name]}
    )
    return {"valid": result["valid"], "objective": result.get("objective"), "error_code": result.get("error_code")}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    instances = build_instances()
    rows = []
    for inst in instances:
        feats = features(inst)
        row = {"instance_id": inst["instance_id"], "regime": inst["regime"], **feats}
        for name in ALGORITHMS:
            res = evaluate(name, inst)
            row[name] = res["objective"]
            if not res["valid"]:
                row[name] = None
                row[f"{name}_error"] = res["error_code"]
        rows.append(row)

    (OUT / "matrix.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")

    names = list(ALGORITHMS)
    import csv
    with (OUT / "matrix.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    def totals(pick) -> float:
        total = 0.0
        for row in rows:
            value = row[pick(row)]
            total += float(value)
        return total

    vbs = sum(min(row[n] for n in names if row[n] is not None) for row in rows)
    summary = {
        "instances": len(rows),
        "regimes": {regime: sum(1 for r in rows if r["regime"] == regime) for regime in REGIMES},
        "portfolio_mean": {n: round(sum(r[n] for r in rows if r[n] is not None) / len(rows), 6) for n in names},
        "sbs": {n: round(totals(lambda _r, n=n: n), 4) for n in names},
        "vbs_total": round(vbs, 4),
        "best_fixed": min(names, key=lambda n: totals(lambda _r, n=n: n)),
    }
    summary["sbs_total"] = summary["sbs"][summary["best_fixed"]]
    summary["sbs_gap_to_vbs"] = round((summary["sbs_total"] - vbs) / vbs, 6)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
