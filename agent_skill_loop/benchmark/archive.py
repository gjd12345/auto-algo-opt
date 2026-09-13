"""Training archive and locked selection views for v1.1 experiments."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Iterable, Mapping

from .contracts import FrozenSelection, sha256_text


def _is_sha256(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)


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
    candidate_id: str = ""
    revision: str = "original"
    algorithm: str = ""
    algorithm_text_sha256: str = ""
    source_ref: str | None = None
    first_evaluation_order: int = 0

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
            "candidate_id": self.candidate_id,
            "revision": self.revision,
            "algorithm": self.algorithm,
            "algorithm_text_sha256": self.algorithm_text_sha256,
            "source_ref": self.source_ref,
            "first_evaluation_order": self.first_evaluation_order,
        }


def build_archive(rows: Iterable[Mapping[str, Any]], *, problem_spec_hash: str, data_manifest_hash: str,
                  evaluator_hash: str, metric_spec_hash: str) -> list[ArchiveEntry]:
    """Dedupe generated algorithms only within one complete evaluation identity."""
    found: dict[str, ArchiveEntry] = {}
    for order, row in enumerate(rows):
        evaluation = row.get("evaluation") if isinstance(row.get("evaluation"), Mapping) else row
        if not isinstance(evaluation, Mapping) or evaluation.get("valid") is not True:
            continue
        origin = str(row.get("origin") or "")
        if origin not in {"generated", "generated_repair"}:
            continue
        if not isinstance(row.get("candidate_id"), str) or not row.get("candidate_id"):
            continue
        if not isinstance(row.get("evaluation_id"), str) or not row.get("evaluation_id"):
            continue
        revision = str(row.get("revision") or "original")
        if origin == "generated" and revision != "original":
            continue
        if origin == "generated_repair" and revision != "repair_1":
            continue
        code = row.get("code")
        code_hash = row.get("code_sha256")
        objective = evaluation.get("objective")
        if not isinstance(code, str) or not code.strip() or not isinstance(code_hash, str) or isinstance(objective, bool) or not isinstance(objective, (int, float)) or not math.isfinite(float(objective)):
            continue
        if code_hash != sha256_text(code):
            continue
        identity_values = (row.get("problem_spec_hash"), row.get("data_manifest_hash"), row.get("evaluator_hash"), row.get("metric_spec_hash"))
        expected_identity = (problem_spec_hash, data_manifest_hash, evaluator_hash, metric_spec_hash)
        if any(not isinstance(value, str) or value != expected for value, expected in zip(identity_values, expected_identity)):
            continue
        source_ref = row.get("source_ref") or row.get("evaluation_ref") or f"evaluation:{row['evaluation_id']}"
        entry = ArchiveEntry(code=code, code_sha256=code_hash, objective=float(objective), evaluation_id=row["evaluation_id"],
                             problem_spec_hash=problem_spec_hash, data_manifest_hash=data_manifest_hash,
                             evaluator_hash=evaluator_hash, metric_spec_hash=metric_spec_hash,
                             origin=origin, candidate_id=row["candidate_id"], revision=revision,
                             algorithm=str(row.get("algorithm") or ""),
                             algorithm_text_sha256=str(row.get("algorithm_text_sha256") or ""),
                             source_ref=str(source_ref), first_evaluation_order=order)
        key = code_hash + ":" + ":".join(expected_identity)
        current = found.get(key)
        if current is None or entry.objective < current.objective:
            # The best later re-evaluation may replace the score, but the
            # discovery/provenance fields remain the first valid generated
            # member.  This prevents a duplicate code with a later, different
            # description or revision from changing who discovered it.
            found[key] = entry if current is None else ArchiveEntry(
                **{
                    **entry.as_dict(),
                    "candidate_id": current.candidate_id,
                    "revision": current.revision,
                    "algorithm": current.algorithm,
                    "algorithm_text_sha256": current.algorithm_text_sha256,
                    "origin": current.origin,
                    "source_ref": current.source_ref,
                    "first_evaluation_order": current.first_evaluation_order,
                }
            )
    return sorted(found.values(), key=lambda item: (item.objective, item.first_evaluation_order))


def freeze_selection(kind: str, entries: Iterable[ArchiveEntry] = (), *, metric_spec_hash: str,
                     source_ref: str | None = None, k: int | None = None, population_snapshot=None) -> FrozenSelection:
    values = list(entries)
    if kind == "incumbent_top1":
        values = _validate_archive_entries(values, metric_spec_hash)
        values = sorted(values, key=lambda item: (item.objective, item.first_evaluation_order))[:1]
    elif kind == "archive_topk":
        if k is None:
            raise ValueError("archive_topk_requires_k")
        values = _validate_archive_entries(values, metric_spec_hash)
        values = sorted(values, key=lambda item: (item.objective, item.first_evaluation_order))[:k]
    elif kind == "final_population_set":
        if population_snapshot is None:
            raise ValueError("final_population_requires_snapshot")
        if population_snapshot.metric_spec_hash != metric_spec_hash:
            raise ValueError("final_population_metric_mismatch")
        values = [dict(item) for item in population_snapshot.members]
    else:
        raise ValueError("invalid_selection_kind")
    if not values:
        raise ValueError("selection_has_no_members")
    return FrozenSelection(selection_kind=kind, members=tuple(item.as_dict() if hasattr(item, "as_dict") else dict(item) for item in values),
                           training_metric_spec_hash=metric_spec_hash, source_ref=source_ref, k_requested=k)


def _validate_archive_entries(entries: list[ArchiveEntry | Mapping[str, Any]], metric_spec_hash: str) -> list[ArchiveEntry]:
    """Validate the persisted archive boundary before creating a test set.

    ``freeze-selection`` is a provenance boundary, so accepting an arbitrary
    JSON object here would let a seed, baseline, or hand-written score enter a
    benchmark result.  Only entries produced by ``build_archive`` (or an
    equivalent fully populated record) are allowed.
    """
    validated: list[ArchiveEntry] = []
    for item in entries:
        if isinstance(item, ArchiveEntry):
            entry = item
        elif isinstance(item, Mapping):
            required = {
                "code", "code_sha256", "objective", "evaluation_id",
                "problem_spec_hash", "data_manifest_hash", "evaluator_hash",
                "metric_spec_hash", "origin", "candidate_id", "revision",
            }
            if not required.issubset(item):
                raise ValueError("archive_entry_identity_missing")
            try:
                entry = ArchiveEntry(
                    code=str(item["code"]),
                    code_sha256=str(item["code_sha256"]),
                    objective=float(item["objective"]),
                    evaluation_id=str(item["evaluation_id"]),
                    problem_spec_hash=str(item["problem_spec_hash"]),
                    data_manifest_hash=str(item["data_manifest_hash"]),
                    evaluator_hash=str(item["evaluator_hash"]),
                    metric_spec_hash=str(item["metric_spec_hash"]),
                    origin=str(item["origin"]),
                    candidate_id=str(item["candidate_id"]),
                    revision=str(item["revision"]),
                    algorithm=str(item.get("algorithm") or ""),
                    algorithm_text_sha256=str(item.get("algorithm_text_sha256") or ""),
                    source_ref=str(item.get("source_ref")) if item.get("source_ref") is not None else None,
                    first_evaluation_order=int(item.get("first_evaluation_order", 0)),
                )
            except (TypeError, ValueError, OverflowError) as exc:
                raise ValueError("archive_entry_invalid") from exc
        else:
            raise ValueError("archive_entry_invalid")
        if (
            not entry.code.strip()
            or entry.code_sha256 != sha256_text(entry.code)
            or not _is_sha256(entry.problem_spec_hash)
            or not _is_sha256(entry.data_manifest_hash)
            or not _is_sha256(entry.evaluator_hash)
            or not _is_sha256(entry.metric_spec_hash)
            or not entry.evaluation_id
            or not entry.candidate_id
            or entry.origin not in {"generated", "generated_repair"}
            or (entry.origin == "generated" and entry.revision != "original")
            or (entry.origin == "generated_repair" and entry.revision != "repair_1")
            or entry.metric_spec_hash != metric_spec_hash
            or not math.isfinite(float(entry.objective))
            or (entry.algorithm_text_sha256 and entry.algorithm_text_sha256 != sha256_text(entry.algorithm))
        ):
            raise ValueError("archive_entry_identity_invalid")
        validated.append(entry)
    return validated
