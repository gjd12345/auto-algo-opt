from __future__ import annotations

import numpy as np

from eoh_rag.experiments.reports.analyze_cvrp_selector_learnability import (
    assess_pairwise_ablation,
    build_leave_one_environment_out_folds,
    build_stratified_folds,
    cross_validated_predictions,
    predict_knn_cost,
    summarize_predictions,
)


def test_cost_knn_uses_training_costs_to_recover_local_expert() -> None:
    train_features = np.asarray([[-2.0], [-1.0], [1.0], [2.0]])
    # n2 始终为 0；expert_a 只在负半轴更优。
    train_costs = np.asarray(
        [
            [0.0, -0.20],
            [0.0, -0.10],
            [0.0, 0.10],
            [0.0, 0.20],
        ]
    )
    predictions = predict_knn_cost(
        train_features,
        train_costs,
        np.asarray([[-1.5], [1.5]]),
        k=1,
    )
    assert predictions.tolist() == [1, 0]


def test_cross_validation_folds_cover_each_instance_once() -> None:
    environments = ["a"] * 10 + ["b"] * 10 + ["c"] * 10
    for folds in (
        build_stratified_folds(environments, fold_count=5),
        build_leave_one_environment_out_folds(environments),
    ):
        test_indices = np.concatenate([test for _, test in folds])
        assert sorted(test_indices.tolist()) == list(range(30))
        for train, test in folds:
            assert not set(train.tolist()) & set(test.tolist())


def test_cross_validated_metrics_keep_n2_and_oracle_directions_clear() -> None:
    features = np.asarray([[-2.0], [-1.0], [1.0], [2.0]])
    relative_costs = np.asarray(
        [
            [0.0, -0.20],
            [0.0, -0.10],
            [0.0, 0.10],
            [0.0, 0.20],
        ]
    )
    folds = [
        (np.asarray([1, 3]), np.asarray([0, 2])),
        (np.asarray([0, 2]), np.asarray([1, 3])),
    ]
    predictions = cross_validated_predictions(
        features,
        relative_costs,
        folds,
        k_values=(1,),
    )
    metrics = summarize_predictions(
        predictions["cost_knn_k1"],
        relative_costs,
        ["a", "a", "b", "b"],
        ["n2", "expert_a"],
    )
    assert metrics["mean_improvement_vs_n2_pct"] >= 0
    assert metrics["mean_regret_to_oracle_pct"] >= 0
    assert sum(metrics["expert_selection_counts"].values()) == 4


def test_cross_validation_reports_weighted_pairwise_ablation() -> None:
    """同一折和随机种子下必须同时给出加权与非加权 pairwise 结果。"""

    features = np.asarray([[-2.0], [-1.0], [1.0], [2.0]])
    relative_costs = np.asarray(
        [
            [0.0, -0.01],
            [0.0, -0.01],
            [0.0, -0.01],
            [1.0, 0.0],
        ]
    )
    folds = [
        (np.asarray([1, 2, 3]), np.asarray([0])),
        (np.asarray([0, 2, 3]), np.asarray([1])),
        (np.asarray([0, 1, 3]), np.asarray([2])),
        (np.asarray([0, 1, 2]), np.asarray([3])),
    ]

    predictions = cross_validated_predictions(
        features,
        relative_costs,
        folds,
        k_values=(1,),
    )

    assert "pairwise_forest_unweighted" in predictions
    assert "pairwise_forest_cost_weighted" in predictions
    assert all(len(values) == 4 for values in predictions.values())


def test_pairwise_ablation_requires_realized_and_worst_environment_gains() -> None:
    """加权模型必须同时超过无权重模型、当前 kNN 和零改善线。"""

    assessment = assess_pairwise_ablation(
        weighted={
            "mean_improvement_vs_n2_pct": 1.0,
            "worst_environment_improvement_vs_n2_pct": -0.1,
        },
        unweighted={
            "mean_improvement_vs_n2_pct": 0.5,
            "worst_environment_improvement_vs_n2_pct": -0.2,
        },
        current_knn={
            "mean_improvement_vs_n2_pct": 0.8,
            "worst_environment_improvement_vs_n2_pct": -0.1,
        },
    )

    assert assessment["gate_checks"] == {
        "positive_mean_improvement": True,
        "better_mean_than_unweighted": True,
        "better_mean_than_current_knn": True,
        "worst_environment_not_worse_than_unweighted": True,
        "worst_environment_not_worse_than_current_knn": True,
    }
    assert assessment["decision"] == "promote_to_selector_v2_dev_candidate"
