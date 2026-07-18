from __future__ import annotations

import numpy as np
import pytest

from eoh_rag.experiments.pairwise_selector import PairwiseCostSensitiveSelector


def test_cost_weight_changes_choice_when_rare_mistake_is_expensive() -> None:
    """少数高代价实例应压过多数几乎无损的 0-1 分类票。"""

    train_features = np.zeros((4, 1), dtype=float)
    train_costs = np.asarray(
        [
            [0.00, 0.01],
            [0.00, 0.01],
            [0.00, 0.01],
            [1.00, 0.00],
        ],
        dtype=float,
    )
    test_features = np.zeros((1, 1), dtype=float)

    unweighted = PairwiseCostSensitiveSelector(
        cost_sensitive=False,
        n_estimators=99,
        random_state=2011,
    ).fit(train_features, train_costs)
    weighted = PairwiseCostSensitiveSelector(
        cost_sensitive=True,
        n_estimators=99,
        random_state=2011,
    ).fit(train_features, train_costs)

    assert unweighted.predict(test_features).tolist() == [0]
    assert weighted.predict(test_features).tolist() == [1]


def test_all_ties_choose_smallest_algorithm_index_deterministically() -> None:
    """全体算法等价时不得引入随机漂移或伪造训练信号。"""

    selector = PairwiseCostSensitiveSelector(random_state=2011).fit(
        np.asarray([[0.0], [1.0]], dtype=float),
        np.zeros((2, 3), dtype=float),
    )

    assert selector.predict(np.asarray([[0.5], [2.0]], dtype=float)).tolist() == [
        0,
        0,
    ]


def test_maximization_uses_the_same_pairwise_contract() -> None:
    """通用选择器只切换目标方向，不复制另一套实现。"""

    selector = PairwiseCostSensitiveSelector(
        objective_direction="maximize",
        random_state=2011,
    ).fit(
        np.asarray([[0.0], [1.0]], dtype=float),
        np.asarray([[0.0, 1.0], [0.0, 2.0]], dtype=float),
    )

    assert selector.predict(np.asarray([[0.5]], dtype=float)).tolist() == [1]


def test_fit_rejects_zero_feature_columns_before_model_training() -> None:
    with pytest.raises(ValueError, match="at least one feature"):
        PairwiseCostSensitiveSelector().fit(
            np.empty((2, 0), dtype=float),
            np.asarray([[0.0, 1.0], [1.0, 0.0]], dtype=float),
        )
