"""Card-prior decision utilities for TOCC.

The decision file is produced by post-run audits. It is intentionally separate
from the RAG corpus: corpus cards describe possible priors, while this module
records whether a controller should accept, deprioritize, or split them.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


DEFAULT_CARD_PRIOR_DECISIONS = (
    Path("eoh_rag_workspace")
    / "reports"
    / "auto_experiment_reports"
    / "tocc_history_card_audit_20260619"
    / "card_prior_decisions.jsonl"
)

HARD_BLOCK_DECISIONS = {"split_required", "split_or_deprioritize"}
DEPRIORITIZED_DECISIONS = {"candidate_deprioritized"}
WATCHLIST_DECISIONS = {"candidate_watchlist"}


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def resolve_decision_path(path: str | Path | None = None) -> Path:
    if path:
        raw = Path(path)
        return raw if raw.is_absolute() else (_project_root() / raw).resolve()
    return (_project_root() / DEFAULT_CARD_PRIOR_DECISIONS).resolve()


@lru_cache(maxsize=8)
def load_card_prior_decisions(path: str | Path | None = None) -> dict[str, dict[str, Any]]:
    decision_path = resolve_decision_path(path)
    if not decision_path.exists():
        return {}

    decisions: dict[str, dict[str, Any]] = {}
    for line_no, line in enumerate(decision_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        item = json.loads(line)
        card_id = str(item.get("card_id", "")).strip()
        if not card_id:
            raise ValueError(f"Missing card_id in {decision_path}:{line_no}")
        decisions[card_id] = item
    return decisions


def decision_for_card(card_id: str, decisions: dict[str, dict[str, Any]] | None = None) -> dict[str, Any] | None:
    if decisions is None:
        decisions = load_card_prior_decisions()
    return decisions.get(card_id)


def decision_status(card_id: str, decisions: dict[str, dict[str, Any]] | None = None) -> str | None:
    decision = decision_for_card(card_id, decisions)
    return str(decision.get("decision")) if decision else None
