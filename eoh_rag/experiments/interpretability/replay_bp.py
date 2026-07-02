"""Replay BP Online best code and validate objective is real.

Runs the evolved score function against the official EoH BP Online evaluator
with multiple random seeds to confirm reproducibility and check for evaluator exploits.
"""

import json
import numpy as np
from pathlib import Path


BEST_CODE = """
def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    utilization = np.exp(item / (residual + item + 1e-9))
    penalty = np.where((residual > 0) & (residual < 2 * item), (residual - item) ** 2 / (item + 1e-9), 0)
    return utilization - penalty
"""


def make_score_fn():
    """Compile the evolved score function."""
    ns = {"np": np}
    exec(BEST_CODE, ns)
    return ns["score"]


def simulate_bp_online(score_fn, items, capacity=100):
    """Simulate online bin packing using the score function.

    Returns dict with objective (waste_ratio), bins_used, stats.
    """
    bins = []  # list of remaining capacities
    invalid_placements = 0
    overflow_count = 0
    nan_count = 0
    inf_count = 0

    for item in items:
        if not bins:
            bins.append(capacity - item)
            continue

        bins_arr = np.array(bins, dtype=np.float64)
        feasible_mask = bins_arr >= item
        feasible_indices = np.where(feasible_mask)[0]

        if len(feasible_indices) == 0:
            bins.append(capacity - item)
            continue

        feasible_bins = bins_arr[feasible_indices]
        scores = score_fn(item, feasible_bins)

        # Sanity checks
        if np.any(np.isnan(scores)):
            nan_count += 1
            scores = np.nan_to_num(scores, nan=-1e18)
        if np.any(np.isinf(scores)):
            inf_count += 1
            scores = np.nan_to_num(scores, posinf=1e18, neginf=-1e18)

        best_idx = feasible_indices[np.argmax(scores)]
        bins[best_idx] -= item

        if bins[best_idx] < 0:
            overflow_count += 1
            invalid_placements += 1

    total_capacity = len(bins) * capacity
    total_items = sum(items)
    waste = total_capacity - total_items
    waste_ratio = waste / total_capacity if total_capacity > 0 else 0

    return {
        "objective": round(waste_ratio, 8),
        "bins_used": len(bins),
        "total_items_placed": len(items),
        "waste_ratio": waste_ratio,
        "invalid_placements": invalid_placements,
        "overflow_count": overflow_count,
        "nan_count": nan_count,
        "inf_count": inf_count,
    }


def generate_weibull_items(n=5000, shape=3.0, scale=45.0, capacity=100, seed=42):
    """Generate items from Weibull distribution (same as EoH/FunSearch benchmark)."""
    rng = np.random.default_rng(seed)
    raw = rng.weibull(shape, size=n) * scale
    items = np.clip(np.round(raw).astype(int), 1, capacity)
    return items.tolist()


def run_replay(n_seeds=20):
    """Run replay with multiple seeds."""
    score_fn = make_score_fn()
    results = []

    for seed in range(n_seeds):
        items = generate_weibull_items(seed=seed)
        result = simulate_bp_online(score_fn, items)
        result["seed"] = seed
        results.append(result)

    objectives = [r["objective"] for r in results]
    summary = {
        "n_seeds": n_seeds,
        "mean_objective": round(np.mean(objectives), 8),
        "std_objective": round(np.std(objectives), 8),
        "min_objective": round(np.min(objectives), 8),
        "max_objective": round(np.max(objectives), 8),
        "median_objective": round(np.median(objectives), 8),
        "total_invalid_placements": sum(r["invalid_placements"] for r in results),
        "total_overflow_count": sum(r["overflow_count"] for r in results),
        "total_nan_count": sum(r["nan_count"] for r in results),
        "total_inf_count": sum(r["inf_count"] for r in results),
        "all_results": results,
    }
    return summary


if __name__ == "__main__":
    summary = run_replay(n_seeds=20)
    print(f"Mean: {summary['mean_objective']:.6f} ± {summary['std_objective']:.6f}")
    print(f"Range: [{summary['min_objective']:.6f}, {summary['max_objective']:.6f}]")
    print(f"Invalid: {summary['total_invalid_placements']}, Overflow: {summary['total_overflow_count']}")
    print(f"NaN: {summary['total_nan_count']}, Inf: {summary['total_inf_count']}")

    out = Path("evidence/bp_interpretability/replay_results.json")
    out.write_text(json.dumps(summary, indent=2))
    print(f"\nSaved to {out}")
