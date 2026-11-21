"""Instance-level algorithm selection on the factorial regime matrix (v2).

Question set (task B):
  1. Is there complementarity?  Compare the best single algorithm (SBS) with the
     per-instance oracle (VBS), overall and inside every design cell.
  2. Is the oracle predictable from pre-solve features?  Leave-one-instance-out
     within the pool, then leave-one-cell-out (8 cells) across pools.
  3. Does a selector beat the fixed choice after its own overhead?  Report total
     distance, mean per-instance regret against VBS, and the training cost in
     evaluator calls.

Every question is answered for two portfolios.  ``core`` is the four rules that
define the original experiment; ``extended`` adds two structurally different
rules (isolation-first, load-fill-first).  ``farthest`` is measured but never
admitted: it is dominated in every cell, and letting it into VBS would only
flatter the oracle.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

import numpy as np  # noqa: E402

OUT = REPO / "experiments/cvrp_midterm/selection"
PORTFOLIOS = {
    "core": ("nn", "savings", "dd_load", "radial"),
    "extended": ("nn", "savings", "dd_load", "radial", "isolate", "load_fill"),
}
FEATURES = ("mean_demand", "cv_demand", "capacity_ratio", "cluster_tendency",
            "radial_std", "depot_eccentricity", "x_spread", "y_spread")


def load(portfolio: str):
    names = PORTFOLIOS[portfolio]
    rows = json.loads((OUT / "matrix.json").read_text(encoding="utf-8"))
    X = np.array([[r[f] for f in FEATURES] for r in rows], dtype=float)
    Y = np.array([[r[a] for a in names] for r in rows], dtype=float)
    cells = [r["cell"] for r in rows]
    return rows, X, Y, cells, names


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


def summarize(name: str, picks, Y, names, cells: list[str], extra: dict | None = None) -> dict:
    chosen = np.array([Y[i, j] for i, j in enumerate(picks)], dtype=float)
    oracle = Y.min(axis=1)
    regret = (chosen - oracle) / oracle
    vbs = float(oracle.sum())
    out = {
        "selector": name,
        "total_objective": round(float(chosen.sum()), 4),
        "gap_to_vbs": round(float((chosen.sum() - vbs) / vbs), 6),
        "mean_regret": round(float(regret.mean()), 6),
        "worst_regret": round(float(regret.max()), 6),
        "picks": {names[j]: int(sum(1 for p in picks if p == j)) for j in range(len(names))},
        "per_cell_gap": {
            cell: round(
                float(
                    (sum(chosen[i] for i in range(len(cells)) if cells[i] == cell)
                     - sum(oracle[i] for i in range(len(cells)) if cells[i] == cell))
                    / sum(oracle[i] for i in range(len(cells)) if cells[i] == cell)
                ), 6)
            for cell in sorted(set(cells))
        },
    }
    if extra:
        out.update(extra)
    return out


def run(portfolio: str) -> dict:
    _rows, X, Y, cells, names = load(portfolio)
    n = len(rows := _rows)
    vbs = float(Y.min(axis=1).sum())
    sbs_pick = int(Y.sum(axis=0).argmin())
    results = [
        summarize("fixed_best_sbs", [sbs_pick] * n, Y, names, cells,
                  {"algorithm": names[sbs_pick]})
    ]

    picks_nn = []
    for i in range(n):
        mask = np.arange(n) != i
        train_x, test_x = standardize(X[mask], X[i:i + 1])
        dist = np.linalg.norm(train_x - test_x, axis=1)
        picks_nn.append(int(Y[mask][int(dist.argmin())].argmin()))
    results.append(summarize("knn1_loo", picks_nn, Y, names, cells))

    picks_ridge = []
    for i in range(n):
        mask = np.arange(n) != i
        train_x, test_x = standardize(X[mask], X[i:i + 1])
        w = ridge_fit(train_x, Y[mask])
        picks_ridge.append(int(ridge_predict(w, test_x)[0].argmin()))
    results.append(summarize("ridge_loo", picks_ridge, Y, names, cells))

    loro = [0] * n
    loro_cells: dict[str, dict] = {}
    for cell in sorted(set(cells)):
        test_idx = [i for i, c in enumerate(cells) if c == cell]
        train_idx = [i for i, c in enumerate(cells) if c != cell]
        train_x, test_x = standardize(X[train_idx], X[test_idx])
        w = ridge_fit(train_x, Y[train_idx])
        pred = ridge_predict(w, test_x)
        picks = [int(p.argmin()) for p in pred]
        for i, p in zip(test_idx, picks):
            loro[i] = p
        sub_oracle = Y[test_idx].min(axis=1).sum()
        sub_chosen = sum(Y[i, p] for i, p in zip(test_idx, picks))
        loro_cells[cell] = {
            "instances": len(test_idx),
            "gap_to_vbs": round(float((sub_chosen - sub_oracle) / sub_oracle), 6),
            "picks": {names[j]: int(sum(1 for p in picks if p == j)) for j in range(len(names))},
        }
    results.append(summarize("ridge_loro", loro, Y, names, cells,
                             {"per_held_out_cell": loro_cells}))

    per_cell = {}
    for cell in sorted(set(cells)):
        idx = [i for i, c in enumerate(cells) if c == cell]
        sub_y = Y[idx]
        sub_vbs = float(sub_y.min(axis=1).sum())
        sub_sbs = int(sub_y.sum(axis=0).argmin())
        per_cell[cell] = {
            "instances": len(idx),
            "vbs": round(sub_vbs, 4),
            "sbs": round(float(sub_y[:, sub_sbs].sum()), 4),
            "sbs_algorithm": names[sub_sbs],
            "sbs_gap_to_vbs": round((float(sub_y[:, sub_sbs].sum()) - sub_vbs) / sub_vbs, 6),
        }

    return {
        "portfolio": portfolio,
        "members": list(names),
        "instances": n,
        "vbs_total": round(vbs, 4),
        "sbs_total": round(float(Y[:, sbs_pick].sum()), 4),
        "sbs_algorithm": names[sbs_pick],
        "sbs_gap_to_vbs": round(float((float(Y[:, sbs_pick].sum()) - vbs) / vbs), 6),
        "selectors": results,
        "per_cell": per_cell,
    }


def main() -> int:
    blocks = {portfolio: run(portfolio) for portfolio in PORTFOLIOS}
    payload = {
        "instances": blocks["core"]["instances"],
        "portfolios": blocks,
        "selection_cost": {
            "training": "the matrix needs one construct evaluation per portfolio member per training instance",
            "evaluations_per_training_instance": {k: len(v) for k, v in PORTFOLIOS.items()},
            "evaluations_per_served_instance": 1,
            "provider_calls": 0,
            "note": "retraining is offline; a deployed selector pays one construct run, not the full portfolio",
        },
    }
    (OUT / "selectors.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({
        portfolio: {
            "vbs_total": block["vbs_total"],
            "sbs_total": block["sbs_total"],
            "sbs_algorithm": block["sbs_algorithm"],
            "sbs_gap_to_vbs": block["sbs_gap_to_vbs"],
            "selectors": [
                {k: r[k] for k in ("selector", "gap_to_vbs", "mean_regret")}
                for r in block["selectors"]
            ],
        }
        for portfolio, block in blocks.items()
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
