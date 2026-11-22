"""Direction-2 portfolio complementarity and out-of-fold algorithm selection.

Computes SBS, Oracle (VBS), and out-of-fold / cross-suite frozen selectors with
strictly separated timing (``feat_ms``, ``infer_ms``, ``solve_ms``, ``total_ms``),
paired Bootstrap 95% CIs, and per-instance selection & mistake records so
CLI and frontend Page 4 -> Page 3 drill-down share identical source rows.
"""

from __future__ import annotations

import time
from typing import Any, Mapping, Sequence

import numpy as np

from experiments.cvrp_midterm.selection_s2.select_s2 import (
    FEATURE_NAMES,
    RegTree,
    build_folds,
    fit_predict_rf_pairwise_cs,
    fit_predict_rf_reg,
    pick_fixed_sbs,
    pick_knn5,
    pick_pairwise,
    pick_ridge_cv,
    pick_stump_1d,
    relative_regret_matrix,
)


def _paired_bootstrap_gain(chosen: np.ndarray, sbs: np.ndarray, n_boot: int = 10000, seed: int = 20261122) -> tuple[float, list[float], float]:
    n = chosen.size
    total_sbs = float(sbs.sum())
    total_chosen = float(chosen.sum())
    gain = (total_sbs - total_chosen) / max(total_sbs, 1e-12)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(n_boot, n))
    boot_chosen = chosen[idx].sum(axis=1)
    boot_sbs = sbs[idx].sum(axis=1)
    boot_gain = (boot_sbs - boot_chosen) / np.maximum(boot_sbs, 1e-12)
    ci_lo, ci_hi = np.quantile(boot_gain, [0.025, 0.975])
    p_one = float(np.mean(boot_gain <= 0.0))
    return gain, [round(float(ci_lo), 6), round(float(ci_hi), 6)], round(p_one, 4)


def _summarize_selector_picks(
    rows: list[dict[str, Any]],
    members: list[str],
    y: np.ndarray,
    solve_ms_mat: np.ndarray,
    picks: np.ndarray,
    sbs_picks: np.ndarray,
    *,
    infer_ms: np.ndarray,
    uses_features: bool,
    selector_id: str,
    n_boot: int = 10000,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    n = len(rows)
    chosen = y[np.arange(n), picks]
    sbs_costs = y[np.arange(n), sbs_picks]
    oracle_idx = np.argmin(y, axis=1)
    vbs = y[np.arange(n), oracle_idx]

    total_chosen = float(chosen.sum())
    total_vbs = float(vbs.sum())
    total_sbs = float(sbs_costs.sum())
    regrets = (chosen - vbs) / np.maximum(vbs, 1e-12)
    gain_vs_sbs, ci95, p_boot = _paired_bootstrap_gain(chosen, sbs_costs, n_boot=n_boot)

    wins = int(np.sum(chosen < sbs_costs - 1e-12))
    losses = int(np.sum(chosen > sbs_costs + 1e-12))
    ties = n - wins - losses

    feat_ms = (
        np.array([float(r["feat_ms"]) for r in rows], dtype=float)
        if uses_features
        else np.zeros(n, dtype=float)
    )
    inf_ms = np.asarray(infer_ms, dtype=float) if uses_features else np.zeros(n, dtype=float)
    solve_ms = np.array([float(solve_ms_mat[i, picks[i]]) for i in range(n)], dtype=float)
    total_ms = feat_ms + inf_ms + solve_ms

    pick_counts = {
        members[k]: int(np.sum(picks == k))
        for k in range(len(members))
        if int(np.sum(picks == k)) > 0
    }

    # Per-scale breakdown
    by_scale: dict[str, dict[str, Any]] = {}
    for sz in sorted({int(r["size"]) for r in rows}):
        mask = np.array([int(r["size"]) == sz for r in rows])
        c_sub = chosen[mask]
        v_sub = vbs[mask]
        s_sub = sbs_costs[mask]
        by_scale[str(sz)] = {
            "n_instances": int(mask.sum()),
            "total": round(float(c_sub.sum()), 4),
            "mean": round(float(c_sub.mean()), 4),
            "gap_to_vbs": round(float((c_sub.sum() - v_sub.sum()) / max(v_sub.sum(), 1e-12)), 6),
            "gain_vs_sbs": round(float((s_sub.sum() - c_sub.sum()) / max(s_sub.sum(), 1e-12)), 6),
            "mean_regret": round(float(np.mean((c_sub - v_sub) / np.maximum(v_sub, 1e-12))), 6),
            "picks": {
                members[k]: int(np.sum(picks[mask] == k))
                for k in range(len(members))
                if int(np.sum(picks[mask] == k)) > 0
            },
        }

    # Per-instance decision & mistake records (shared source for Page 4 -> Page 3 drill-down)
    per_instance_decisions: list[dict[str, Any]] = []
    for i, r in enumerate(rows):
        sel_alg = members[int(picks[i])]
        ora_alg = members[int(oracle_idx[i])]
        sbs_alg = members[int(sbs_picks[i])]
        sel_cost = float(chosen[i])
        ora_cost = float(vbs[i])
        sbs_cost = float(sbs_costs[i])
        reg_rel = float((sel_cost - ora_cost) / max(ora_cost, 1e-12))
        delta_sbs_rel = float((sbs_cost - sel_cost) / max(sbs_cost, 1e-12))
        is_mistake = sel_cost > ora_cost + 1e-9
        worse_than_sbs = sel_cost > sbs_cost + 1e-9
        per_instance_decisions.append({
            "instance_id": r["instance_id"],
            "cell": r.get("cell"),
            "size": int(r["size"]),
            "spatial": r.get("spatial"),
            "selected_algorithm": sel_alg,
            "oracle_algorithm": ora_alg,
            "sbs_algorithm": sbs_alg,
            "selected_cost": round(sel_cost, 6),
            "oracle_cost": round(ora_cost, 6),
            "sbs_cost": round(sbs_cost, 6),
            "regret_abs": round(sel_cost - ora_cost, 6),
            "regret_rel": round(reg_rel, 6),
            "gain_vs_sbs_rel": round(delta_sbs_rel, 6),
            "is_mistake_vs_oracle": bool(is_mistake),
            "worse_than_sbs": bool(worse_than_sbs),
            "feat_ms": round(float(feat_ms[i]), 4),
            "infer_ms": round(float(inf_ms[i]), 4),
            "solve_ms": round(float(solve_ms[i]), 4),
            "total_ms": round(float(total_ms[i]), 4),
        })

    mistake_count = sum(1 for d in per_instance_decisions if d["is_mistake_vs_oracle"])
    summary = {
        "selector_id": selector_id,
        "uses_features": uses_features,
        "n_instances": n,
        "total": round(total_chosen, 4),
        "mean": round(total_chosen / max(n, 1), 4),
        "vbs_total": round(total_vbs, 4),
        "sbs_total": round(total_sbs, 4),
        "gap_to_vbs": round((total_chosen - total_vbs) / max(total_vbs, 1e-12), 6),
        "gain_vs_sbs": round(gain_vs_sbs, 6),
        "gain_ci95": ci95,
        "p_boot_one_sided": p_boot,
        "wtl_vs_sbs": {"wins": wins, "ties": ties, "losses": losses},
        "mistake_count_vs_oracle": mistake_count,
        "oracle_hit_rate": round((n - mistake_count) / max(n, 1), 4),
        "mean_regret": round(float(regrets.mean()), 6),
        "worst_regret": round(float(regrets.max()), 6),
        "mean_feat_ms": round(float(feat_ms.mean()), 4),
        "mean_infer_ms": round(float(inf_ms.mean()), 4),
        "mean_solve_ms": round(float(solve_ms.mean()), 4),
        "mean_total_ms": round(float(total_ms.mean()), 4),
        "total_ms_p50": round(float(np.percentile(total_ms, 50)), 4),
        "total_ms_p95": round(float(np.percentile(total_ms, 95)), 4),
        "picks": pick_counts,
        "by_scale": by_scale,
    }
    return summary, per_instance_decisions


def _run_selectors_on_split(
    x_tr: np.ndarray,
    y_tr: np.ndarray,
    x_te: np.ndarray,
    *,
    seed: int = 20261122,
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    n_te = x_te.shape[0]
    picks: dict[str, np.ndarray] = {}
    infer_ms: dict[str, np.ndarray] = {}

    picks["fixed_best_sbs"] = pick_fixed_sbs(y_tr, n_te)
    infer_ms["fixed_best_sbs"] = np.zeros(n_te, dtype=float)

    st_p, _st_spec, st_inf = pick_stump_1d(x_tr, y_tr, x_te, min_leaf=max(4, min(12, x_tr.shape[0] // 8)), return_infer_ms=True)
    picks["stump_1d"] = st_p
    infer_ms["stump_1d"] = st_inf

    p_knn, inf_knn = pick_knn5(x_tr, y_tr, x_te, k_nn=min(5, max(1, x_tr.shape[0] - 1)), return_infer_ms=True)
    picks["knn5"] = p_knn
    infer_ms["knn5"] = inf_knn

    p_ridge, inf_ridge = pick_ridge_cv(x_tr, y_tr, x_te, return_infer_ms=True)
    picks["ridge"] = p_ridge
    infer_ms["ridge"] = inf_ridge

    p_pw_cs, inf_pw_cs = pick_pairwise(x_tr, y_tr, x_te, weighted=True, return_infer_ms=True)
    picks["pairwise_cs"] = p_pw_cs
    infer_ms["pairwise_cs"] = inf_pw_cs

    p_pw_pl, inf_pw_pl = pick_pairwise(x_tr, y_tr, x_te, weighted=False, return_infer_ms=True)
    picks["pairwise_plain"] = p_pw_pl
    infer_ms["pairwise_plain"] = inf_pw_pl

    rf_pred, _trees, inf_rf = fit_predict_rf_reg(
        x_tr,
        y_tr,
        x_te,
        n_trees=40,
        max_depth=4,
        min_leaf=max(3, min(6, x_tr.shape[0] // 12)),
        max_features=4,
        seed=seed,
        return_infer_ms=True,
    )
    picks["rf_reg"] = np.argmin(rf_pred, axis=1)
    infer_ms["rf_reg"] = inf_rf

    p_rf_pw, inf_rf_pw = fit_predict_rf_pairwise_cs(
        x_tr,
        y_tr,
        x_te,
        n_trees=20,
        max_depth=3,
        min_leaf=max(4, min(8, x_tr.shape[0] // 10)),
        max_features=4,
        seed=seed,
        return_infer_ms=True,
    )
    picks["rf_pairwise_cs"] = p_rf_pw
    infer_ms["rf_pairwise_cs"] = inf_rf_pw

    return picks, infer_ms


def evaluate_oof_portfolio(
    suite_id: str,
    portfolio_id: str,
    rows: list[dict[str, Any]],
    members: Sequence[str],
    *,
    protocols: Sequence[str] = ("cv12", "loro48", "loso3"),
    n_boot: int = 10000,
) -> dict[str, Any]:
    """Run out-of-fold algorithm selection across protocols on one suite."""
    members_list = list(members)
    n = len(rows)
    x = np.array([[float(r["features"][f]) for f in FEATURE_NAMES] for r in rows], dtype=float)
    y = np.array([[float(r["costs"][m]) for m in members_list] for r in rows], dtype=float)
    solve_ms_mat = np.array([[float(r["solve_ms"][m]) for m in members_list] for r in rows], dtype=float)

    global_sbs_idx = int(np.argmin(y.sum(axis=0)))
    global_sbs_costs = y[:, global_sbs_idx]
    oracle_idx = np.argmin(y, axis=1)
    oracle_costs = y[np.arange(n), oracle_idx]
    oracle_counts = {
        members_list[k]: int(np.sum(oracle_idx == k))
        for k in range(len(members_list))
        if int(np.sum(oracle_idx == k)) > 0
    }

    by_scale_comp: dict[str, dict[str, Any]] = {}
    for sz in sorted({int(r["size"]) for r in rows}):
        mask = np.array([int(r["size"]) == sz for r in rows])
        y_sub = y[mask]
        sbs_sub_idx = int(np.argmin(y_sub.sum(axis=0)))
        sbs_sub_total = float(y_sub[:, sbs_sub_idx].sum())
        vbs_sub_total = float(y_sub.min(axis=1).sum())
        ora_sub = np.argmin(y_sub, axis=1)
        by_scale_comp[str(sz)] = {
            "n_instances": int(mask.sum()),
            "sbs_algorithm": members_list[sbs_sub_idx],
            "sbs_total": round(sbs_sub_total, 4),
            "vbs_total": round(vbs_sub_total, 4),
            "sbs_gap_to_vbs": round((sbs_sub_total - vbs_sub_total) / max(vbs_sub_total, 1e-12), 6),
            "oracle_counts": {
                members_list[k]: int(np.sum(ora_sub == k))
                for k in range(len(members_list))
                if int(np.sum(ora_sub == k)) > 0
            },
        }

    protocols_out: dict[str, dict[str, Any]] = {}
    selector_names = (
        "fixed_best_sbs",
        "stump_1d",
        "knn5",
        "ridge",
        "pairwise_cs",
        "pairwise_plain",
        "rf_reg",
        "rf_pairwise_cs",
    )
    for proto in protocols:
        folds = build_folds(rows, proto)
        picks_map = {sel: np.empty(n, dtype=int) for sel in selector_names}
        infer_map = {sel: np.zeros(n, dtype=float) for sel in selector_names}
        for f_i, (tr, te) in enumerate(folds):
            fold_picks, fold_inf = _run_selectors_on_split(x[tr], y[tr], x[te], seed=20261122 + f_i)
            for sel in selector_names:
                picks_map[sel][te] = fold_picks[sel]
                infer_map[sel][te] = fold_inf[sel]

        # Oracle reference row (no feature/infer overhead; exact per-instance best)
        oracle_summary, _ = _summarize_selector_picks(
            rows,
            members_list,
            y,
            solve_ms_mat,
            oracle_idx,
            picks_map["fixed_best_sbs"],
            infer_ms=np.zeros(n, dtype=float),
            uses_features=False,
            selector_id="oracle_vbs",
            n_boot=n_boot,
        )

        sel_summaries: dict[str, dict[str, Any]] = {"oracle_vbs": oracle_summary}
        sel_decisions: dict[str, list[dict[str, Any]]] = {}
        for sel in selector_names:
            summ, decs = _summarize_selector_picks(
                rows,
                members_list,
                y,
                solve_ms_mat,
                picks_map[sel],
                picks_map["fixed_best_sbs"],
                infer_ms=infer_map[sel],
                uses_features=(sel != "fixed_best_sbs"),
                selector_id=sel,
                n_boot=n_boot,
            )
            sel_summaries[sel] = summ
            # Persist full per-instance decisions for key selectors (SBS + RF + Ridge + Stump + Pairwise)
            if sel in {"fixed_best_sbs", "rf_reg", "ridge", "pairwise_plain", "pairwise_cs", "stump_1d"}:
                sel_decisions[sel] = decs

        protocols_out[proto] = {
            "protocol": proto,
            "n_folds": len(folds),
            "selectors": sel_summaries,
            "per_instance_decisions": sel_decisions,
        }

    return {
        "suite_id": suite_id,
        "portfolio_id": portfolio_id,
        "evaluation_mode": "out_of_fold",
        "members": members_list,
        "n_instances": n,
        "global_sbs_algorithm": members_list[global_sbs_idx],
        "global_sbs_total": round(float(global_sbs_costs.sum()), 4),
        "global_vbs_total": round(float(oracle_costs.sum()), 4),
        "global_sbs_gap_to_vbs": round(
            float((global_sbs_costs.sum() - oracle_costs.sum()) / max(oracle_costs.sum(), 1e-12)),
            6,
        ),
        "oracle_counts": oracle_counts,
        "by_scale_complementarity": by_scale_comp,
        "protocols": protocols_out,
    }


def evaluate_frozen_transfer_portfolio(
    *,
    train_suite_id: str,
    test_suite_id: str,
    portfolio_id: str,
    train_rows: list[dict[str, Any]],
    test_rows: list[dict[str, Any]],
    members: Sequence[str],
    n_boot: int = 10000,
) -> dict[str, Any]:
    """Train frozen selectors strictly on ``train_suite`` and evaluate on isolated ``test_suite``."""
    members_list = list(members)
    x_tr = np.array([[float(r["features"][f]) for f in FEATURE_NAMES] for r in train_rows], dtype=float)
    y_tr = np.array([[float(r["costs"][m]) for m in members_list] for r in train_rows], dtype=float)
    x_te = np.array([[float(r["features"][f]) for f in FEATURE_NAMES] for r in test_rows], dtype=float)
    y_te = np.array([[float(r["costs"][m]) for m in members_list] for r in test_rows], dtype=float)
    solve_te = np.array([[float(r["solve_ms"][m]) for m in members_list] for r in test_rows], dtype=float)

    n_te = len(test_rows)
    picks_map, infer_map = _run_selectors_on_split(x_tr, y_tr, x_te, seed=20261201)
    oracle_idx = np.argmin(y_te, axis=1)
    oracle_costs = y_te[np.arange(n_te), oracle_idx]
    sbs_te_idx = int(np.argmin(y_te.sum(axis=0)))
    sbs_tr_idx = int(picks_map["fixed_best_sbs"][0])

    oracle_summary, _ = _summarize_selector_picks(
        test_rows,
        members_list,
        y_te,
        solve_te,
        oracle_idx,
        picks_map["fixed_best_sbs"],
        infer_ms=np.zeros(n_te, dtype=float),
        uses_features=False,
        selector_id="oracle_vbs",
        n_boot=n_boot,
    )
    sel_summaries: dict[str, dict[str, Any]] = {"oracle_vbs": oracle_summary}
    sel_decisions: dict[str, list[dict[str, Any]]] = {}
    for sel, picks in picks_map.items():
        summ, decs = _summarize_selector_picks(
            test_rows,
            members_list,
            y_te,
            solve_te,
            picks,
            picks_map["fixed_best_sbs"],
            infer_ms=infer_map[sel],
            uses_features=(sel != "fixed_best_sbs"),
            selector_id=sel,
            n_boot=n_boot,
        )
        sel_summaries[sel] = summ
        if sel in {"fixed_best_sbs", "rf_reg", "ridge", "pairwise_plain", "pairwise_cs", "stump_1d"}:
            sel_decisions[sel] = decs

    return {
        "suite_id": test_suite_id,
        "train_suite_id": train_suite_id,
        "portfolio_id": portfolio_id,
        "evaluation_mode": "frozen_cross_suite_transfer",
        "members": members_list,
        "n_train_instances": len(train_rows),
        "n_instances": n_te,
        "train_selected_sbs_algorithm": members_list[sbs_tr_idx],
        "test_posthoc_sbs_algorithm": members_list[sbs_te_idx],
        "global_sbs_algorithm": members_list[sbs_tr_idx],
        "global_sbs_total": round(float(y_te[:, sbs_tr_idx].sum()), 4),
        "global_vbs_total": round(float(oracle_costs.sum()), 4),
        "global_sbs_gap_to_vbs": round(
            float((y_te[:, sbs_tr_idx].sum() - oracle_costs.sum()) / max(oracle_costs.sum(), 1e-12)),
            6,
        ),
        "oracle_counts": {
            members_list[k]: int(np.sum(oracle_idx == k))
            for k in range(len(members_list))
            if int(np.sum(oracle_idx == k)) > 0
        },
        "protocols": {
            "frozen_transfer": {
                "protocol": "frozen_transfer",
                "train_suite_id": train_suite_id,
                "test_suite_id": test_suite_id,
                "selectors": sel_summaries,
                "per_instance_decisions": sel_decisions,
            }
        },
    }
