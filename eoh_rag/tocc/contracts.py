"""Stable TOCC manifest contract names and compatibility normalization."""
from __future__ import annotations


TOCC_CANDIDATE_POOL_STRATEGY = "tocc_candidate_pool"
LEGACY_TOCC_SELECTED_CARDS_STRATEGY = "tocc_selected_cards"


def normalize_tocc_context_strategy(value: str | None) -> str:
    """Normalize the legacy strategy name without rejecting unrelated modes."""
    strategy = str(value or "")
    if strategy == LEGACY_TOCC_SELECTED_CARDS_STRATEGY:
        return TOCC_CANDIDATE_POOL_STRATEGY
    return strategy
