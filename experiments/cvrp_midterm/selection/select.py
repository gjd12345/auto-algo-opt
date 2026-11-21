"""Instance-level algorithm selection on the regime matrix.

Question set (task B):
  1. Is there complementarity?  Compare the best single algorithm (SBS) with the
     per-instance oracle (VBS).
  2. Is the oracle predictable from pre-solve features?  Leave-one-out within the
     pool, then leave-one-regime-out across pools.
  3. Does a selector beat the fixed choice after its own overhead?  Report total
     distance, regret against VBS, and the training cost in solver calls.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

import numpy as np  # noqa: E402

OUT = REPO / "experiments/cvrp_midterm/selection"
SERIOUS = ("nn", "savings", "dd_load", "radial")
FEATURES = ("mean_demand", "cv_demand", "capacity_ratio", "cluster_tendency",
            "radial_std", "depot_eccentricity", "x_spread", "y_spread")


def load():
    rows = json.loads((OUT / "matrix.json").read_text(encoding="utf-8"))
    X = np.array([[r[f] for f in FEATURES] for r in rows], dtype=float)
    Y = np.array([[r[a] for a in SERIOUS] for r in rows], dtype=float)
    regimes = [r["regime"] for r in rows]
    return rows, X, Y, regimes


def standardize(train_x: np.ndarray, apply_x: np.ndarray):
    mu = train_x.mean(axis=0)
    sd = train_x.std(axis=0)
    sd[sd < 1e-12] = 1.0
    return (train_x - mu) / sd, (apply_x - mu) / sd


def ridge_fit(x: np.ndarray, y: np.ndarray, lam: float = 1.0) -> np.ndarray:
    xb = np.hstack([np.ones((x.shape[0], 1)), x])
    reg = lam * np.eye(xb.shape[1])
    reg[0, 0] = 0.0
    return np.linalg.solve(xb.T @ xb + reg, xb.T @ y)


def ridge_predict(w: np.ndarray, x: np.ndarray) -> np.ndarray:
    xb = np.hstack([np.ones((x.shape[0], 1)), x])
    return xb @ w


def totals(picks, Y) -> float:
    return float(sum(Y[i, j] for i, j in enumerate(picks)))


def report(name: str, picks, Y, vbs: float, extra: dict | None = None) -> dict:
    total = totals(picks, Y)
    out = {
        "selector": name,
        "total_objective": round(total, 4),
        "gap_to_vbs": round((total - vbs) / vbs, 6),
        "picks": {SERIOUS[j]: int(sum(1 for p in picks if p == j)) for j in range(len(SERIOUS))},
    }
    if extra:
        out.update(extra)
    return out


def main() -> int:
    rows, X, Y, regimes = load()
    n = len(rows)
    vbs = float(Y.min(axis=1).sum())
    sbs_pick = int(Y.sum(axis=0).argmin())
    fixed = [sbs_pick] * n

    results = [report("fixed_best_sbs", fixed, Y, vbs, {"algorithm": SERIOUS[sbs_pick]})]

    # 1-NN on standardized features, leave-one-out.
    picks_nn = []
    for i in range(n):
        mask = np.arange(n) != i
        train_x, test_x = standardize(X[mask], X[i:i + 1])
        dist = np.linalg.norm(train_x - test_x, axis=1)
        picks_nn.append(int(Y[mask][int(dist.argmin())].argmin()))
    results.append(report("knn1_loo", picks_nn, Y, vbs))

    # Ridge per algorithm, leave-one-out.
    picks_ridge = []
    for i in range(n):
        mask = np.arange(n) != i
        train_x, test_x = standardize(X[mask], X[i:i + 1])
        w = ridge_fit(train_x, Y[mask])
        picks_ridge.append(int(ridge_predict(w, test_x)[0].argmin()))
    results.append(report("ridge_loo", picks_ridge, Y, vbs))

    # Leave-one-regime-out: train on the other two pools, test on the held-out one.
    loro = []
    for regime in sorted(set(regimes)):
        test_idx = [i for i, r in enumerate(regimes) if r == regime]
        train_idx = [i for i, r in enumerate(regimes) if r != regime]
        train_x, test_x = standardize(X[train_idx], X[test_idx])
        w = ridge_fit(train_x, Y[train_idx])
        pred = ridge_predict(w, test_x)
        picks = [int(p.argmin()) for p in pred]
        loro.extend(zip(test_idx, picks))
    loro_sorted = [p for _, p in sorted(loro)]
    results.append(report("ridge_loro", loro_sorted, Y, vbs))

    per_regime = {}
    for regime in sorted(set(regimes)):
        idx = [i for i, r in enumerate(regimes) if r == regime]
        sub_y = Y[idx]
        sub_vbs = float(sub_y.min(axis=1).sum())
        sub_sbs = int(sub_y.sum(axis=0).argmin())
        per_regime[regime] = {
            "instances": len(idx),
            "vbs": round(sub_vbs, 4),
            "sbs": round(float(sub_y[:, sub_sbs].sum()), 4),
            "sbs_algorithm": SERIOUS[sub_sbs],
            "sbs_gap_to_vbs": round((float(sub_y[:, sub_sbs].sum()) - sub_vbs) / sub_vbs, 6),
        }

    payload = {
        "instances": n,
        "algorithms": SERIOUS,
        "vbs_total": round(vbs, 4),
        "sbs_total": round(float(Y[:, sbs_pick].sum()), 4),
        "sbs_gap_to_vbs": round((float(Y[:, sbs_pick].sum()) - vbs) / vbs, 6),
        "selectors": results,
        "per_regime": per_regime,
        "selection_cost_note": "every selector needs the full matrix on its training instances: 4 algorithm evaluations per instance, no provider calls",
    }
    (OUT / "selectors.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
