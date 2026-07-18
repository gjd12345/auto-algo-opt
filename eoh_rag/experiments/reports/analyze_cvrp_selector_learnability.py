"""只用冻结 development 数据诊断 CVRP expert selector 的可学习性。

本模块是离线 ``external_teacher`` 诊断，不生成正式科研 Agent 候选，也不读取
confirmation。它借鉴算法选择的 feature matrix + performance matrix 视角，用固定
交叉验证协议回答：九个冻结特征是否包含可预测的专家互补信号。
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from eoh_rag.experiments.pairwise_selector import (
    PairwiseCostSensitiveSelector,
)
from eoh_rag.experiments.research_contracts import canonical_json_sha256
from official_eoh.examples.cvrp_expert_router.cvrp_expert_router_problem import (
    CVRPEXPERTROUTER,
)


def _standardize_from_train(
    train_features: np.ndarray,
    test_features: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """只用训练折统计量标准化，避免测试折信息泄漏。"""
    center = np.mean(train_features, axis=0)
    scale = np.std(train_features, axis=0)
    scale = np.where(scale > 1e-12, scale, 1.0)
    return (train_features - center) / scale, (test_features - center) / scale


def predict_knn_cost(
    train_features: np.ndarray,
    train_relative_costs: np.ndarray,
    test_features: np.ndarray,
    *,
    k: int,
) -> np.ndarray:
    """以训练邻居的逐专家平均成本做 cost-sensitive kNN 选择。"""
    if len(train_features) == 0 or len(train_features) != len(train_relative_costs):
        raise ValueError("training features and costs must be non-empty and aligned")
    if k <= 0:
        raise ValueError("k must be positive")
    standardized_train, standardized_test = _standardize_from_train(
        train_features,
        test_features,
    )
    effective_k = min(k, len(standardized_train))
    predictions: list[int] = []
    for row in standardized_test:
        distances = np.sum((standardized_train - row) ** 2, axis=1)
        neighbor_indices = np.argsort(distances, kind="stable")[:effective_k]
        predicted_costs = np.mean(
            train_relative_costs[neighbor_indices],
            axis=0,
        )
        predictions.append(int(np.argmin(predicted_costs)))
    return np.asarray(predictions, dtype=int)


def build_stratified_folds(
    environments: Iterable[str],
    *,
    fold_count: int = 5,
) -> list[tuple[np.ndarray, np.ndarray]]:
    """按环境分层、按冻结顺序轮转分折，完全确定且不使用随机数。"""
    environment_values = np.asarray(list(environments), dtype=object)
    if fold_count < 2:
        raise ValueError("fold_count must be at least two")
    test_buckets: list[list[int]] = [[] for _ in range(fold_count)]
    for environment in sorted(set(environment_values.tolist())):
        indices = np.flatnonzero(environment_values == environment)
        for offset, index in enumerate(indices):
            test_buckets[offset % fold_count].append(int(index))
    all_indices = np.arange(len(environment_values), dtype=int)
    folds: list[tuple[np.ndarray, np.ndarray]] = []
    for bucket in test_buckets:
        test_indices = np.asarray(sorted(bucket), dtype=int)
        train_indices = np.setdiff1d(all_indices, test_indices, assume_unique=True)
        folds.append((train_indices, test_indices))
    return folds


def build_leave_one_environment_out_folds(
    environments: Iterable[str],
) -> list[tuple[np.ndarray, np.ndarray]]:
    environment_values = np.asarray(list(environments), dtype=object)
    all_indices = np.arange(len(environment_values), dtype=int)
    folds: list[tuple[np.ndarray, np.ndarray]] = []
    for environment in sorted(set(environment_values.tolist())):
        test_indices = np.flatnonzero(environment_values == environment)
        train_indices = np.setdiff1d(all_indices, test_indices, assume_unique=True)
        folds.append((train_indices, test_indices))
    return folds


def cross_validated_predictions(
    features: np.ndarray,
    relative_costs: np.ndarray,
    folds: list[tuple[np.ndarray, np.ndarray]],
    *,
    k_values: tuple[int, ...] = (1, 3, 5, 9),
    pairwise_n_estimators: int = 99,
    pairwise_random_state: int = 2011,
    pairwise_backup_minimum_vote_margin: int = 0,
) -> dict[str, np.ndarray]:
    """每个测试实例只由不含自身的训练折产生一次预测。"""
    if pairwise_backup_minimum_vote_margin < 0:
        raise ValueError("pairwise_backup_minimum_vote_margin must be non-negative")
    sample_count = len(features)
    predictions = {
        "single_best_train": np.full(sample_count, -1, dtype=int),
        **{
            f"cost_knn_k{k}": np.full(sample_count, -1, dtype=int)
            for k in k_values
        },
        "pairwise_forest_unweighted": np.full(sample_count, -1, dtype=int),
        "pairwise_forest_cost_weighted": np.full(
            sample_count,
            -1,
            dtype=int,
        ),
        "pairwise_forest_unweighted_tie_backup": np.full(
            sample_count,
            -1,
            dtype=int,
        ),
    }
    for fold_index, (train_indices, test_indices) in enumerate(folds):
        if len(train_indices) == 0 or len(test_indices) == 0:
            raise ValueError("each fold must contain train and test instances")
        single_best = int(np.argmin(np.mean(relative_costs[train_indices], axis=0)))
        predictions["single_best_train"][test_indices] = single_best
        for k in k_values:
            predictions[f"cost_knn_k{k}"][test_indices] = predict_knn_cost(
                features[train_indices],
                relative_costs[train_indices],
                features[test_indices],
                k=k,
            )
        for method_name, cost_sensitive in (
            ("pairwise_forest_unweighted", False),
            ("pairwise_forest_cost_weighted", True),
        ):
            selector = PairwiseCostSensitiveSelector(
                cost_sensitive=cost_sensitive,
                n_estimators=pairwise_n_estimators,
                # 两个消融臂使用同一棵随机森林结构；fold 偏移只避免跨折复用随机流。
                random_state=pairwise_random_state + fold_index,
            ).fit(
                features[train_indices],
                relative_costs[train_indices],
            )
            predictions[method_name][test_indices] = selector.predict(
                features[test_indices]
            )
            if not cost_sensitive:
                # 后备算法只能由训练折决定，避免测试实例的真实成本反向影响路由。
                predictions["pairwise_forest_unweighted_tie_backup"][
                    test_indices
                ] = selector.predict_with_backup(
                    features[test_indices],
                    backup_algorithm_index=single_best,
                    minimum_vote_margin=pairwise_backup_minimum_vote_margin,
                )
    if any(np.any(values < 0) for values in predictions.values()):
        raise ValueError("cross-validation did not predict every instance exactly once")
    return predictions


def summarize_predictions(
    predictions: np.ndarray,
    relative_costs: np.ndarray,
    environments: list[str],
    expert_ids: list[str],
) -> dict[str, Any]:
    row_indices = np.arange(len(predictions), dtype=int)
    selected = relative_costs[row_indices, predictions]
    oracle = np.min(relative_costs, axis=1)
    selection_counts = Counter(expert_ids[int(index)] for index in predictions)
    environment_improvements = {
        environment: -100.0
        * float(np.mean(selected[np.asarray(environments) == environment]))
        for environment in sorted(set(environments))
    }
    tolerance = 1e-12
    return {
        "mean_improvement_vs_n2_pct": -100.0 * float(np.mean(selected)),
        "median_improvement_vs_n2_pct": -100.0 * float(np.median(selected)),
        "mean_regret_to_oracle_pct": 100.0 * float(np.mean(selected - oracle)),
        "oracle_cost_match_rate": float(
            np.mean(np.abs(selected - oracle) <= tolerance)
        ),
        "better_same_worse_vs_n2": {
            "better": int(np.sum(selected < -tolerance)),
            "same": int(np.sum(np.abs(selected) <= tolerance)),
            "worse": int(np.sum(selected > tolerance)),
        },
        "environment_improvement_vs_n2_pct": environment_improvements,
        "worst_environment_improvement_vs_n2_pct": min(
            environment_improvements.values()
        ),
        "expert_selection_counts": {
            expert_id: int(selection_counts.get(expert_id, 0))
            for expert_id in expert_ids
        },
    }


def assess_pairwise_ablation(
    *,
    weighted: dict[str, Any],
    unweighted: dict[str, Any],
    current_knn: dict[str, Any],
) -> dict[str, Any]:
    """按预注册 development 门禁判断代价权重是否值得进入 selector-v2。"""

    mean_key = "mean_improvement_vs_n2_pct"
    worst_key = "worst_environment_improvement_vs_n2_pct"
    weighted_mean = float(weighted[mean_key])
    unweighted_mean = float(unweighted[mean_key])
    current_mean = float(current_knn[mean_key])
    weighted_worst = float(weighted[worst_key])
    unweighted_worst = float(unweighted[worst_key])
    current_worst = float(current_knn[worst_key])
    tolerance = 1e-12
    gate_checks = {
        "positive_mean_improvement": weighted_mean > tolerance,
        "better_mean_than_unweighted": (
            weighted_mean - unweighted_mean > tolerance
        ),
        "better_mean_than_current_knn": (
            weighted_mean - current_mean > tolerance
        ),
        "worst_environment_not_worse_than_unweighted": (
            weighted_worst + tolerance >= unweighted_worst
        ),
        "worst_environment_not_worse_than_current_knn": (
            weighted_worst + tolerance >= current_worst
        ),
    }
    return {
        "primary_protocol": "leave_one_environment_out",
        "weighted_minus_unweighted_mean_improvement_pct": (
            weighted_mean - unweighted_mean
        ),
        "weighted_minus_current_knn_mean_improvement_pct": (
            weighted_mean - current_mean
        ),
        "gate_checks": gate_checks,
        "decision": (
            "promote_to_selector_v2_dev_candidate"
            if all(gate_checks.values())
            else "do_not_promote"
        ),
    }


def assess_backup_ablation(
    *,
    backup: dict[str, Any],
    unweighted: dict[str, Any],
) -> dict[str, Any]:
    """判断固定后备是否在不牺牲原选择器的前提下改善开发期稳健性。"""

    mean_key = "mean_improvement_vs_n2_pct"
    worst_key = "worst_environment_improvement_vs_n2_pct"
    backup_mean = float(backup[mean_key])
    unweighted_mean = float(unweighted[mean_key])
    backup_worst = float(backup[worst_key])
    unweighted_worst = float(unweighted[worst_key])
    tolerance = 1e-12
    gate_checks = {
        "positive_mean_improvement": backup_mean > tolerance,
        "mean_not_worse_than_unweighted": (
            backup_mean + tolerance >= unweighted_mean
        ),
        "worst_environment_not_worse_than_unweighted": (
            backup_worst + tolerance >= unweighted_worst
        ),
    }
    return {
        "primary_protocol": "leave_one_environment_out",
        "backup_minus_unweighted_mean_improvement_pct": (
            backup_mean - unweighted_mean
        ),
        "backup_minus_unweighted_worst_environment_improvement_pct": (
            backup_worst - unweighted_worst
        ),
        "gate_checks": gate_checks,
        "decision": (
            "promote_to_selector_v2_dev_candidate"
            if all(gate_checks.values())
            else "do_not_promote"
        ),
    }


def _collect_development_matrix() -> dict[str, Any]:
    problem = CVRPEXPERTROUTER(timeout=180, n_processes=1)
    feature_order = list(problem.contract["feature_order"])
    expert_ids = list(problem.expert_ids)
    features = np.asarray(
        [
            [float(instance["features"][name]) for name in feature_order]
            for instance in problem.development_instances
        ],
        dtype=float,
    )
    environments = [
        str(instance["environment"]) for instance in problem.development_instances
    ]
    seeds = [int(instance["seed"]) for instance in problem.development_instances]
    relative_cost_rows: list[list[float]] = []
    fallback_cells = 0
    for costs in problem.expert_costs:
        reference = costs["n2"]
        if reference is None or reference <= 0:
            raise ValueError("n2 must be feasible on every development instance")
        row: list[float] = []
        for expert_id in expert_ids:
            selected = costs[expert_id]
            if selected is None:
                # 与正式 evaluator 一致：冻结专家失败时回退 n2，因此有效相对成本为零。
                selected = reference
                fallback_cells += 1
            row.append((float(selected) - float(reference)) / float(reference))
        relative_cost_rows.append(row)
    relative_costs = np.asarray(relative_cost_rows, dtype=float)
    data_rows = [
        {
            "environment": environment,
            "seed": seed,
            "features": {
                name: float(value)
                for name, value in zip(feature_order, feature_row)
            },
            "relative_cost_vs_n2": {
                expert_id: float(value)
                for expert_id, value in zip(expert_ids, cost_row)
            },
        }
        for environment, seed, feature_row, cost_row in zip(
            environments,
            seeds,
            features,
            relative_costs,
        )
    ]
    return {
        "features": features,
        "relative_costs": relative_costs,
        "environments": environments,
        "seeds": seeds,
        "feature_order": feature_order,
        "expert_ids": expert_ids,
        "fallback_cells": fallback_cells,
        "dataset_hash": canonical_json_sha256(data_rows),
        "contract_sha256": problem.contract_sha256.lower(),
        "contract_oracle_improvement_pct": float(
            problem.contract["dev_oracle_report_only"][
                "mean_improvement_vs_n2_pct"
            ]
        ),
    }


def analyze_development_learnability() -> dict[str, Any]:
    data = _collect_development_matrix()
    features = data.pop("features")
    relative_costs = data.pop("relative_costs")
    environments = data["environments"]
    expert_ids = data["expert_ids"]
    oracle_predictions = np.argmin(relative_costs, axis=1)
    oracle_metrics = summarize_predictions(
        oracle_predictions,
        relative_costs,
        environments,
        expert_ids,
    )
    if not np.isclose(
        oracle_metrics["mean_improvement_vs_n2_pct"],
        data["contract_oracle_improvement_pct"],
        atol=1e-10,
    ):
        raise ValueError("development oracle no longer matches the frozen contract")

    protocol_folds = {
        "stratified_5fold": build_stratified_folds(environments, fold_count=5),
        "leave_one_environment_out": build_leave_one_environment_out_folds(
            environments
        ),
    }
    protocols: dict[str, Any] = {}
    for protocol_name, folds in protocol_folds.items():
        predictions = cross_validated_predictions(
            features,
            relative_costs,
            folds,
        )
        protocols[protocol_name] = {
            "fold_count": len(folds),
            "methods": {
                name: summarize_predictions(
                    values,
                    relative_costs,
                    environments,
                    expert_ids,
                )
                for name, values in predictions.items()
            },
        }

    stratified_k5 = protocols["stratified_5fold"]["methods"]["cost_knn_k5"]
    loeo_k5 = protocols["leave_one_environment_out"]["methods"]["cost_knn_k5"]
    loeo_methods = protocols["leave_one_environment_out"]["methods"]
    pairwise_ablation = assess_pairwise_ablation(
        weighted=loeo_methods["pairwise_forest_cost_weighted"],
        unweighted=loeo_methods["pairwise_forest_unweighted"],
        current_knn=loeo_k5,
    )
    backup_ablation = assess_backup_ablation(
        backup=loeo_methods["pairwise_forest_unweighted_tie_backup"],
        unweighted=loeo_methods["pairwise_forest_unweighted"],
    )
    if (
        stratified_k5["mean_improvement_vs_n2_pct"] > 0
        and loeo_k5["mean_improvement_vs_n2_pct"] > 0
    ):
        assessment = "features_show_cross_environment_predictive_signal"
    elif stratified_k5["mean_improvement_vs_n2_pct"] > 0:
        assessment = "features_show_within_distribution_signal_only"
    else:
        assessment = "fixed_k5_has_no_positive_cross_validated_signal"

    return {
        "schema_version": "cvrp_selector_learnability_dev/v3",
        "status": "exploratory_complete",
        "actor": "codex",
        "provenance": "external_teacher_diagnostic",
        "data_scope": "development_only",
        "confirmation_accessed": False,
        "sample_count": len(environments),
        **data,
        "oracle_report_only": oracle_metrics,
        "protocols": protocols,
        "pairwise_ablation": {
            "provenance": "Hydra-MIP external method reference",
            "n_estimators": 99,
            "random_state": 2011,
            "weighted_sample_rule": "absolute pairwise relative-cost difference",
            "unweighted_sample_rule": "uniform weight on non-tie pairwise labels",
            **pairwise_ablation,
        },
        "backup_ablation": {
            "provenance": "SATzilla2012 fallback-routing adaptation",
            "selector": "pairwise_forest_unweighted",
            "backup": "single_best_train",
            "minimum_vote_margin": 0,
            **backup_ablation,
        },
        "primary_diagnostic": {
            "method": "cost_knn_k5",
            "assessment": assessment,
            "not_a_formal_selector_candidate": True,
        },
        "next_action": (
            "restore_valid_provider_credentials_and_rerun_same_frozen_"
            "research_agent_coordinates"
        ),
    }


def _write_markdown(path: Path, result: dict[str, Any]) -> None:
    lines = [
        "# CVRP Selector Development Learnability Diagnostic",
        "",
        f"- status: `{result['status']}`",
        f"- provenance: `{result['provenance']}`",
        f"- data_scope: `{result['data_scope']}`",
        f"- confirmation_accessed: `{result['confirmation_accessed']}`",
        f"- sample_count: `{result['sample_count']}`",
        f"- dataset_hash: `{result['dataset_hash']}`",
        f"- assessment: `{result['primary_diagnostic']['assessment']}`",
        "",
        "## Report-only oracle",
        "",
        (
            "- mean_improvement_vs_n2_pct: "
            f"`{result['oracle_report_only']['mean_improvement_vs_n2_pct']:.6f}`"
        ),
        "",
    ]
    for protocol_name, protocol in result["protocols"].items():
        lines.extend(
            [
                f"## {protocol_name}",
                "",
                "| method | mean improvement vs n2 (%) | mean regret to oracle (%) | oracle match | worst environment improvement (%) |",
                "|---|---:|---:|---:|---:|",
            ]
        )
        for method_name, metrics in protocol["methods"].items():
            lines.append(
                f"| {method_name} "
                f"| {metrics['mean_improvement_vs_n2_pct']:.6f} "
                f"| {metrics['mean_regret_to_oracle_pct']:.6f} "
                f"| {metrics['oracle_cost_match_rate']:.4f} "
                f"| {metrics['worst_environment_improvement_vs_n2_pct']:.6f} |"
            )
        lines.append("")
    lines.extend(
        [
            "## Pairwise cost-sensitive ablation",
            "",
            f"- decision: `{result['pairwise_ablation']['decision']}`",
            (
                "- primary_protocol: "
                f"`{result['pairwise_ablation']['primary_protocol']}`"
            ),
            (
                "- weighted_minus_unweighted_mean_improvement_pct: "
                f"`{result['pairwise_ablation']['weighted_minus_unweighted_mean_improvement_pct']:.6f}`"
            ),
            (
                "- weighted_minus_current_knn_mean_improvement_pct: "
                f"`{result['pairwise_ablation']['weighted_minus_current_knn_mean_improvement_pct']:.6f}`"
            ),
            "",
            "### Gate checks",
            "",
            *[
                f"- {name}: `{passed}`"
                for name, passed in result["pairwise_ablation"][
                    "gate_checks"
                ].items()
            ],
            "",
            "## Fixed-backup abstention ablation",
            "",
            f"- decision: `{result['backup_ablation']['decision']}`",
            (
                "- backup_minus_unweighted_mean_improvement_pct: "
                f"`{result['backup_ablation']['backup_minus_unweighted_mean_improvement_pct']:.6f}`"
            ),
            (
                "- backup_minus_unweighted_worst_environment_improvement_pct: "
                f"`{result['backup_ablation']['backup_minus_unweighted_worst_environment_improvement_pct']:.6f}`"
            ),
            "",
            "### Gate checks",
            "",
            *[
                f"- {name}: `{passed}`"
                for name, passed in result["backup_ablation"]["gate_checks"].items()
            ],
            "",
            "## Evidence boundary",
            "",
            "- This is a deterministic development-only external-teacher diagnostic.",
            "- No confirmation instance or cost is loaded.",
            "- No method is promoted to a formal research-agent candidate from this report.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-md", type=Path, required=True)
    args = parser.parse_args()
    result = analyze_development_learnability()
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_markdown(args.output_md, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
