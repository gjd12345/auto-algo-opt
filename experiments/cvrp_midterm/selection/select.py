"""Instance-level algorithm selection on the factorial regime matrix (v3).

Question set (task B):
  1. Is there complementarity?  Compare the best single algorithm (SBS) with the
     per-instance oracle (VBS), overall and inside every design cell.
  2. Is the oracle predictable from pre-solve features?  Leave-one-instance-out
     within the pool, then leave-one-cell-out (8 cells) across pools.
  3. Does a selector beat the fixed choice after its own overhead?  Report total
     distance, gain against the fixed choice, mean per-instance regret against
     VBS, and the training cost in evaluator calls.

Revision 3 adds the frozen rule C to the pool (``with_c``, ``extended_c``) and a
fourth selector family: pairwise comparison.  For every ordered pair of rules a
linear-probability model is fit on the sign of the pairwise difference and votes
for the rule it predicts to win; the rule with most pairwise wins is chosen, and
predicted objective breaks ties.  This is the classic pairwise-ranking reduction
(better suited than regression to choosing between near-tied rules), fit with
the same ridge machinery so the comparison isolates the reduction, not the
regulariser.

``farthest`` is measured but never admitted: it is dominated in every cell, and
letting it into VBS would only flatter the oracle.
"""

from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

import numpy as np  # noqa: E402

OUT = REPO / "experiments/cvrp_midterm/selection"
PORTFOLIOS = {
    "core": ("nn", "savings", "dd_load", "radial"),
    "with_c": ("nn", "savings", "dd_load", "radial", "c"),
    "extended_c": ("nn", "savings", "dd_load", "radial", "isolate", "load_fill", "c"),
    "core_abc": ("nn", "savings", "dd_load", "radial", "a", "b", "c"),
    "full_pool": ("nn", "savings", "dd_load", "radial", "isolate", "load_fill",
                  "a", "b", "c"),
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


def ridge_fit(x: np.ndarray, y: np.ndarray, lam: float = 1.0,
              weight: np.ndarray | None = None) -> np.ndarray:
    """Ridge on standardised features; the intercept is never penalised.

    ``weight`` turns this into weighted least squares, which is what makes the
    pairwise models cost-sensitive: a pair that differs by 3.0 counts three
    times as much as a pair that differs by 1.0.
    """
    xb = np.hstack([np.ones((x.shape[0], 1)), x])
    reg = lam * np.eye(xb.shape[1])
    reg[0, 0] = 0.0
    if weight is None:
        return np.linalg.solve(xb.T @ xb + reg, xb.T @ y)
    w = np.asarray(weight, dtype=float).ravel()
    return np.linalg.solve(xb.T @ (xb * w[:, None]) + reg, xb.T @ (y * w))


def ridge_predict(w: np.ndarray, x: np.ndarray) -> np.ndarray:
    xb = np.hstack([np.ones((x.shape[0], 1)), x])
    return xb @ w


def pairwise_pick(train_x: np.ndarray, train_y: np.ndarray, test_x: np.ndarray,
                  fallback: np.ndarray, weighted: bool = True) -> int:
    """Vote among rules by pairwise win models; predicted objective breaks ties.

    ``train_y`` is (n_train, k) objective values (lower is better), ``fallback``
    is the predicted objective row used only to break a vote tie.

    The default model is cost-sensitive: each pairwise observation is weighted
    by ``|c_a - c_b|``, so a pair that differs by 3.0 counts three times as much
    as a pair that differs by 1.0.  ``weighted=False`` keeps the plain sign fit
    measured in revision 3, so the two can be compared on the same folds.
    """
    k = train_y.shape[1]
    votes = np.zeros(k)
    for a, b in itertools.combinations(range(k), 2):
        diff = train_y[:, a] - train_y[:, b]
        # +1 means rule ``a`` is better (lower objective) on that instance.
        target = np.where(diff < 0.0, 1.0, -1.0)
        weight = None
        if weighted:
            gap = np.abs(diff)
            mean_gap = float(gap.mean())
            weight = gap / mean_gap if mean_gap > 1e-12 else None
        if np.all(target == 1.0) or np.all(target == -1.0):
            votes[a if target[0] > 0 else b] += 1
            continue
        w = ridge_fit(train_x, target, weight=weight)
        if float(ridge_predict(w, test_x)[0]) > 0.0:
            votes[a] += 1
        else:
            votes[b] += 1
    best = np.flatnonzero(votes == votes.max())
    if best.size == 1:
        return int(best[0])
    return int(best[int(np.argmin(fallback[best]))])


def cluster_stump_pick(train_x: np.ndarray, train_y: np.ndarray, test_x: np.ndarray,
                       feature_index: int = 3) -> int:
    """Interpretable 1-feature decision stump on ``cluster_tendency`` (index 3).

    Finds the single threshold t minimizing total training objective when picking
    the best left rule (x <= t) and best right rule (x > t), strictly inside the
    training fold (zero leakage).
    """
    vals = train_x[:, feature_index]
    order = np.argsort(vals)
    s_vals = vals[order]
    s_y = train_y[order]
    n_tr = s_y.shape[0]
    cum_left = np.cumsum(s_y, axis=0)
    total = cum_left[-1]
    best_obj = float("inf")
    best_t = float(np.median(vals))
    best_left = int(total.argmin())
    best_right = best_left
    for split in range(4, n_tr - 4):
        if s_vals[split] == s_vals[split - 1]:
            continue
        left_tot = cum_left[split - 1]
        right_tot = total - left_tot
        li = int(left_tot.argmin())
        ri = int(right_tot.argmin())
        cand = float(left_tot[li] + right_tot[ri])
        if cand < best_obj:
            best_obj = cand
            best_t = 0.5 * float(s_vals[split - 1] + s_vals[split])
            best_left, best_right = li, ri
    return best_left if float(test_x[0, feature_index]) <= best_t else best_right


def _paired_bootstrap(chosen: np.ndarray, fixed: np.ndarray, draws: int = 10000,
                      seed: int = 42) -> dict:
    n = chosen.shape[0]
    diff = fixed - chosen  # positive = selector beats fixed SBS
    wins = int(np.sum(diff > 1e-12))
    ties = int(np.sum(np.abs(diff) <= 1e-12))
    losses = int(np.sum(diff < -1e-12))
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(draws, n))
    boot_fixed = fixed[idx].sum(axis=1)
    boot_chosen = chosen[idx].sum(axis=1)
    boot_gains = (boot_fixed - boot_chosen) / boot_fixed
    lo, hi = np.percentile(boot_gains, [2.5, 97.5])
    p_one_sided = float(np.mean(boot_gains <= 0.0))
    return {
        "gain_ci95": [round(float(lo), 6), round(float(hi), 6)],
        "p_boot_one_sided": round(p_one_sided, 4),
        "wtl_vs_fixed": {"wins": wins, "ties": ties, "losses": losses},
    }


def summarize(name: str, picks, Y, names, cells: list[str], fixed_total: float,
              fixed_vec: np.ndarray | None = None,
              extra: dict | None = None) -> dict:
    chosen = np.array([Y[i, j] for i, j in enumerate(picks)], dtype=float)
    oracle = Y.min(axis=1)
    regret = (chosen - oracle) / oracle
    vbs = float(oracle.sum())
    total = float(chosen.sum())
    out = {
        "selector": name,
        "total_objective": round(total, 4),
        "gap_to_vbs": round((total - vbs) / vbs, 6),
        "gain_vs_fixed": round((fixed_total - total) / fixed_total, 6),
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
    if fixed_vec is not None and name != "fixed_best_sbs":
        out.update(_paired_bootstrap(chosen, fixed_vec))
    if extra:
        out.update(extra)
    return out


def run(portfolio: str) -> dict:
    rows, X, Y, cells, names = load(portfolio)
    n = len(rows)
    k = len(names)
    vbs = float(Y.min(axis=1).sum())
    sbs_pick = int(Y.sum(axis=0).argmin())
    fixed_vec = Y[:, sbs_pick].copy()
    fixed_total = float(fixed_vec.sum())
    results = [
        summarize("fixed_best_sbs", [sbs_pick] * n, Y, names, cells, fixed_total,
                  fixed_vec=fixed_vec,
                  extra={"algorithm": names[sbs_pick], "design": "none"})
    ]

    folds = list(range(n))

    picks_nn, picks_ridge, picks_pair, picks_pair_plain, picks_stump = [], [], [], [], []
    for i in folds:
        mask = np.arange(n) != i
        train_x, test_x = standardize(X[mask], X[i:i + 1])
        dist = np.linalg.norm(train_x - test_x, axis=1)
        picks_nn.append(int(Y[mask][int(dist.argmin())].argmin()))

        w = ridge_fit(train_x, Y[mask])
        pred = ridge_predict(w, test_x)[0]
        picks_ridge.append(int(pred.argmin()))
        picks_pair.append(pairwise_pick(train_x, Y[mask], test_x, pred))
        picks_pair_plain.append(
            pairwise_pick(train_x, Y[mask], test_x, pred, weighted=False)
        )
        picks_stump.append(cluster_stump_pick(X[mask], Y[mask], X[i:i + 1]))

    results.append(summarize("cluster_stump_loo", picks_stump, Y, names, cells, fixed_total,
                             fixed_vec=fixed_vec,
                             extra={"design": "1-feature threshold split on cluster_tendency fit inside fold"}))
    results.append(summarize("knn1_loo", picks_nn, Y, names, cells, fixed_total,
                             fixed_vec=fixed_vec,
                             extra={"design": "1-nearest-neighbour on pre-solve features"}))
    results.append(summarize("ridge_loo", picks_ridge, Y, names, cells, fixed_total,
                             fixed_vec=fixed_vec,
                             extra={"design": "one ridge per rule, argmin of predictions"}))
    results.append(summarize("pairwise_loo", picks_pair, Y, names, cells, fixed_total,
                             fixed_vec=fixed_vec,
                             extra={"design": "one cost-sensitive ridge per pair (weight |c_a - c_b|) on the win sign, vote by pairwise wins"}))
    results.append(summarize("pairwise_loo_unweighted", picks_pair_plain, Y, names, cells, fixed_total,
                             fixed_vec=fixed_vec,
                             extra={"design": "same pairwise vote with unweighted signs (revision 3 recipe), for the cost-sensitivity ablation"}))

    loro_picks = {"stump": [0] * n, "ridge": [0] * n, "pairwise": [0] * n, "pairwise_plain": [0] * n}
    loro_cells = {"stump": {}, "ridge": {}, "pairwise": {}, "pairwise_plain": {}}
    for cell in sorted(set(cells)):
        test_idx = [i for i, c in enumerate(cells) if c == cell]
        train_idx = [i for i, c in enumerate(cells) if c != cell]
        train_x, test_x = standardize(X[train_idx], X[test_idx])
        w = ridge_fit(train_x, Y[train_idx])
        pred = ridge_predict(w, test_x)
        picks_stump_cell = [
            cluster_stump_pick(X[train_idx], Y[train_idx], X[i:i + 1])
            for i in test_idx
        ]
        picks_ridge_cell = [int(p.argmin()) for p in pred]
        picks_pair_cell = [
            pairwise_pick(train_x, Y[train_idx], test_x[j:j + 1], pred[j])
            for j in range(len(test_idx))
        ]
        picks_pair_plain_cell = [
            pairwise_pick(train_x, Y[train_idx], test_x[j:j + 1], pred[j], weighted=False)
            for j in range(len(test_idx))
        ]
        for i, p in zip(test_idx, picks_stump_cell):
            loro_picks["stump"][i] = p
        for i, p in zip(test_idx, picks_ridge_cell):
            loro_picks["ridge"][i] = p
        for i, p in zip(test_idx, picks_pair_cell):
            loro_picks["pairwise"][i] = p
        for i, p in zip(test_idx, picks_pair_plain_cell):
            loro_picks["pairwise_plain"][i] = p
        sub_oracle = Y[test_idx].min(axis=1).sum()
        for label, picks in (("stump", picks_stump_cell),
                             ("ridge", picks_ridge_cell),
                             ("pairwise", picks_pair_cell),
                             ("pairwise_plain", picks_pair_plain_cell)):
            sub_chosen = sum(Y[i, p] for i, p in zip(test_idx, picks))
            loro_cells[label][cell] = {
                "instances": len(test_idx),
                "gap_to_vbs": round(float((sub_chosen - sub_oracle) / sub_oracle), 6),
                "picks": {names[j]: int(sum(1 for p in picks if p == j)) for j in range(k)},
            }

    results.append(summarize("cluster_stump_loro", loro_picks["stump"], Y, names, cells, fixed_total,
                             fixed_vec=fixed_vec,
                             extra={"design": "1-feature cluster_tendency stump trained on seven cells, scored on the eighth",
                                    "per_held_out_cell": loro_cells["stump"]}))
    results.append(summarize("ridge_loro", loro_picks["ridge"], Y, names, cells, fixed_total,
                             fixed_vec=fixed_vec,
                             extra={"design": "ridge trained on seven cells, scored on the eighth",
                                    "per_held_out_cell": loro_cells["ridge"]}))
    results.append(summarize("pairwise_loro", loro_picks["pairwise"], Y, names, cells, fixed_total,
                             fixed_vec=fixed_vec,
                             extra={"design": "cost-sensitive pairwise votes trained on seven cells, scored on the eighth",
                                    "per_held_out_cell": loro_cells["pairwise"]}))
    results.append(summarize("pairwise_loro_unweighted", loro_picks["pairwise_plain"], Y,
                             names, cells, fixed_total,
                             fixed_vec=fixed_vec,
                             extra={"design": "unweighted pairwise votes trained on seven cells, scored on the eighth",
                                    "per_held_out_cell": loro_cells["pairwise_plain"]}))

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
            "mean_objective": {names[j]: round(float(sub_y[:, j].mean()), 4) for j in range(k)},
        }

    return {
        "portfolio": portfolio,
        "members": list(names),
        "instances": n,
        "vbs_total": round(vbs, 4),
        "sbs_total": round(fixed_total, 4),
        "sbs_algorithm": names[sbs_pick],
        "sbs_gap_to_vbs": round((fixed_total - vbs) / vbs, 6),
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
                {k: r[k] for k in ("selector", "total_objective", "gap_to_vbs",
                                   "gain_vs_fixed", "mean_regret")}
                for r in block["selectors"]
            ],
        }
        for portfolio, block in blocks.items()
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
