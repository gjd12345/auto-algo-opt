"""TOCC — Trace-Conditioned Operator-Card Controller."""

from .controller import diagnose, TOCCDecision
from .contracts import (
    LEGACY_TOCC_SELECTED_CARDS_STRATEGY,
    TOCC_CANDIDATE_POOL_STRATEGY,
    normalize_tocc_context_strategy,
)
from .gatekeeper import validate_proposal
from .pipeline import run_tocc_v2_cycle
from .loop import run_v3_loop

__all__ = [
    "diagnose",
    "LEGACY_TOCC_SELECTED_CARDS_STRATEGY",
    "TOCC_CANDIDATE_POOL_STRATEGY",
    "TOCCDecision",
    "normalize_tocc_context_strategy",
    "validate_proposal",
    "run_tocc_v2_cycle",
    "run_v3_loop",
]
