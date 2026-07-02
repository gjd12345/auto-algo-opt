from __future__ import annotations

from eoh_rag.tocc.contracts import (
    LEGACY_TOCC_SELECTED_CARDS_STRATEGY,
    TOCC_CANDIDATE_POOL_STRATEGY,
    normalize_tocc_context_strategy,
)


def test_canonical_context_strategy_is_stable() -> None:
    assert normalize_tocc_context_strategy(TOCC_CANDIDATE_POOL_STRATEGY) == TOCC_CANDIDATE_POOL_STRATEGY


def test_legacy_context_strategy_normalizes_to_candidate_pool() -> None:
    assert normalize_tocc_context_strategy(LEGACY_TOCC_SELECTED_CARDS_STRATEGY) == TOCC_CANDIDATE_POOL_STRATEGY


def test_unrelated_context_strategy_is_unchanged() -> None:
    assert normalize_tocc_context_strategy("manual_context") == "manual_context"
