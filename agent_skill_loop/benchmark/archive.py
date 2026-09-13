"""Training archive and locked selection views for v1.1 experiments."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Iterable, Mapping

from .contracts import FrozenSelection, sha256_text


@dataclass(frozen=True)
class ArchiveEntry:
    """One discovered algorithm identity; re-evaluations stay in the ledger."""

    code: str
    code_sha256: str
    objective: float
    evaluation_id: str | None
    problem_spec_hash: str
    data_manifest_hash: str
    evaluator_hash: str
    metric_spec_hash: str
    origin: str
    source_ref: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "code_sha256": self.code_sha256,
            "objective": self.objective,
            "evaluation_id": self.evaluation_id,
            "problem_spec_hash": self.problem_spec_hash,
            "data_manifest_hash": self.data_manifest_hash,
            "evaluator_hash": self.evaluator_hash,
            "metric_spec_hash": self.metric_spec_hash,
            "origin": self.origin,
            "source_ref": self.source_ref,
        }


def build_archive(rows: Iterable[Mapping[str, Any]], *, problem_spec_hash: str, data_manifest_hash: str,
                  evaluator_hash: str, metric_spec_hash: str) -> list[ArchiveEntry]:
    """Dedupe algorithms by code only within one complete evaluation identity."""
    found: dict[str, ArchiveEntry] = {}
    for row in rows:
        evaluation = row.get("evaluation") if isinstance(row.get("evaluation"), Mapping) else row
        if not isinstance(evaluation, Mapping) or evaluation.get("valid") is not True:
            continue
        code = row.get("code")
        code_hash = row.get("code_sha256")
        objective = evaluation.get("objective")
        if not isinstance(code, str) or not code.strip() or not isinstance(code_hash, str) or isinstance(objective, bool) or not isinstance(objective, (int, float)) or not math.isfinite(float(objective)):
            continue
        if code_hash != sha256_text(code):
            continue
        identity = (str(row.get("problem_spec_hash") or problem_spec_hash), str(row.get("data_manifest_hash") or data_manifest_hash),
                    str(row.get("evaluator_hash") or evaluator_hash), str(row.get("metric_spec_hash") or metric_spec_hash))
        if any(
            value is not None and str(value) != expected
            for value, expected in zip(
                (row.get("problem_spec_hash"), row.get("data_manifest_hash"), row.get("evaluator_hash"), row.get("metric_spec_hash")),
                (problem_spec_hash, data_manifest_hash, evaluator_hash, metric_spec_hash),
            )
        ):
            continue
        entry = ArchiveEntry(code=code, code_sha256=code_hash, objective=float(objective), evaluation_id=row.get("evaluation_id"),
                             problem_spec_hash=identity[0], data_manifest_hash=identity[1], evaluator_hash=identity[2], metric_spec_hash=identity[3],
                             origin=str(row.get("origin") or "unknown"), source_ref=row.get("source_ref"))
        key = code_hash + ":" + ":".join(identity)
        current = found.get(key)
        if current is None or entry.objective < current.objective:
            found[key] = entry
    return sorted(found.values(), key=lambda item: (item.objective, item.code_sha256, item.evaluation_id or ""))


def freeze_selection(kind: str, entries: Iterable[ArchiveEntry], *, metric_spec_hash: str,
                     source_ref: str | None = None, k: int | None = None) -> FrozenSelection:
    values = list(entries)
    if kind == "incumbent_top1":
        values = values[:1]
    elif kind == "archive_topk":
        if k is None:
            raise ValueError("archive_topk_requires_k")
        values = values[:k]
    elif kind != "final_population_set":
        raise ValueError("invalid_selection_kind")
    return FrozenSelection(selection_kind=kind, members=tuple(item.as_dict() for item in values),
                           training_metric_spec_hash=metric_spec_hash, source_ref=source_ref, k_requested=k)
