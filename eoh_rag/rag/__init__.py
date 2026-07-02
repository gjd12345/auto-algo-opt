"""Lightweight RAG utilities for InsertShips prompt context."""

from .prompt_context import format_prompt_context, format_prompt_context_with_audit
from .features import (
    STRATEGY_FEATURES,
    extract_card_features,
    extract_code_features,
    extract_identifier_tokens,
    extract_strategy_features,
    load_population_features,
    normalize_strategy_feature,
)
from .reranker import RerankConfig, retrieve_with_rerank
from .retriever import (
    retrieve,
)
from .schemas import CorpusItem, load_corpus, save_corpus

__all__ = [
    "CorpusItem",
    "RerankConfig",
    "STRATEGY_FEATURES",
    "extract_card_features",
    "extract_code_features",
    "extract_identifier_tokens",
    "extract_strategy_features",
    "format_prompt_context",
    "format_prompt_context_with_audit",
    "load_corpus",
    "load_population_features",
    "normalize_strategy_feature",
    "retrieve",
    "retrieve_with_rerank",
    "save_corpus",
]
