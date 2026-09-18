"""Bounded, deterministic behavior evidence for one evaluator invocation.

The digest covers every observed event.  Samples are diagnostic excerpts only
and are never used as a substitute for the full digest or as a ranking signal.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections import deque
from typing import Any, Mapping


SCHEMA_VERSION = "algorithm-optimization-behavior-evidence/v1"


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def behavior_contract_hash(contract: Mapping[str, Any]) -> str:
    return _digest({"schema_version": SCHEMA_VERSION, "contract": dict(contract)})


class BehaviorTraceRecorder:
    """Hash complete ordered event streams while retaining bounded excerpts."""

    def __init__(self, *, contract: Mapping[str, Any], suite_hash: str, sample_size: int = 4) -> None:
        self.contract = dict(contract)
        self.contract_hash = behavior_contract_hash(self.contract)
        self.suite_hash = str(suite_hash)
        self.sample_size = max(0, int(sample_size))
        self._overhead_ns = 0
        self.instances: list[dict[str, Any]] = []
        self._current: dict[str, Any] | None = None

    def begin_instance(self, *, instance_id: str, instance_index: int) -> None:
        started = time.perf_counter_ns()
        if self._current is not None:
            raise ValueError("behavior_instance_already_open")
        self._current = {
            "instance_id": str(instance_id),
            "instance_index": int(instance_index),
            "digest": hashlib.sha256(),
            "event_count": 0,
            "first": [],
            "last": deque(maxlen=self.sample_size),
        }
        self._overhead_ns += time.perf_counter_ns() - started

    def record(self, event: Mapping[str, Any]) -> None:
        started = time.perf_counter_ns()
        if self._current is None:
            raise ValueError("behavior_instance_not_open")
        normalized = dict(event)
        encoded = _canonical(normalized)
        self._current["digest"].update(len(encoded).to_bytes(8, "big"))
        self._current["digest"].update(encoded)
        self._current["event_count"] += 1
        if len(self._current["first"]) < self.sample_size:
            self._current["first"].append(normalized)
        self._current["last"].append(normalized)
        self._overhead_ns += time.perf_counter_ns() - started

    def finish_instance(self, *, status: str, terminal: Mapping[str, Any] | None = None) -> None:
        started = time.perf_counter_ns()
        if self._current is None:
            return
        current = self._current
        first = list(current["first"])
        last = list(current["last"])
        # Avoid duplicating the same short trace in first/last excerpts.
        if current["event_count"] <= self.sample_size:
            last = []
        row = {
            "instance_id": current["instance_id"],
            "instance_index": current["instance_index"],
            "status": status,
            "event_count": current["event_count"],
            "trace_sha256": current["digest"].hexdigest(),
            "sample_first": first,
            "sample_last": last,
            "terminal": dict(terminal or {}),
        }
        self.instances.append(row)
        self._current = None
        self._overhead_ns += time.perf_counter_ns() - started

    def finalize(self, *, status: str) -> dict[str, Any]:
        started = time.perf_counter_ns()
        if self._current is not None:
            self.finish_instance(status="partial")
        comparable = status == "complete" and bool(self.instances) and all(
            row["status"] == "complete" for row in self.instances
        )
        signature_payload = {
            "behavior_contract_hash": self.contract_hash,
            "suite_hash": self.suite_hash,
            "instances": [
                {
                    "instance_id": row["instance_id"],
                    "instance_index": row["instance_index"],
                    "event_count": row["event_count"],
                    "trace_sha256": row["trace_sha256"],
                    "terminal": row["terminal"],
                }
                for row in self.instances
            ],
        }
        value = {
            "schema_version": SCHEMA_VERSION,
            "status": status,
            "comparable": comparable,
            "behavior_contract": self.contract,
            "behavior_contract_hash": self.contract_hash,
            "suite_hash": self.suite_hash,
            "observed_instance_count": len(self.instances),
            "observed_event_count": sum(row["event_count"] for row in self.instances),
            "behavior_signature": _digest(signature_payload) if comparable else None,
            "instances": self.instances,
        }
        self._overhead_ns += time.perf_counter_ns() - started
        value["observer_elapsed_seconds"] = round(self._overhead_ns / 1_000_000_000, 6)
        return value


class ObservedCandidateError(ValueError):
    """Candidate failure carrying the behavior observed before failure."""

    def __init__(self, original: BaseException, evidence: Mapping[str, Any]) -> None:
        super().__init__(str(original))
        self.original = original
        self.behavior_evidence = dict(evidence)


class ObserverFailure(RuntimeError):
    """Trusted observation failed; this is not a candidate-code diagnosis."""


def combine_behavior_evidence(
    rows: list[Mapping[str, Any]], *, suite_hash: str, expected_instances: int | None = None
) -> dict[str, Any] | None:
    """Combine one-instance evidence emitted by the partial-evaluation path."""
    evidence = [row for row in rows if isinstance(row, Mapping)]
    if not evidence:
        return None
    contract_hashes = {row.get("behavior_contract_hash") for row in evidence}
    if len(contract_hashes) != 1 or None in contract_hashes:
        return None
    instances = []
    for index, row in enumerate(evidence):
        values = row.get("instances")
        if not isinstance(values, list):
            return None
        instances.extend({**item, "instance_index": index} for item in values if isinstance(item, Mapping))
    complete = (
        (expected_instances is None or len(evidence) == expected_instances)
        and all(row.get("status") == "complete" and row.get("comparable") is True for row in evidence)
    )
    payload = {
        "behavior_contract_hash": next(iter(contract_hashes)),
        "suite_hash": suite_hash,
        "instances": [
            {key: item.get(key) for key in ("instance_id", "instance_index", "event_count", "trace_sha256", "terminal")}
            for item in instances
        ],
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "complete" if complete else "partial",
        "comparable": complete,
        "behavior_contract": evidence[0].get("behavior_contract"),
        "behavior_contract_hash": next(iter(contract_hashes)),
        "suite_hash": suite_hash,
        "observed_instance_count": len(instances),
        "observed_event_count": sum(int(item.get("event_count") or 0) for item in instances),
        "behavior_signature": _digest(payload) if complete else None,
        "instances": instances,
        "observer_elapsed_seconds": round(sum(float(row.get("observer_elapsed_seconds") or 0) for row in evidence), 6),
    }
