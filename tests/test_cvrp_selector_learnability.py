from __future__ import annotations

import numpy as np

from eoh_rag.experiments.reports.analyze_cvrp_selector_learnability import (
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
