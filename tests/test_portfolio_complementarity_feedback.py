from __future__ import annotations

import json

import pytest

from eoh_rag.experiments.portfolio_feedback import assess_portfolio_candidate


def test_complementary_candidate_can_pass_both_development_gates() -> None:
    """候选即使单体均值更差，只要补齐盲区且真实 selector 改善，就应保留。"""

    assessment = assess_portfolio_candidate(
        candidate_id="candidate-a",
        candidate_code_hash="candidate-hash",
        incumbent_code_hashes=("expert-1-hash", "expert-2-hash"),
        objective_direction="minimize",
        generation_instance_ids=("g1", "g2", "g3", "g4"),
        incumbent_portfolio_objectives=(10.0, 10.0, 10.0, 10.0),
        candidate_objectives=(5.0, 20.0, 20.0, 20.0),
        candidate_feasible=(True, True, True, True),
        validation_instance_ids=("v1", "v2"),
        baseline_selector_objectives=(10.0, 10.0),
        expanded_selector_objectives=(9.0, 9.0),
    )

    assert assessment.standalone_mean_gain == -6.25
    assert assessment.oracle_mean_gain == 1.25
    assert assessment.real_selector_mean_gain == 1.0
    assert assessment.decision == "accept_for_v2_pool"
    assert assessment.gate_checks == {
        "development_only": True,
        "disjoint_validation": True,
        "code_hash_unique": True,
        "candidate_feasible": True,
        "oracle_gain": True,
        "real_selector_gain": True,
    }


def test_oracle_gain_without_real_selector_gain_is_rejected() -> None:
    """理想组合上界不能替代不相交 development 上的真实 selector 效果。"""

    assessment = assess_portfolio_candidate(
        candidate_id="candidate-oracle-only",
        candidate_code_hash="candidate-hash",
        incumbent_code_hashes=("expert-hash",),
        objective_direction="minimize",
        generation_instance_ids=("g1", "g2"),
        incumbent_portfolio_objectives=(10.0, 10.0),
        candidate_objectives=(5.0, 20.0),
        candidate_feasible=(True, True),
        validation_instance_ids=("v1", "v2"),
        baseline_selector_objectives=(10.0, 10.0),
        expanded_selector_objectives=(9.0, 11.0),
    )

    assert assessment.oracle_mean_gain == 2.5
    assert assessment.real_selector_mean_gain == 0.0
    assert assessment.gate_checks["oracle_gain"] is True
    assert assessment.gate_checks["real_selector_gain"] is False
    assert assessment.oracle_only_not_sufficient is True
    assert assessment.decision == "reject_candidate"


def test_generation_and_selector_validation_instances_must_be_disjoint() -> None:
    """同一 development 实例不能既塑造候选，又证明真实 selector 增益。"""

    with pytest.raises(ValueError, match="不相交"):
        assess_portfolio_candidate(
            candidate_id="candidate-leaky",
            candidate_code_hash="candidate-hash",
            incumbent_code_hashes=("expert-hash",),
            objective_direction="minimize",
            generation_instance_ids=("shared",),
            incumbent_portfolio_objectives=(10.0,),
            candidate_objectives=(9.0,),
            candidate_feasible=(True,),
            validation_instance_ids=("shared",),
            baseline_selector_objectives=(10.0,),
            expanded_selector_objectives=(9.0,),
        )


def test_confirmation_scope_cannot_enter_portfolio_generation_feedback() -> None:
    """confirmation 只能最终报告，不能进入 v2 候选生成或裁剪反馈。"""

    with pytest.raises(ValueError, match="dev_only"):
        assess_portfolio_candidate(
            candidate_id="candidate-confirmation-leak",
            candidate_code_hash="candidate-hash",
            incumbent_code_hashes=("expert-hash",),
            objective_direction="minimize",
            generation_instance_ids=("g1",),
            incumbent_portfolio_objectives=(10.0,),
            candidate_objectives=(9.0,),
            candidate_feasible=(True,),
            validation_instance_ids=("v1",),
            baseline_selector_objectives=(10.0,),
            expanded_selector_objectives=(9.0,),
            observed_scope="confirmation",
        )


def test_duplicate_candidate_code_is_rejected_even_when_scores_improve() -> None:
    """同一实现的不同证据阶段不能被误算成新专家。"""

    assessment = assess_portfolio_candidate(
        candidate_id="candidate-duplicate",
        candidate_code_hash="same-hash",
        incumbent_code_hashes=("same-hash", "other-hash"),
        objective_direction="minimize",
        generation_instance_ids=("g1",),
        incumbent_portfolio_objectives=(10.0,),
        candidate_objectives=(8.0,),
        candidate_feasible=(True,),
        validation_instance_ids=("v1",),
        baseline_selector_objectives=(10.0,),
        expanded_selector_objectives=(8.0,),
    )

    assert assessment.gate_checks["code_hash_unique"] is False
    assert assessment.decision == "reject_candidate"


def test_code_hash_deduplication_is_case_insensitive() -> None:
    assessment = assess_portfolio_candidate(
        candidate_id="candidate-duplicate-case",
        candidate_code_hash="abcdef",
        incumbent_code_hashes=("ABCDEF",),
        objective_direction="minimize",
        generation_instance_ids=("g1",),
        incumbent_portfolio_objectives=(10.0,),
        candidate_objectives=(8.0,),
        candidate_feasible=(True,),
        validation_instance_ids=("v1",),
        baseline_selector_objectives=(10.0,),
        expanded_selector_objectives=(8.0,),
    )

    assert assessment.gate_checks["code_hash_unique"] is False
    assert assessment.decision == "reject_candidate"


def test_infeasible_candidate_cannot_buy_portfolio_gain() -> None:
    assessment = assess_portfolio_candidate(
        candidate_id="candidate-infeasible",
        candidate_code_hash="candidate-hash",
        incumbent_code_hashes=("expert-hash",),
        objective_direction="minimize",
        generation_instance_ids=("g1", "g2"),
        incumbent_portfolio_objectives=(10.0, 10.0),
        candidate_objectives=(1.0, 1.0),
        candidate_feasible=(True, False),
        validation_instance_ids=("v1",),
        baseline_selector_objectives=(10.0,),
        expanded_selector_objectives=(1.0,),
    )

    assert assessment.gate_checks["candidate_feasible"] is False
    assert assessment.decision == "reject_candidate"


def test_per_instance_evidence_must_be_nonempty_finite_and_aligned() -> None:
    """禁止 zip 静默截断错位坐标，或让 NaN 进入科研反馈。"""

    with pytest.raises(ValueError, match="generation"):
        assess_portfolio_candidate(
            candidate_id="candidate-misaligned",
            candidate_code_hash="candidate-hash",
            incumbent_code_hashes=("expert-hash",),
            objective_direction="minimize",
            generation_instance_ids=("g1", "g2"),
            incumbent_portfolio_objectives=(10.0, 10.0),
            candidate_objectives=(9.0,),
            candidate_feasible=(True, True),
            validation_instance_ids=("v1",),
            baseline_selector_objectives=(10.0,),
            expanded_selector_objectives=(9.0,),
        )

    with pytest.raises(ValueError, match="finite"):
        assess_portfolio_candidate(
            candidate_id="candidate-nan",
            candidate_code_hash="candidate-hash",
            incumbent_code_hashes=("expert-hash",),
            objective_direction="minimize",
            generation_instance_ids=("g1",),
            incumbent_portfolio_objectives=(10.0,),
            candidate_objectives=(float("nan"),),
            candidate_feasible=(True,),
            validation_instance_ids=("v1",),
            baseline_selector_objectives=(10.0,),
            expanded_selector_objectives=(9.0,),
        )


def test_instance_ids_must_be_unique_within_each_development_split() -> None:
    """重复坐标会暗中改变实例权重，必须在反馈编译前拒绝。"""

    with pytest.raises(ValueError, match="unique"):
        assess_portfolio_candidate(
            candidate_id="candidate-duplicate-coordinate",
            candidate_code_hash="candidate-hash",
            incumbent_code_hashes=("expert-hash",),
            objective_direction="minimize",
            generation_instance_ids=("g1", "g1"),
            incumbent_portfolio_objectives=(10.0, 10.0),
            candidate_objectives=(9.0, 9.0),
            candidate_feasible=(True, True),
            validation_instance_ids=("v1",),
            baseline_selector_objectives=(10.0,),
            expanded_selector_objectives=(9.0,),
        )


def test_maximization_problem_uses_the_same_complementarity_contract() -> None:
    """最大化问题只改变增益方向，不复制另一套反馈实现。"""

    assessment = assess_portfolio_candidate(
        candidate_id="candidate-max",
        candidate_code_hash="candidate-hash",
        incumbent_code_hashes=("expert-hash",),
        objective_direction="maximize",
        generation_instance_ids=("g1", "g2"),
        incumbent_portfolio_objectives=(10.0, 10.0),
        candidate_objectives=(20.0, 0.0),
        candidate_feasible=(True, True),
        validation_instance_ids=("v1",),
        baseline_selector_objectives=(10.0,),
        expanded_selector_objectives=(12.0,),
    )

    assert assessment.standalone_mean_gain == 0.0
    assert assessment.oracle_mean_gain == 5.0
    assert assessment.real_selector_mean_gain == 2.0
    assert assessment.decision == "accept_for_v2_pool"


def test_assessment_serializes_scope_and_evidence_counts() -> None:
    """反馈必须能直接进入证据账本，并显式声明没有读取 confirmation。"""

    assessment = assess_portfolio_candidate(
        candidate_id="candidate-ledger",
        candidate_code_hash="candidate-hash",
        incumbent_code_hashes=("expert-hash",),
        objective_direction="minimize",
        generation_instance_ids=("g1", "g2"),
        incumbent_portfolio_objectives=(10.0, 10.0),
        candidate_objectives=(9.0, 11.0),
        candidate_feasible=(True, True),
        validation_instance_ids=("v1",),
        baseline_selector_objectives=(10.0,),
        expanded_selector_objectives=(9.0,),
    )

    payload = assessment.to_dict()
    assert payload["observed_scope"] == "dev_only"
    assert payload["confirmation_accessed"] is False
    assert payload["generation_instance_count"] == 2
    assert payload["validation_instance_count"] == 1
    assert payload["objective_direction"] == "minimize"
    assert payload["minimum_oracle_mean_gain"] == 0.0
    assert payload["minimum_selector_mean_gain"] == 0.0
    json.dumps(payload)


def test_gain_thresholds_must_be_finite_and_nonnegative() -> None:
    with pytest.raises(ValueError, match="threshold"):
        assess_portfolio_candidate(
            candidate_id="candidate-invalid-threshold",
            candidate_code_hash="candidate-hash",
            incumbent_code_hashes=("expert-hash",),
            objective_direction="minimize",
            generation_instance_ids=("g1",),
            incumbent_portfolio_objectives=(10.0,),
            candidate_objectives=(10.0,),
            candidate_feasible=(True,),
            validation_instance_ids=("v1",),
            baseline_selector_objectives=(10.0,),
            expanded_selector_objectives=(10.0,),
            minimum_oracle_mean_gain=-1.0,
        )
