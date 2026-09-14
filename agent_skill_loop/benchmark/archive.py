"""Training archive and locked selection views for v1.1 experiments."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping

from .contracts import FrozenSelection, sha256_json, sha256_text


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
    # Discovery and scoring are deliberately separate.  A later re-evaluation
    # may improve the score without becoming the place that discovered the
    # algorithm.
    discovery_ref: str | None = None
    score_evaluation_ref: str | None = None
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
            "discovery_ref": self.discovery_ref,
            "score_evaluation_ref": self.score_evaluation_ref,
            "first_evaluation_order": self.first_evaluation_order,
        }

    @property
    def source_ref(self) -> str | None:
        """Read-compatible alias for pre-v1.1 archive consumers."""
        return self.discovery_ref


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
        discovery_ref = (
            row.get("discovery_ref")
            or row.get("source_ref")  # legacy input compatibility only
            or row.get("evaluation_ref")
            or f"evaluation:{row['evaluation_id']}"
        )
        score_evaluation_ref = (
            row.get("score_evaluation_ref")
            or row.get("evaluation_ref")
            or f"evaluation:{row['evaluation_id']}"
        )
        entry = ArchiveEntry(code=code, code_sha256=code_hash, objective=float(objective), evaluation_id=row["evaluation_id"],
                             problem_spec_hash=problem_spec_hash, data_manifest_hash=data_manifest_hash,
                             evaluator_hash=evaluator_hash, metric_spec_hash=metric_spec_hash,
                             origin=origin, candidate_id=row["candidate_id"], revision=revision,
                             algorithm=str(row.get("algorithm") or ""),
                             algorithm_text_sha256=str(row.get("algorithm_text_sha256") or ""),
                             discovery_ref=str(discovery_ref), score_evaluation_ref=str(score_evaluation_ref),
                             first_evaluation_order=order)
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
                    "discovery_ref": current.discovery_ref,
                    "first_evaluation_order": current.first_evaluation_order,
                }
            )
    return sorted(found.values(), key=lambda item: (item.objective, item.first_evaluation_order))


def build_archive_from_session(run_path: str | Path, *, run_id: str | None = None) -> dict[str, Any]:
    """Build a training archive from hash-verified Session evidence.

    This is intentionally a read-only projection.  It never evaluates code,
    reads Memory, contacts a provider, or accepts a hand-written candidate
    list.  The only inputs are completed ``evaluation_facts.json`` files whose
    references and hashes are stored in the Session SQLite state.
    """
    from agent_skill_loop import session_runtime as db

    root = Path(run_path).resolve()
    database = root / "session.sqlite3"
    if not database.is_file():
        raise ValueError("session_run_not_found")
    con = db._connect(database)
    try:
        db._require_schema(con, action="benchmark-archive")
        run = db._require_run(con, action="benchmark-archive", run_id=run_id)
        if not run["benchmark_id"]:
            raise ValueError("archive_requires_benchmark_session")
        # ``state`` is the read-only identity check.  It validates the frozen
        # config and suite without requiring the current checkout's Runtime or
        # Skill hash to match the historical Session.
        _config, suite = db._verify_files(root, run, action="state")
        round_rows = con.execute(
            "SELECT * FROM rounds WHERE run_id=? AND evaluation_facts_ref IS NOT NULL ORDER BY round_id",
            (run["run_id"],),
        ).fetchall()
        if not round_rows:
            raise ValueError("archive_evidence_missing")

        candidates: list[dict[str, Any]] = []
        source_facts: list[dict[str, Any]] = []
        expected_benchmark = {
            "benchmark_id": run["benchmark_id"],
            "profile": run["benchmark_profile"],
            "problem_spec_hash": run["problem_spec_hash"],
            "benchmark_spec_hash": run["benchmark_spec_hash"],
            "data_manifest_hash": run["data_manifest_hash"],
            "reference_manifest_hash": run["reference_manifest_hash"],
            "metric_spec_hash": run["metric_spec_hash"],
        }
        for round_row in round_rows:
            ref = round_row["evaluation_facts_ref"]
            if not isinstance(ref, str) or not ref:
                raise ValueError("archive_evidence_reference_invalid")
            facts_path = (root / ref).resolve()
            if not facts_path.is_relative_to(root) or not facts_path.is_file():
                raise ValueError("archive_evidence_reference_invalid")
            facts_text = facts_path.read_text(encoding="utf-8")
            if db._sha256(facts_text) != round_row["evaluation_facts_sha256"]:
                raise ValueError("archive_evidence_hash_mismatch")
            try:
                facts = json.loads(facts_text)
            except (TypeError, json.JSONDecodeError) as exc:
                raise ValueError("archive_evidence_invalid") from exc
            if not isinstance(facts, Mapping) or facts.get("round_id") != round_row["round_id"]:
                raise ValueError("archive_evidence_identity_mismatch")
            if any(facts.get(name) != run[name] for name in ("problem", "suite_hash", "evaluator_hash")):
                raise ValueError("archive_evidence_identity_mismatch")
            benchmark_facts = facts.get("benchmark")
            if not isinstance(benchmark_facts, Mapping) or any(
                benchmark_facts.get(name) != value for name, value in expected_benchmark.items()
            ):
                raise ValueError("archive_evidence_benchmark_identity_mismatch")
            fact_candidates = facts.get("candidates")
            if not isinstance(fact_candidates, list):
                raise ValueError("archive_evidence_candidates_invalid")
            source_facts.append({
                "round_id": round_row["round_id"],
                "ref": ref,
                "sha256": round_row["evaluation_facts_sha256"],
                "candidate_count": len(fact_candidates),
            })
            for index, candidate in enumerate(fact_candidates):
                if not isinstance(candidate, Mapping):
                    raise ValueError("archive_candidate_invalid")
                row = dict(candidate)
                # Collected facts carry the common evaluation identity at
                # document level. Bind it after verifying the document hash;
                # reject conflicting per-candidate declarations.
                for name in ("problem_spec_hash", "data_manifest_hash", "evaluator_hash", "metric_spec_hash"):
                    if name in row and row[name] != run[name]:
                        raise ValueError("archive_candidate_identity_mismatch")
                    row[name] = run[name]
                candidate_ref = f"{ref}#candidates/{index}"
                row["discovery_ref"] = row.get("discovery_ref") or candidate_ref
                row["score_evaluation_ref"] = row.get("score_evaluation_ref") or (
                    f"evaluation:{row.get('evaluation_id')}"
                    if row.get("evaluation_id") else None
                )
                candidates.append(row)

        entries = build_archive(
            candidates,
            problem_spec_hash=str(run["problem_spec_hash"]),
            data_manifest_hash=str(run["data_manifest_hash"]),
            evaluator_hash=str(run["evaluator_hash"]),
            metric_spec_hash=str(run["metric_spec_hash"]),
        )
        payload: dict[str, Any] = {
            "schema_version": "algorithm-optimization-archive/v1",
            "run_id": run["run_id"],
            "problem": run["problem"],
            "suite_hash": suite["content_hash"],
            "evaluator_hash": run["evaluator_hash"],
            "benchmark": expected_benchmark,
            "source_facts": source_facts,
            "entries": [entry.as_dict() for entry in entries],
            "entry_count": len(entries),
            "status": "complete",
        }
        payload["archive_sha256"] = sha256_json(payload)
        return payload
    finally:
        con.close()


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
                    discovery_ref=str(item.get("discovery_ref") or item.get("source_ref")) if (item.get("discovery_ref") is not None or item.get("source_ref") is not None) else None,
                    score_evaluation_ref=str(item.get("score_evaluation_ref") or f"evaluation:{item['evaluation_id']}"),
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
            or not entry.discovery_ref
            or not entry.score_evaluation_ref
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
