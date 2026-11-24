"""Deterministic OpenCode Go model routing and rate-card cost accounting."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping


DEFAULT_WEAK_MODEL = "deepseek-v4.1-flash"
DEFAULT_STRONG_MODEL = "deepseek-v4-pro"
DEFAULT_OPENCODE_RATE_CARD_VERSION = "opencode-go-reference/v1"


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _connect_ledger(ledger_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(ledger_path), timeout=30.0, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=FULL")
    con.execute("PRAGMA busy_timeout=5000")
    return con


def ensure_routing_table(con: sqlite3.Connection) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS routing_logical_calls (
            logical_call_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            logical_ordinal INTEGER NOT NULL,
            purpose TEXT NOT NULL,
            requested_model TEXT NOT NULL,
            route_role TEXT NOT NULL,
            created_at_utc TEXT NOT NULL,
            UNIQUE(run_id, purpose, logical_ordinal)
        )
        """
    )


@dataclass(frozen=True)
class ModelRoutingPolicy:
    """Deterministic logical-call routing policy for heterogeneous model controls."""

    enabled: bool = False
    weak_model: str = DEFAULT_WEAK_MODEL
    strong_model: str = DEFAULT_STRONG_MODEL
    strong_every_n: int = 4
    planner_model: str | None = None
    repair_model: str | None = None
    probe_model: str | None = None
    rate_card_version: str = DEFAULT_OPENCODE_RATE_CARD_VERSION
    rate_card: dict[str, dict[str, float]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.strong_every_n, int) or isinstance(self.strong_every_n, bool) or self.strong_every_n < 1:
            raise ValueError("strong_every_n_must_be_positive_int")
        if not str(self.weak_model).strip() or not str(self.strong_model).strip():
            raise ValueError("routing_models_must_be_nonempty")

    @property
    def policy_sha256(self) -> str:
        return hashlib.sha256(_canonical_json(self.to_dict()).encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "weak_model": self.weak_model,
            "strong_model": self.strong_model,
            "strong_every_n": int(self.strong_every_n),
            "planner_model": self.planner_model,
            "repair_model": self.repair_model,
            "probe_model": self.probe_model,
            "rate_card_version": self.rate_card_version,
            "rate_card": {k: dict(v) for k, v in sorted(self.rate_card.items())},
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any] | None) -> "ModelRoutingPolicy":
        if raw is None:
            return cls(enabled=False)
        return cls(
            enabled=bool(raw.get("enabled", True)),
            weak_model=str(raw.get("weak_model") or DEFAULT_WEAK_MODEL),
            strong_model=str(raw.get("strong_model") or DEFAULT_STRONG_MODEL),
            strong_every_n=int(raw.get("strong_every_n", 4)),
            planner_model=str(raw["planner_model"]) if raw.get("planner_model") else None,
            repair_model=str(raw["repair_model"]) if raw.get("repair_model") else None,
            probe_model=str(raw["probe_model"]) if raw.get("probe_model") else None,
            rate_card_version=str(raw.get("rate_card_version") or DEFAULT_OPENCODE_RATE_CARD_VERSION),
            rate_card={str(k): {str(rk): float(rv) for rk, rv in dict(v).items()} for k, v in dict(raw.get("rate_card") or {}).items()},
        )

    def select_for_ordinal(self, purpose: str, logical_ordinal: int) -> tuple[str, str]:
        """Return ``(model_alias, route_role)`` deterministically for ``logical_ordinal`` (1-based)."""
        if purpose == "eoh_probe":
            return (self.probe_model or self.weak_model), "probe"
        if purpose == "eoh_repair":
            return (self.repair_model or self.weak_model), "repair"
        if purpose in {"planner", "reflection"}:
            return (self.planner_model or self.weak_model), "planner"
        if not self.enabled:
            return self.weak_model, "single_model"
        if logical_ordinal >= 1 and logical_ordinal % self.strong_every_n == 0:
            return self.strong_model, "strong"
        return self.weak_model, "weak"


def allocate_logical_route(
    ledger_path: Path,
    *,
    run_id: str,
    purpose: str,
    policy: ModelRoutingPolicy,
    created_at_utc: str,
    existing_logical_call_id: str | None = None,
) -> dict[str, Any]:
    """Allocate or replay a durable logical routing decision in SQLite."""
    ledger_path = Path(ledger_path)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    con = _connect_ledger(ledger_path)
    try:
        con.execute("BEGIN IMMEDIATE")
        ensure_routing_table(con)
        if existing_logical_call_id:
            row = con.execute(
                "SELECT * FROM routing_logical_calls WHERE logical_call_id=? AND run_id=?",
                (existing_logical_call_id, run_id),
            ).fetchone()
            if row is not None:
                con.execute("COMMIT")
                return {
                    "logical_call_id": str(row["logical_call_id"]),
                    "logical_ordinal": int(row["logical_ordinal"]),
                    "requested_model": str(row["requested_model"]),
                    "route_role": str(row["route_role"]),
                }
        count_purpose = "eoh_generation" if purpose == "eoh_generation" else purpose
        max_ord = con.execute(
            "SELECT COALESCE(MAX(logical_ordinal), 0) FROM routing_logical_calls WHERE run_id=? AND purpose=?",
            (run_id, count_purpose),
        ).fetchone()[0]
        logical_ordinal = int(max_ord) + 1
        model_alias, route_role = policy.select_for_ordinal(purpose, logical_ordinal)
        logical_id = existing_logical_call_id or f"lcall_{uuid.uuid4().hex}"
        con.execute(
            """
            INSERT INTO routing_logical_calls(
                logical_call_id, run_id, logical_ordinal, purpose, requested_model, route_role, created_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (logical_id, run_id, logical_ordinal, count_purpose, model_alias, route_role, created_at_utc),
        )
        con.execute("COMMIT")
        return {
            "logical_call_id": logical_id,
            "logical_ordinal": logical_ordinal,
            "requested_model": model_alias,
            "route_role": route_role,
        }
    except Exception:
        try:
            con.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise
    finally:
        con.close()


def extract_provider_usage(parsed: Mapping[str, Any] | None) -> dict[str, Any]:
    """Extract served model, request ID, and token counts preserving 0 vs None."""
    if not isinstance(parsed, Mapping):
        return {
            "served_model": None,
            "provider_request_id": None,
            "input_tokens": None,
            "output_tokens": None,
            "cached_tokens": None,
        }
    usage = parsed.get("usage") if isinstance(parsed.get("usage"), Mapping) else {}
    in_tok = usage.get("prompt_tokens", usage.get("input_tokens"))
    out_tok = usage.get("completion_tokens", usage.get("output_tokens"))
    details = usage.get("prompt_tokens_details") if isinstance(usage.get("prompt_tokens_details"), Mapping) else {}
    cached_tok = usage.get("cached_tokens", details.get("cached_tokens"))
    served = parsed.get("model")
    req_id = parsed.get("id")
    return {
        "served_model": str(served) if isinstance(served, str) and served.strip() else None,
        "provider_request_id": str(req_id) if isinstance(req_id, str) and req_id.strip() else None,
        "input_tokens": int(in_tok) if type(in_tok) is int and in_tok >= 0 else None,
        "output_tokens": int(out_tok) if type(out_tok) is int and out_tok >= 0 else None,
        "cached_tokens": int(cached_tok) if type(cached_tok) is int and cached_tok >= 0 else None,
    }


def compute_attempt_cost_usd(
    *,
    model_alias: str | None,
    input_tokens: int | None,
    output_tokens: int | None,
    cached_tokens: int | None,
    rate_card: Mapping[str, Mapping[str, float]] | None,
) -> tuple[float | None, bool, str | None]:
    """Price one provider attempt in USD; return ``(cost_usd, priced, reason)`` cleanly."""
    if not model_alias or not isinstance(rate_card, Mapping) or model_alias not in rate_card:
        return None, False, "missing_rate_card"
    if input_tokens is None or output_tokens is None:
        return None, False, "missing_token_usage"
    if input_tokens < 0 or output_tokens < 0:
        return None, False, "negative_token_usage"
    rates = rate_card[model_alias]
    if "input_per_m" not in rates or "output_per_m" not in rates:
        return None, False, "incomplete_rate_card"
    in_rate = float(rates["input_per_m"])
    out_rate = float(rates["output_per_m"])
    cache_rate_raw = rates.get("cache_read_per_m")
    if cached_tokens is None:
        if cache_rate_raw is not None and float(cache_rate_raw) != in_rate:
            return None, False, "missing_cached_tokens_for_split_rate"
        uncached = input_tokens
        cached = 0
        cache_rate = in_rate
    else:
        if cached_tokens < 0 or cached_tokens > input_tokens:
            return None, False, "invalid_cached_token_bounds"
        uncached = input_tokens - cached_tokens
        cached = cached_tokens
        cache_rate = float(cache_rate_raw) if cache_rate_raw is not None else in_rate
    usd = (uncached * in_rate + cached * cache_rate + output_tokens * out_rate) / 1_000_000.0
    return round(usd, 8), True, None
