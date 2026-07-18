"""通用逐实例算法选择器：用错选代价训练成对随机森林。"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

import numpy as np
from sklearn.ensemble import RandomForestClassifier


@dataclass(frozen=True)
class _PairModel:
    left_index: int
    right_index: int
    classifier: RandomForestClassifier | None
    constant_winner: int | None


class PairwiseCostSensitiveSelector:
    """从实例特征和逐算法损失矩阵学习每个实例应选择的算法。

    ``cost_sensitive=True`` 时，算法对上的样本权重等于两算法损失差；
    关闭时仍忽略完全平局，但其余样本统一使用权重 1，供严格消融。
    """

    def __init__(
        self,
        *,
        cost_sensitive: bool = True,
        objective_direction: Literal["minimize", "maximize"] = "minimize",
        n_estimators: int = 99,
        random_state: int = 0,
    ) -> None:
        if n_estimators <= 0:
            raise ValueError("n_estimators must be positive")
        if objective_direction not in {"minimize", "maximize"}:
            raise ValueError(
                "objective_direction must be minimize or maximize"
            )
        self.cost_sensitive = bool(cost_sensitive)
        self.objective_direction = objective_direction
        self.n_estimators = int(n_estimators)
        self.random_state = int(random_state)
        self._feature_count: int | None = None
        self._algorithm_count: int | None = None
        self._pair_models: list[_PairModel] = []

    def fit(
        self,
        features: np.ndarray,
        costs: np.ndarray,
    ) -> PairwiseCostSensitiveSelector:
        """拟合所有算法对；目标方向由 ``objective_direction`` 冻结。"""

        feature_matrix = np.asarray(features, dtype=float)
        cost_matrix = np.asarray(costs, dtype=float)
        if feature_matrix.ndim != 2 or cost_matrix.ndim != 2:
            raise ValueError("features and costs must both be two-dimensional")
        if len(feature_matrix) == 0 or len(feature_matrix) != len(cost_matrix):
            raise ValueError("features and costs must be non-empty and aligned")
        if feature_matrix.shape[1] == 0:
            raise ValueError("features must contain at least one feature column")
        if cost_matrix.shape[1] < 2:
            raise ValueError("costs must contain at least two algorithms")
        if not np.all(np.isfinite(feature_matrix)) or not np.all(
            np.isfinite(cost_matrix)
        ):
            raise ValueError("features and costs must contain only finite values")

        self._feature_count = int(feature_matrix.shape[1])
        self._algorithm_count = int(cost_matrix.shape[1])
        self._pair_models = []
        max_features = min(
            self._feature_count,
            int(math.floor(math.log2(max(1, self._feature_count)))) + 1,
        )
        pair_offset = 0
        for left_index in range(self._algorithm_count):
            for right_index in range(left_index + 1, self._algorithm_count):
                differences = (
                    cost_matrix[:, left_index] - cost_matrix[:, right_index]
                )
                non_tie = np.abs(differences) > 1e-15
                labels = (
                    (differences > 0).astype(int)
                    if self.objective_direction == "minimize"
                    else (differences < 0).astype(int)
                )
                sample_weights = (
                    np.abs(differences)
                    if self.cost_sensitive
                    else non_tie.astype(float)
                )
                active_labels = labels[sample_weights > 0]
                if len(active_labels) == 0:
                    # 两算法在全部训练实例上等价，固定较小索引以保证可重放。
                    pair_model = _PairModel(
                        left_index=left_index,
                        right_index=right_index,
                        classifier=None,
                        constant_winner=left_index,
                    )
                elif np.all(active_labels == active_labels[0]):
                    winner = (
                        right_index if int(active_labels[0]) == 1 else left_index
                    )
                    pair_model = _PairModel(
                        left_index=left_index,
                        right_index=right_index,
                        classifier=None,
                        constant_winner=winner,
                    )
                else:
                    classifier = RandomForestClassifier(
                        n_estimators=self.n_estimators,
                        max_features=max_features,
                        bootstrap=True,
                        n_jobs=1,
                        random_state=self.random_state + pair_offset,
                    )
                    classifier.fit(
                        feature_matrix,
                        labels,
                        sample_weight=sample_weights,
                    )
                    pair_model = _PairModel(
                        left_index=left_index,
                        right_index=right_index,
                        classifier=classifier,
                        constant_winner=None,
                    )
                self._pair_models.append(pair_model)
                pair_offset += 1
        return self

    def predict(self, features: np.ndarray) -> np.ndarray:
        """返回每个实例选择的算法列索引。"""

        if self._feature_count is None or self._algorithm_count is None:
            raise ValueError("selector must be fitted before predict")
        feature_matrix = np.asarray(features, dtype=float)
        if feature_matrix.ndim != 2 or feature_matrix.shape[1] != self._feature_count:
            raise ValueError("prediction features do not match fitted feature shape")
        if not np.all(np.isfinite(feature_matrix)):
            raise ValueError("prediction features must contain only finite values")

        sample_count = len(feature_matrix)
        votes = np.zeros((sample_count, self._algorithm_count), dtype=int)
        pair_winners: list[np.ndarray] = []
        for pair_model in self._pair_models:
            if pair_model.classifier is None:
                winners = np.full(
                    sample_count,
                    int(pair_model.constant_winner),
                    dtype=int,
                )
            else:
                pair_predictions = pair_model.classifier.predict(feature_matrix)
                winners = np.where(
                    pair_predictions == 0,
                    pair_model.left_index,
                    pair_model.right_index,
                ).astype(int)
            pair_winners.append(winners)
            votes[np.arange(sample_count), winners] += 1

        predictions: list[int] = []
        for row_index, row_votes in enumerate(votes):
            tied = np.flatnonzero(row_votes == np.max(row_votes))
            if len(tied) == 1:
                predictions.append(int(tied[0]))
                continue
            tied_set = set(int(value) for value in tied)
            secondary = {algorithm_index: 0 for algorithm_index in tied_set}
            for pair_model, winners in zip(self._pair_models, pair_winners):
                if (
                    pair_model.left_index in tied_set
                    and pair_model.right_index in tied_set
                ):
                    secondary[int(winners[row_index])] += 1
            # 论文最终随机破平局；科研证据账本需要完全可重放，因此固定较小索引。
            predictions.append(
                min(
                    secondary,
                    key=lambda algorithm_index: (
                        -secondary[algorithm_index],
                        algorithm_index,
                    ),
                )
            )
        return np.asarray(predictions, dtype=int)
