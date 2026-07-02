"""
脚本：test_bp_card_synthesis.py
功能：验证 BP Online card 合成使用 problem-specific 词表，不泄漏 TSP/CVRP 术语
输入：无
输出：pytest 断言
用法：python3 -m pytest tests/test_bp_card_synthesis.py -v
"""

from __future__ import annotations

import pytest

from eoh_rag.rag.problem_vocab import (
    BP_FEATURE_DO,
    BP_FEATURE_WHEN,
    CVRP_FEATURE_DO,
    TSP_FEATURE_DO,
    get_feature_vocab,
)


class TestBPVocab:
    def test_bp_has_new_features(self):
        assert "same_size_reservation" in BP_FEATURE_DO
        assert "item_scaled_residual" in BP_FEATURE_DO
        assert "reusable_slack" in BP_FEATURE_DO
        assert "dead_gap_avoidance" in BP_FEATURE_DO
        assert "awkward_gap_penalty" in BP_FEATURE_DO

    def test_bp_has_matching_when(self):
        assert "same_size_reservation" in BP_FEATURE_WHEN
        assert "item_scaled_residual" in BP_FEATURE_WHEN
        assert "reusable_slack" in BP_FEATURE_WHEN
        assert "dead_gap_avoidance" in BP_FEATURE_WHEN
        assert "awkward_gap_penalty" in BP_FEATURE_WHEN

    def test_bp_vocab_no_tsp_cvrp_terms(self):
        """BP 词表不应包含 TSP/CVRP 特有术语。"""
        tsp_only_terms = {"destination", "depot", "tour", "nearest_node", "farthest"}
        cvrp_only_terms = {"depot_distance", "savings", "sweep", "capacity"}
        forbidden = tsp_only_terms | cvrp_only_terms
        bp_terms = set(BP_FEATURE_DO.keys()) | set(BP_FEATURE_WHEN.keys())
        leaked = bp_terms & forbidden
        assert leaked == set(), f"BP vocab contains forbidden terms: {leaked}"

    def test_tsp_vocab_no_bp_terms(self):
        """TSP 词表不应包含 BP 特有术语。"""
        bp_only = {"residual", "tight_fit", "utilization", "fragmentation", "bin", "gap_penalty"}
        tsp_terms = set(TSP_FEATURE_DO.keys())
        leaked = tsp_terms & bp_only
        assert leaked == set(), f"TSP vocab contains BP terms: {leaked}"

    def test_get_feature_vocab_bp(self):
        do, when = get_feature_vocab("bp_online")
        assert do is BP_FEATURE_DO
        assert when is BP_FEATURE_WHEN

    def test_get_feature_vocab_unknown(self):
        do, when = get_feature_vocab("unknown_problem")
        assert do == {}
        assert when == {}


class TestCardSynthesisBPIsolation:
    """验证 _build_content 对 BP 使用 problem-specific 词表。"""

    def test_bp_card_uses_bp_vocab(self):
        from eoh_rag.rag.card_synthesis import _build_content

        content = _build_content("bp_online", {"residual", "tight_fit"})
        # 应包含 BP 相关描述
        assert "residual" in content.lower() or "fit" in content.lower()
        # 不应包含 TSP/CVRP 术语
        assert "destination" not in content.lower()
        assert "depot" not in content.lower()
        assert "tour" not in content.lower()

    def test_bp_card_new_features(self):
        from eoh_rag.rag.card_synthesis import _build_content

        content = _build_content("bp_online", {"dead_gap_avoidance", "reusable_slack"})
        assert "gap" in content.lower() or "slack" in content.lower() or "residual" in content.lower()
