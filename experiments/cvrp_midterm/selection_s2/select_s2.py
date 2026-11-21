"""Stage 2 Track B: Out-of-fold algorithm selection across 288 multi-scale instances.

Evaluates interpretable and nonlinear selectors (all pure NumPy, strictly
out-of-fold, zero test leakage) across three validation protocols:
1. cv12   : 12-fold stratified within-distribution CV across all 48 factor cells
2. loro48 : 48-fold Leave-One-Regime-Cell-Out (unseen factor combination)
3. loso3  : 3-fold Leave-One-Scale-Out (train on 2 sizes, test on unseen size)

Scale-normalized relative regret targets y_k = (c_k - min_m c_m) / min_m c_m
are computed strictly on training instances so models transfer cleanly across
scales n in {50, 100, 200}.

Selectors:
- fixed_best_sbs   : in-fold Single Best Solver
- stump_1d         : depth-1 single-feature decision stump minimizing training cost
- knn5             : 5-NN on z-scored features predicting relative regret
- ridge            : multi-output ridge with inside-fold lambda CV
- pairwise_cs      : cost-sensitive weighted pairwise linear ranking
- pairwise_plain   : unweighted pairwise linear ranking
- rf_reg           : pure-NumPy Random Forest multi-output regret regressor (40 trees)
- rf_pairwise_cs   : pure-NumPy Cost-Sensitive Pairwise Random Forest (AutoFolio/SATzilla style)

Reports 10,000-draw paired Bootstrap 95% CIs, one-sided p_boot, W/T/L vs SBS,
mean/worst regret, net runtime (feat_s + chosen_solve_s), per-scale breakdown,
and permutation feature importance.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

import numpy as np  # noqa: E402

OUT = REPO / "experiments/cvrp_midterm/selection_s2"
MATRIX_PATH = OUT / "matrix_s2.json"
SUMMARY_PATH = OUT / "summary_s2.json"
OUT_JSON = OUT / "selectors_s2.json"

FEATURE_NAMES = (
    "mean_demand",
    "cv_demand",
    "capacity_ratio",
    "cluster_tendency",
    "radial_std",
    "depot_eccentricity",
    "x_spread",
    "y_spread",
    "log_n",
    "demand_bimodality",
    "nn_dist_cv",
    "depot_angle_disp",
)


def standardize(x_tr: np.ndarray, x_te: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mu = x_tr.mean(axis=0)
    sd = x_tr.std(axis=0)
    sd[sd < 1e-12] = 1.0
    return (x_tr - mu) / sd, (x_te - mu) / sd


def relative_regret_matrix(y: np.ndarray) -> np.ndarray:
    """Dimensionless per-instance relative regret (c_k - c_min) / c_min."""
    row_min = np.maximum(y.min(axis=1, keepdims=True), 1e-12)
    return (y - row_min) / row_min


def ridge_fit(x: np.ndarray, y: np.ndarray, lam: float = 1.0, weights: np.ndarray | None = None) -> np.ndarray:
    xb = np.hstack([np.ones((x.shape[0], 1)), x])
    p = xb.shape[1]
    eye = np.eye(p)
    eye[0, 0] = 0.0
    if weights is None:
        a = xb.T @ xb + lam * eye
        b = xb.T @ y
    else:
        w = np.asarray(weights, dtype=float).reshape(-1, 1)
        a = xb.T @ (w * xb) + lam * eye
        b = xb.T @ (w * y)
    return np.linalg.solve(a, b)


def ridge_predict(beta: np.ndarray, x: np.ndarray) -> np.ndarray:
    xb = np.hstack([np.ones((x.shape[0], 1)), x])
    return xb @ beta


# ---------- Pure-NumPy Fast CART / Random Forest ----------

class RegTree:
    """Fast vectorized CART regression tree (supports multi-output and sample weights)."""

    __slots__ = ("max_depth", "min_leaf", "max_features", "tree_")

    def __init__(self, max_depth: int = 4, min_leaf: int = 6, max_features: int | None = None):
        self.max_depth = max_depth
        self.min_leaf = min_leaf
        self.max_features = max_features
        self.tree_: dict = {}

    def fit(self, x: np.ndarray, y: np.ndarray, rng: np.random.Generator, w: np.ndarray | None = None) -> "RegTree":
        if y.ndim == 1:
            y = y[:, None]
        if w is None:
            w = np.ones(x.shape[0], dtype=float)
        idx = np.arange(x.shape[0], dtype=int)
        self.tree_ = self._build(x, y, w, idx, depth=0, rng=rng)
        return self

    def _leaf_value(self, y: np.ndarray, w: np.ndarray, idx: np.ndarray) -> np.ndarray:
        ww = w[idx]
        s = float(ww.sum())
        if s <= 1e-12:
            return y[idx].mean(axis=0)
        return (ww[:, None] * y[idx]).sum(axis=0) / s

    def _build(self, x: np.ndarray, y: np.ndarray, w: np.ndarray, idx: np.ndarray, depth: int, rng: np.random.Generator) -> dict:
        n = idx.size
        val = self._leaf_value(y, w, idx)
        if depth >= self.max_depth or n < 2 * self.min_leaf:
            return {"leaf": True, "val": val}

        p = x.shape[1]
        if self.max_features is not None and self.max_features < p:
            feats = rng.choice(p, size=self.max_features, replace=False)
        else:
            feats = np.arange(p)

        w_sub = w[idx]
        y_sub = y[idx]
        wy_sub = w_sub[:, None] * y_sub
        total_w = float(w_sub.sum())
        total_wy = wy_sub.sum(axis=0)
        # Maximizing (sum_L^2 / w_L + sum_R^2 / w_R) is exact weighted SSE minimization!
        base_score = float(np.sum(total_wy * total_wy) / max(total_w, 1e-12))
        best_gain = 1e-12
        best_feat = -1
        best_thr = 0.0
        best_left: np.ndarray | None = None
        best_right: np.ndarray | None = None

        for f in feats:
            col = x[idx, f]
            order = np.argsort(col, kind="mergesort")
            s_col = col[order]
            if s_col[-1] - s_col[0] <= 1e-12:
                continue
            s_w = w_sub[order]
            s_wy = wy_sub[order]
            cw = np.cumsum(s_w)
            cwy = np.cumsum(s_wy, axis=0)
            # Valid split indices k: left = [0..k], right = [k+1..n-1]
            # Must have at least min_leaf on each side and distinct feature values
            lo = self.min_leaf - 1
            hi = n - self.min_leaf
            if lo >= hi:
                continue
            diff_mask = s_col[lo:hi] < s_col[lo + 1 : hi + 1] - 1e-12
            if not np.any(diff_mask):
                continue
            ks = np.nonzero(diff_mask)[0] + lo
            wl = cw[ks]
            wr = total_w - wl
            ok = (wl > 1e-12) & (wr > 1e-12)
            if not np.any(ok):
                continue
            ks = ks[ok]
            wl = wl[ok]
            wr = wr[ok]
            wyl = cwy[ks]
            wyr = total_wy[None, :] - wyl
            scores = np.sum(wyl * wyl, axis=1) / wl + np.sum(wyr * wyr, axis=1) / wr
            bi = int(np.argmax(scores))
            gain = float(scores[bi]) - base_score
            if gain > best_gain:
                k = int(ks[bi])
                best_gain = gain
                best_feat = int(f)
                best_thr = 0.5 * (float(s_col[k]) + float(s_col[k + 1]))
                best_left = idx[order[: k + 1]]
                best_right = idx[order[k + 1 :]]

        if best_feat < 0 or best_left is None or best_right is None:
            return {"leaf": True, "val": val}
        return {
            "leaf": False,
            "feat": best_feat,
            "thr": best_thr,
            "left": self._build(x, y, w, best_left, depth + 1, rng),
            "right": self._build(x, y, w, best_right, depth + 1, rng),
        }

    def predict(self, x: np.ndarray) -> np.ndarray:
        out = np.empty((x.shape[0], self._out_dim(self.tree_)), dtype=float)
        for i in range(x.shape[0]):
            node = self.tree_
            xi = x[i]
            while not node["leaf"]:
                node = node["left"] if xi[node["feat"]] <= node["thr"] else node["right"]
            out[i] = node["val"]
        return out

    @staticmethod
    def _out_dim(node: dict) -> int:
        while not node["leaf"]:
            node = node["left"]
        return int(node["val"].shape[0])


def fit_predict_rf_reg(
    x_tr: np.ndarray,
    y_tr: np.ndarray,
    x_te: np.ndarray,
    *,
    n_trees: int = 40,
    max_depth: int = 4,
    min_leaf: int = 6,
    max_features: int = 4,
    seed: int = 20261122,
) -> tuple[np.ndarray, list[RegTree]]:
    rng = np.random.default_rng(seed)
    regret_tr = relative_regret_matrix(y_tr)
    n, k = regret_tr.shape
    preds = np.zeros((x_te.shape[0], k), dtype=float)
    trees: list[RegTree] = []
    for _ in range(n_trees):
        bag = rng.integers(0, n, size=n)
        tree = RegTree(max_depth=max_depth, min_leaf=min_leaf, max_features=max_features)
        tree.fit(x_tr[bag], regret_tr[bag], rng)
        preds += tree.predict(x_te)
        trees.append(tree)
    return preds / n_trees, trees


def fit_predict_rf_pairwise_cs(
    x_tr: np.ndarray,
    y_tr: np.ndarray,
    x_te: np.ndarray,
    *,
    n_trees: int = 20,
    max_depth: int = 3,
    min_leaf: int = 8,
    max_features: int = 4,
    seed: int = 20261122,
) -> np.ndarray:
    """Cost-sensitive pairwise RF predicting expected relative pairwise regret."""
    rng = np.random.default_rng(seed)
    n, k = y_tr.shape
    n_te = x_te.shape[0]
    row_min = np.maximum(y_tr.min(axis=1), 1e-12)
    # Expected regret matrix: lower total predicted excess over rivals is better
    expected_loss = np.zeros((n_te, k), dtype=float)
    for a in range(k):
        for b in range(a + 1, k):
            diff = (y_tr[:, a] - y_tr[:, b]) / row_min  # >0 means b is better than a
            w = np.abs(diff)
            wm = float(w.mean())
            if wm < 1e-12:
                continue
            w = w / wm + 0.05  # smooth floor so informative ties keep tiny weight
            pred_ab = np.zeros(n_te, dtype=float)
            for _ in range(n_trees):
                bag = rng.integers(0, n, size=n)
                tree = RegTree(max_depth=max_depth, min_leaf=min_leaf, max_features=max_features)
                tree.fit(x_tr[bag], diff[bag], rng, w=w[bag])
                pred_ab += tree.predict(x_te)[:, 0]
            pred_ab /= n_trees
            # Positive pred_ab penalizes a; negative pred_ab penalizes b
            expected_loss[:, a] += np.maximum(0.0, pred_ab)
            expected_loss[:, b] += np.maximum(0.0, -pred_ab)
    return np.argmin(expected_loss, axis=1)


# ---------- Other Selectors ----------

def pick_fixed_sbs(y_tr: np.ndarray, n_te: int) -> np.ndarray:
    best = int(np.argmin(y_tr.sum(axis=0)))
    return np.full(n_te, best, dtype=int)


def pick_stump_1d(x_tr: np.ndarray, y_tr: np.ndarray, x_te: np.ndarray, min_leaf: int = 12) -> tuple[np.ndarray, dict]:
    """Depth-1 interpretable decision stump choosing 1 feature + threshold minimizing relative regret."""
    regret_tr = relative_regret_matrix(y_tr)
    n, p = x_tr.shape
    best_obj = float(regret_tr.sum(axis=0).min())
    best_sbs = int(np.argmin(regret_tr.sum(axis=0)))
    best_spec = {"feat": -1, "thr": 0.0, "left": best_sbs, "right": best_sbs}

    for f in range(p):
        col = x_tr[:, f]
        order = np.argsort(col, kind="mergesort")
        s_col = col[order]
        s_r = regret_tr[order]
        csum = np.cumsum(s_r, axis=0)
        total = csum[-1]
        for k in range(min_leaf - 1, n - min_leaf):
            if s_col[k + 1] - s_col[k] <= 1e-12:
                continue
            left_sums = csum[k]
            right_sums = total - left_sums
            li = int(np.argmin(left_sums))
            ri = int(np.argmin(right_sums))
            obj = float(left_sums[li] + right_sums[ri])
            if obj < best_obj - 1e-12:
                best_obj = obj
                best_spec = {
                    "feat": f,
                    "thr": 0.5 * (float(s_col[k]) + float(s_col[k + 1])),
                    "left": li,
                    "right": ri,
                }
    if best_spec["feat"] < 0:
        return np.full(x_te.shape[0], best_spec["left"], dtype=int), best_spec
    picks = np.where(x_te[:, best_spec["feat"]] <= best_spec["thr"], best_spec["left"], best_spec["right"])
    return picks.astype(int), best_spec


def pick_knn5(x_tr: np.ndarray, y_tr: np.ndarray, x_te: np.ndarray, k_nn: int = 5) -> np.ndarray:
    xs_tr, xs_te = standardize(x_tr, x_te)
    regret_tr = relative_regret_matrix(y_tr)
    d = np.linalg.norm(xs_te[:, None, :] - xs_tr[None, :, :], axis=2)
    nn_idx = np.argsort(d, axis=1)[:, :k_nn]
    nn_d = np.take_along_axis(d, nn_idx, axis=1)
    w = 1.0 / (nn_d + 1e-6)
    w = w / w.sum(axis=1, keepdims=True)
    pred = np.einsum("ij,ijk->ik", w, regret_tr[nn_idx])
    return np.argmin(pred, axis=1)


def pick_ridge_cv(x_tr: np.ndarray, y_tr: np.ndarray, x_te: np.ndarray) -> np.ndarray:
    """Multi-output ridge on relative regret with inside-fold 5-fold lambda selection."""
    regret_tr = relative_regret_matrix(y_tr)
    lambdas = (0.1, 1.0, 10.0, 50.0)
    n = x_tr.shape[0]
    fold_ids = np.arange(n) % 5
    best_lam = 1.0
    best_loss = float("inf")
    for lam in lambdas:
        loss = 0.0
        for fid in range(5):
            va = fold_ids == fid
            tr = ~va
            xs_t, xs_v = standardize(x_tr[tr], x_tr[va])
            beta = ridge_fit(xs_t, regret_tr[tr], lam=lam)
            pred = ridge_predict(beta, xs_v)
            picks = np.argmin(pred, axis=1)
            loss += float(regret_tr[va][np.arange(va.sum()), picks].sum())
        if loss < best_loss:
            best_loss = loss
            best_lam = lam
    xs_tr, xs_te = standardize(x_tr, x_te)
    beta = ridge_fit(xs_tr, regret_tr, lam=best_lam)
    return np.argmin(ridge_predict(beta, xs_te), axis=1)


def pick_pairwise(x_tr: np.ndarray, y_tr: np.ndarray, x_te: np.ndarray, *, weighted: bool, lam: float = 10.0) -> np.ndarray:
    xs_tr, xs_te = standardize(x_tr, x_te)
    row_min = np.maximum(y_tr.min(axis=1), 1e-12)
    k = y_tr.shape[1]
    scores = np.zeros((x_te.shape[0], k), dtype=float)
    for a in range(k):
        for b in range(a + 1, k):
            rel_diff = (y_tr[:, b] - y_tr[:, a]) / row_min  # >0 means a beats b
            target = np.sign(rel_diff)
            if weighted:
                w = np.abs(rel_diff)
                wm = float(w.mean())
                w = (w / wm) if wm > 1e-12 else np.ones_like(w)
                beta = ridge_fit(xs_tr, target[:, None], lam=lam, weights=w)
            else:
                beta = ridge_fit(xs_tr, target[:, None], lam=lam)
            margin = ridge_predict(beta, xs_te)[:, 0]
            scores[:, a] += margin
            scores[:, b] -= margin
    return np.argmax(scores, axis=1)


# ---------- Evaluation & Bootstrap ----------

def build_folds(rows: list[dict], protocol: str) -> list[tuple[np.ndarray, np.ndarray]]:
    n = len(rows)
    if protocol == "cv12":
        # Stratified across all 48 cells (6 instances/cell -> assign cell-ordered indices mod 12)
        fold_of = np.empty(n, dtype=int)
        by_cell: dict[str, list[int]] = {}
        for i, r in enumerate(rows):
            by_cell.setdefault(r["cell"], []).append(i)
        offset = 0
        for cell in sorted(by_cell):
            for j, idx in enumerate(by_cell[cell]):
                fold_of[idx] = (offset + j) % 12
            offset = (offset + 6) % 12
        return [(np.where(fold_of != f)[0], np.where(fold_of == f)[0]) for f in range(12)]
    if protocol == "loro48":
        cells = sorted({r["cell"] for r in rows})
        return [
            (
                np.array([i for i, r in enumerate(rows) if r["cell"] != c], dtype=int),
                np.array([i for i, r in enumerate(rows) if r["cell"] == c], dtype=int),
            )
            for c in cells
        ]
    if protocol == "loso3":
        sizes = sorted({int(r["size"]) for r in rows})
        return [
            (
                np.array([i for i, r in enumerate(rows) if int(r["size"]) != sz], dtype=int),
                np.array([i for i, r in enumerate(rows) if int(r["size"]) == sz], dtype=int),
            )
            for sz in sizes
        ]
    raise ValueError(protocol)


def summarize_picks(
    rows: list[dict],
    members: list[str],
    y: np.ndarray,
    picks: np.ndarray,
    sbs_costs: np.ndarray,
    *,
    n_boot: int = 10000,
) -> dict:
    n = y.shape[0]
    chosen = y[np.arange(n), picks]
    vbs = y.min(axis=1)
    total_chosen = float(chosen.sum())
    total_vbs = float(vbs.sum())
    total_sbs = float(sbs_costs.sum())
    regrets = (chosen - vbs) / vbs
    gain_vs_sbs = (total_sbs - total_chosen) / total_sbs

    # Paired bootstrap over instances (10,000 draws)
    rng = np.random.default_rng(20261122)
    idx = rng.integers(0, n, size=(n_boot, n))
    boot_chosen = chosen[idx].sum(axis=1)
    boot_sbs = sbs_costs[idx].sum(axis=1)
    boot_gain = (boot_sbs - boot_chosen) / boot_sbs
    ci_lo, ci_hi = np.quantile(boot_gain, [0.025, 0.975])
    p_one_sided = float(np.mean(boot_gain <= 0.0))

    wins = int(np.sum(chosen < sbs_costs - 1e-12))
    losses = int(np.sum(chosen > sbs_costs + 1e-12))
    ties = n - wins - losses

    # Net runtime: feature extraction + chosen rule solve time
    feat_ms = np.array([float(r["feat_s"]) * 1000.0 for r in rows])
    chosen_solve_ms = np.array([float(rows[i][f"{members[picks[i]]}_solve_s"]) * 1000.0 for i in range(n)])
    pick_counts = {members[k]: int(np.sum(picks == k)) for k in range(len(members)) if int(np.sum(picks == k)) > 0}

    # Per-scale breakdown
    by_scale: dict[str, dict] = {}
    for sz in (50, 100, 200):
        mask = np.array([int(r["size"]) == sz for r in rows])
        c_sub = chosen[mask]
        v_sub = vbs[mask]
        s_sub = sbs_costs[mask]
        by_scale[str(sz)] = {
            "total": round(float(c_sub.sum()), 4),
            "gap_to_vbs": round(float((c_sub.sum() - v_sub.sum()) / v_sub.sum()), 6),
            "gain_vs_sbs": round(float((s_sub.sum() - c_sub.sum()) / s_sub.sum()), 6),
            "mean_regret": round(float(np.mean((c_sub - v_sub) / v_sub)), 6),
            "picks": {
                members[k]: int(np.sum(picks[mask] == k))
                for k in range(len(members))
                if int(np.sum(picks[mask] == k)) > 0
            },
        }

    return {
        "total": round(total_chosen, 4),
        "vbs_total": round(total_vbs, 4),
        "sbs_total": round(total_sbs, 4),
        "gap_to_vbs": round((total_chosen - total_vbs) / total_vbs, 6),
        "gain_vs_fixed": round(gain_vs_sbs, 6),
        "gain_ci95": [round(float(ci_lo), 6), round(float(ci_hi), 6)],
        "p_boot_one_sided": round(p_one_sided, 4),
        "wtl_vs_fixed": {"wins": wins, "ties": ties, "losses": losses},
        "mean_regret": round(float(regrets.mean()), 6),
        "worst_regret": round(float(regrets.max()), 6),
        "mean_net_ms": round(float(np.mean(feat_ms + chosen_solve_ms)), 3),
        "mean_solve_only_ms": round(float(np.mean(chosen_solve_ms)), 3),
        "picks": pick_counts,
        "by_scale": by_scale,
    }


def permutation_importance_rf(
    x: np.ndarray,
    y: np.ndarray,
    folds: list[tuple[np.ndarray, np.ndarray]],
    *,
    repeats: int = 10,
) -> dict[str, float]:
    """Out-of-fold permutation importance on rf_reg (increase in total objective, %)."""
    n = x.shape[0]
    base_picks = np.empty(n, dtype=int)
    fold_models: list[tuple[np.ndarray, list[RegTree]]] = []
    for f_i, (tr, te) in enumerate(folds):
        preds, trees = fit_predict_rf_reg(x[tr], y[tr], x[te], seed=20261122 + f_i)
        base_picks[te] = np.argmin(preds, axis=1)
        fold_models.append((te, trees))
    base_total = float(y[np.arange(n), base_picks].sum())

    rng = np.random.default_rng(777)
    imp: dict[str, float] = {}
    for fi, fname in enumerate(FEATURE_NAMES):
        deltas = []
        for _ in range(repeats):
            x_perm = x.copy()
            x_perm[:, fi] = rng.permutation(x_perm[:, fi])
            perm_picks = np.empty(n, dtype=int)
            for te, trees in fold_models:
                p_mat = np.zeros((te.size, y.shape[1]), dtype=float)
                for tree in trees:
                    p_mat += tree.predict(x_perm[te])
                perm_picks[te] = np.argmin(p_mat, axis=1)
            perm_total = float(y[np.arange(n), perm_picks].sum())
            deltas.append((perm_total - base_total) / base_total)
        imp[fname] = round(float(np.mean(deltas)), 6)
    return dict(sorted(imp.items(), key=lambda kv: -kv[1]))


def run_portfolio(rows: list[dict], members: list[str]) -> dict:
    x = np.array([[float(r[f]) for f in FEATURE_NAMES] for r in rows], dtype=float)
    y = np.array([[float(r[m]) for m in members] for r in rows], dtype=float)
    n = len(rows)

    # Global SBS (and in-fold SBS computed per protocol)
    global_sbs_idx = int(np.argmin(y.sum(axis=0)))
    global_sbs_costs = y[:, global_sbs_idx]

    protocols_out: dict[str, dict] = {}
    stump_rules: dict[str, list[dict]] = {}
    for proto in ("cv12", "loro48", "loso3"):
        folds = build_folds(rows, proto)
        picks_map = {
            "fixed_best_sbs": np.empty(n, dtype=int),
            "stump_1d": np.empty(n, dtype=int),
            "knn5": np.empty(n, dtype=int),
            "ridge": np.empty(n, dtype=int),
            "pairwise_cs": np.empty(n, dtype=int),
            "pairwise_plain": np.empty(n, dtype=int),
            "rf_reg": np.empty(n, dtype=int),
            "rf_pairwise_cs": np.empty(n, dtype=int),
        }
        stump_log = []
        for f_i, (tr, te) in enumerate(folds):
            picks_map["fixed_best_sbs"][te] = pick_fixed_sbs(y[tr], te.size)
            st_p, st_spec = pick_stump_1d(x[tr], y[tr], x[te])
            picks_map["stump_1d"][te] = st_p
            stump_log.append({
                "fold": f_i,
                "feature": FEATURE_NAMES[st_spec["feat"]] if st_spec["feat"] >= 0 else "none",
                "threshold": round(st_spec["thr"], 5),
                "left": members[st_spec["left"]],
                "right": members[st_spec["right"]],
            })
            picks_map["knn5"][te] = pick_knn5(x[tr], y[tr], x[te])
            picks_map["ridge"][te] = pick_ridge_cv(x[tr], y[tr], x[te])
            picks_map["pairwise_cs"][te] = pick_pairwise(x[tr], y[tr], x[te], weighted=True)
            picks_map["pairwise_plain"][te] = pick_pairwise(x[tr], y[tr], x[te], weighted=False)
            rf_pred, _ = fit_predict_rf_reg(x[tr], y[tr], x[te], seed=20261122 + f_i)
            picks_map["rf_reg"][te] = np.argmin(rf_pred, axis=1)
            picks_map["rf_pairwise_cs"][te] = fit_predict_rf_pairwise_cs(x[tr], y[tr], x[te], seed=20261122 + f_i)

        # Reference SBS cost for Bootstrap CI: in-fold fixed_best_sbs (avoids peeking!)
        infold_sbs_costs = y[np.arange(n), picks_map["fixed_best_sbs"]]
        protocols_out[proto] = {
            sel: summarize_picks(rows, members, y, picks, infold_sbs_costs)
            for sel, picks in picks_map.items()
        }
        stump_rules[proto] = stump_log

    # Feature importance under cv12
    cv12_folds = build_folds(rows, "cv12")
    feat_imp = permutation_importance_rf(x, y, cv12_folds, repeats=8)

    return {
        "members": members,
        "global_sbs_rule": members[global_sbs_idx],
        "global_sbs_total": round(float(global_sbs_costs.sum()), 4),
        "global_vbs_total": round(float(y.min(axis=1).sum()), 4),
        "global_sbs_gap_to_vbs": round(float((global_sbs_costs.sum() - y.min(axis=1).sum()) / y.min(axis=1).sum()), 6),
        "protocols": protocols_out,
        "rf_permutation_importance_cv12": feat_imp,
        "stump_summary_loso3": stump_rules["loso3"],
    }


def main() -> int:
    rows = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    base_members = list(summary["base_members"])
    all_members = list(summary["all_members"])

    out: dict = {
        "script": "experiments/cvrp_midterm/selection_s2/select_s2.py",
        "instances": len(rows),
        "features": list(FEATURE_NAMES),
        "portfolios": {
            "pointwise_base": run_portfolio(rows, base_members),
        },
    }
    if all_members != base_members:
        out["portfolios"]["pointwise_plus_s2"] = run_portfolio(rows, all_members)

    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    # Compact console overview
    for pname, pdata in out["portfolios"].items():
        print(f"\n=== PORTFOLIO: {pname} (SBS={pdata['global_sbs_rule']}, gap={pdata['global_sbs_gap_to_vbs']*100:.2f}%) ===")
        for proto in ("cv12", "loro48", "loso3"):
            print(f"  [{proto}]")
            for sel, m in pdata["protocols"][proto].items():
                lo, hi = m["gain_ci95"]
                wtl = m["wtl_vs_fixed"]
                print(
                    f"    {sel:16s} | gap={m['gap_to_vbs']*100:5.2f}% | gain={m['gain_vs_fixed']*100:+6.2f}% "
                    f"[{lo*100:+5.2f}%, {hi*100:+5.2f}%] p={m['p_boot_one_sided']:.4f} | "
                    f"W/T/L={wtl['wins']}/{wtl['ties']}/{wtl['losses']} | net={m['mean_net_ms']:.2f}ms"
                )
        print("  Top permutation importance (cv12 rf_reg):", list(pdata["rf_permutation_importance_cv12"].items())[:6])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
