"""Read-only role audit and paired analysis for the M3.5 pure KB re-test."""

from __future__ import annotations

import ast
import json
import sqlite3
from collections.abc import Mapping, Sequence
from contextlib import closing
from pathlib import Path
from typing import Any

from agent_skill_loop.interface_design.blind_eval_m3 import holm_bonferroni_adjust
from agent_skill_loop.memory import MemoryAPI
from agent_skill_loop.memory.api import solution_execution_ast_sha256
from agent_skill_loop.session_memory import _verified_json
from agent_skill_loop.skill_store import load_skill
from research_agent.contracts import AgentConfig, sha256_file, sha256_text
from research_agent.tools.kb_tools import verify_pinned_release
from tools.run_m35_memory_ablation import _digest, _inside, _json, _paired_stats, _store_card_files, _store_digest

_PIN_FIELDS = ("kb_release_id", "kb_manifest_sha256")


def _kb_audit(run_dir: Path, config: AgentConfig) -> dict[str, Any]:
    if not (config.kb_enabled and config.kb_store_path and config.pinned_kb_release_id
            and config.pinned_kb_manifest_sha256):
        raise ValueError("m35v2_kb_pin_required")
    release = verify_pinned_release(
        Path(config.kb_store_path), release_id=config.pinned_kb_release_id,
        manifest_sha256=config.pinned_kb_manifest_sha256,
    )
    counts = {"kb_search": 0, "kb_read": 0}
    log = run_dir / "agent_artifacts" / "kb_events.jsonl"
    if log.is_file():
        for line in log.read_text(encoding="utf-8").splitlines():
            event = json.loads(line)
            if (not isinstance(event, dict) or event.get("op") not in counts or event.get("release_id") != release["release_id"]
                    or event.get("manifest_sha256") != release["manifest_sha256"]):
                raise ValueError("m35v2_kb_event_pin_mismatch")
            counts[event["op"]] += 1
    return {
        "kb_release_id": release["release_id"], "kb_manifest_sha256": release["manifest_sha256"],
        "kb_release_path": str(Path(release["release"]).resolve()),
        "kb_search_count": counts["kb_search"], "kb_read_count": counts["kb_read"],
    }


def _audit_publication(session: Path, write: sqlite3.Row, store: MemoryAPI) -> dict[str, Any]:
    if (write["operation_status"] != "SUCCEEDED" or write["action"] not in {"submit-evaluation", "memory-revise"}
            or not write["reference"] or write["error_code"] is not None):
        raise ValueError("m35v2_invalid_publication_receipt")
    result = json.loads(write["receipt_json"])["result"]
    result_memory = result.get("memory") or {}
    if (result_memory.get("status") != "published" or result_memory.get("reference") != write["reference"]
            or result_memory.get("error_code") is not None
            or result.get("proposal_ref") != write["proposal_ref"]
            or result.get("evaluation_facts_ref") != write["evaluation_facts_ref"]
            or result.get("evaluation_facts_sha256") != write["evaluation_facts_sha256"]):
        raise ValueError("m35v2_invalid_publication_receipt")
    proposal = _verified_json(session, write["proposal_ref"], result.get("proposal_sha256"))
    facts = _verified_json(session, write["evaluation_facts_ref"], write["evaluation_facts_sha256"])
    card = store.read_version(write["reference"])
    provenance = card["provenance"]
    evidence_ref = proposal.get("evidence_ref")
    expected = {
        "source_run_id": write["run_id"], "round_id": str(write["round_id"]),
        "source_session_root": str(session.parent / "session_run"),
        "evaluation_facts_ref": write["evaluation_facts_ref"],
        "evaluation_facts_sha256": write["evaluation_facts_sha256"], "evidence_ref": evidence_ref,
    }
    if (proposal.get("kind") != write["kind"] or card["type"] != write["kind"]
            or card["name"] != proposal.get("name") or card["project"] != proposal.get("project")
            or card["scene"] != proposal.get("scene") or card["integrity"] != "verified"
            or card["description"] != proposal.get("description") or card["format_version"] != 3
            or card.get("based_on") != proposal.get("memory_based_on")
            or card.get("code_anchor") != proposal.get("code_anchor")
            or card["body_sha256"] != sha256_text(proposal["body"].replace("\r\n", "\n").replace("\r", "\n").strip())
            or any(provenance.get(field) != value for field, value in expected.items())
            or evidence_ref not in facts["evidence_refs"]):
        raise ValueError("m35v2_publication_provenance_mismatch")
    metadata = _json(Path(card["path"]).with_suffix(".json"))
    operation_key = f"{write['run_id']}:{write['operation_id']}"
    if metadata.get("operation_key") != operation_key:
        raise ValueError("m35v2_publication_operation_mismatch")
    matches = [row for row in facts["candidates"] if f"evaluation:{row['evaluation_id']}" == evidence_ref]
    if len(matches) != 1:
        raise ValueError("m35v2_publication_candidate_missing")
    candidate = matches[0]
    anchor = card.get("code_anchor") or {}
    if (candidate.get("valid") is not True or candidate.get("origin") not in {"generated", "generated_repair"}
            or anchor.get("code_sha256") != candidate["code_sha256"]
            or sha256_text(candidate["code"]) != candidate["code_sha256"]
            or provenance.get("source_evaluation_id") != candidate["evaluation_id"]
            or provenance.get("candidate_code_sha256") != candidate["code_sha256"]
            or provenance.get("suite_hash") != facts["suite_hash"]
            or provenance.get("evaluator_hash") != facts["evaluator_hash"]):
        raise ValueError("m35v2_publication_candidate_mismatch")
    canonical = sha256_text(ast.unparse(ast.parse(candidate["code"])))
    if (anchor.get("canonical_ast_sha256") != canonical or provenance.get("canonical_ast_sha256") != canonical
            or result_memory.get("canonical_ast_sha256") != canonical):
        raise ValueError("m35v2_publication_ast_mismatch")
    parent_version_id = None
    exported_ref = facts.get("best_generated_ref")
    if exported_ref:
        exported = load_skill(_inside(session, exported_ref))
        if (exported.valid and exported.code_sha256 == candidate["code_sha256"]
                and exported.mean_objective == candidate["objective"]):
            parent_version_id = exported.parent_version_id
    if (provenance.get("parent_version_id") != parent_version_id
            or result_memory.get("parent_version_id") != parent_version_id):
        raise ValueError("m35v2_publication_parent_mismatch")
    if write["kind"] == "solution":
        parent_ref = (facts.get("incumbent_before") or {}).get("ref")
        if (parent_version_id is None or not parent_ref
                or load_skill(_inside(session, parent_ref)).version_id != parent_version_id
                or provenance.get("source_skill_ref") != exported_ref
                or solution_execution_ast_sha256(card["body"]) != canonical):
            raise ValueError("m35v2_solution_lineage_mismatch")
    return {
        "operation_id": write["operation_id"], "operation_key": operation_key,
        "round_id": write["round_id"], "kind": write["kind"], "reference": write["reference"],
        "evidence_ref": evidence_ref, "code_sha256": candidate["code_sha256"],
        "canonical_ast_sha256": canonical, "parent_version_id": parent_version_id,
    }


def _audit_session(
    session: Path, config: AgentConfig, kb: Mapping[str, Any], store: MemoryAPI | None,
) -> tuple[int, int, int, list[dict[str, Any]]]:
    ledger = session / "session.sqlite3"
    if ledger.resolve() != ledger or not ledger.is_file():
        raise ValueError("m35v2_missing_session_ledger")
    with closing(sqlite3.connect(f"{ledger.as_uri()}?mode=ro", uri=True)) as con:
        con.row_factory = sqlite3.Row
        con.execute("BEGIN")
        runs = con.execute("SELECT * FROM runs").fetchall()
        if len(runs) != 1:
            raise ValueError("m35v2_session_identity_mismatch")
        run = runs[0]
        config_path = session / "config_frozen.json"
        if sha256_file(config_path) != run["config_sha256"]:
            raise ValueError("m35v2_session_config_digest_mismatch")
        frozen = _json(config_path)
        if any(frozen.get(key) != kb[key] for key in (*_PIN_FIELDS, "kb_release_path")):
            raise ValueError("m35v2_session_kb_pin_mismatch")
        pb = frozen.get("persistent_budget") or {}
        frozen_memory = frozen.get("memory") or {}
        if (frozen.get("run_id") != run["run_id"] or pb.get("run_id") != config.run_id
                or frozen_memory.get("enabled") is not config.memory_enabled
                or frozen_memory.get("online_writeback_enabled") is not config.memory_online_writeback_enabled
                or frozen_memory.get("store") != config.memory_store_path
                or run["memory_enabled"] != int(config.memory_enabled)
                or run["memory_online_writeback_enabled"] != int(config.memory_online_writeback_enabled)
                or run["memory_store"] != config.memory_store_path):
            raise ValueError("m35v2_session_memory_policy_mismatch")
        for round_row in con.execute("SELECT context_manifest_ref FROM rounds WHERE context_manifest_ref IS NOT NULL"):
            context_path = _inside(session, round_row["context_manifest_ref"])
            selection = _json(context_path).get("interface_selection") or {}
            if any(selection.get(key) != kb[key] for key in _PIN_FIELDS):
                raise ValueError("m35v2_round_kb_pin_mismatch")
            summary_path = context_path.parent / "eoh_run" / "summary.json"
            if summary_path.is_file():
                summary = _json(summary_path)
                if any(summary.get(key) != kb[key] for key in _PIN_FIELDS):
                    raise ValueError("m35v2_execution_kb_pin_mismatch")
        search_count = con.execute("SELECT COUNT(*) FROM memory_searches").fetchone()[0]
        read_count = con.execute("SELECT COUNT(*) FROM memory_reads").fetchone()[0]
        write_count = con.execute("SELECT COUNT(*) FROM memory_writes").fetchone()[0]
        if not config.memory_enabled and (search_count or read_count):
            raise ValueError("m35v2_disabled_memory_access_rows")
        if not config.memory_online_writeback_enabled and write_count:
            raise ValueError("m35v2_read_only_memory_write_rows")
        if write_count and store is None:
            raise ValueError("m35v2_publication_store_missing")
        rows = con.execute(
            "SELECT w.*, o.status AS operation_status, o.action, o.receipt_json, "
            "r.evaluation_facts_ref, r.evaluation_facts_sha256 FROM memory_writes w "
            "LEFT JOIN operations o USING (operation_id, run_id, round_id) "
            "LEFT JOIN rounds r USING (run_id, round_id) ORDER BY w.write_id"
        ).fetchall()
        if any(row["status"] in {"proposed", "accepted"} for row in rows):
            raise ValueError("m35v2_unsettled_memory_write")
        publications = [_audit_publication(session, row, store) for row in rows if row["status"] == "published"]
    return search_count, read_count, write_count, publications


def _audit_store_receipts(
    store: Path, config: AgentConfig, initial_sha256: str, receipts: Sequence[Mapping[str, Any]],
) -> None:
    files = set(_store_card_files(store))
    if any(path.with_suffix(".md" if path.suffix == ".json" else ".json") not in files for path in files):
        raise ValueError("m35v2_unpaired_memory_version_files")
    online_operations = []
    initial_files = {}
    for path in sorted(files):
        if path.suffix != ".json":
            continue
        key = _json(path).get("operation_key")
        if config.memory_mode == "m35_full" and isinstance(key, str) and key.startswith("auto_dream:"):
            for source in (path, path.with_suffix(".md")):
                initial_files[source.relative_to(store).as_posix()] = sha256_file(source)
        else:
            online_operations.append(key)
    if _digest(initial_files) != initial_sha256:
        raise ValueError("m35v2_initial_memory_cards_changed")
    if (len(online_operations) != len(receipts)
            or set(online_operations) != {receipt["operation_key"] for receipt in receipts}):
        raise ValueError("m35v2_unreceipted_online_memory_version")


def audit_cell(config: AgentConfig, *, initial_store_sha256: str | None) -> dict[str, Any]:
    """Verify a terminal cell against the frozen role, including interrupted Sessions."""
    run_dir = Path(config.output_dir).resolve()
    recorded = AgentConfig.from_dict(_json(run_dir / "agent_config.json"))
    if recorded != config:
        raise ValueError("m35v2_agent_config_mismatch")
    kb = _kb_audit(run_dir, config)
    store = None
    final_digest = None
    store_path = None
    if config.memory_enabled:
        if config.memory_store_path is None or initial_store_sha256 is None:
            raise ValueError("m35v2_initial_memory_store_missing")
        if config.memory_mode == "m35_l12" and initial_store_sha256 != _digest({}):
            raise ValueError("m35v2_online_memory_must_start_empty")
        store_path = Path(config.memory_store_path)
        if store_path != run_dir / "memory":
            raise ValueError("m35v2_private_memory_store_required")
        if _json(run_dir / "initial_memory_receipt.json").get("sha256") != initial_store_sha256:
            raise ValueError("m35v2_initial_memory_receipt_mismatch")
        final_digest = _store_digest(store_path)
        if any(store_path.glob("*/*.publish")):
            raise ValueError("m35v2_unsettled_memory_store")
        if not config.memory_online_writeback_enabled and final_digest != initial_store_sha256:
            raise ValueError("m35v2_read_only_memory_digest_changed")
        if config.memory_online_writeback_enabled:
            store = MemoryAPI(store_path, read_only=True)
    elif (initial_store_sha256 is not None or config.memory_store_path is not None
          or (run_dir / "memory").exists() or (run_dir / "memory").is_symlink()):
        raise ValueError("m35v2_disabled_memory_store")

    searches = reads = writes = 0
    receipts = []
    sessions = [*sorted(run_dir.glob("session_run_interrupted_*")), run_dir / "session_run"]
    for session in sessions:
        search_count, read_count, write_count, publications = _audit_session(session, config, kb, store)
        searches += search_count
        reads += read_count
        writes += write_count
        receipts.extend(publications)

    if store is not None:
        # Each online card version must have a matching durable publication row.
        # Dream cards have distinct offline operation keys and were frozen beforehand.
        _audit_store_receipts(store_path, config, initial_store_sha256, receipts)
    qualifying = sum(row["kind"] in {"solution", "insight"} for row in receipts)
    return {
        **kb, "memory_search_count": searches, "memory_read_count": reads, "memory_write_row_count": writes,
        "publication_count": len(receipts), "writeback_receipts": receipts, "solution_or_insight_count": qualifying,
        "writeback_status": ("disabled" if not config.memory_online_writeback_enabled else
                             "writeback_observed" if qualifying else "writeback_not_observed"),
        "initial_store_sha256": initial_store_sha256, "final_store_sha256": final_digest,
    }


def suite_report(suite: Mapping[str, Any], *, seeds: Sequence[int], arms: Sequence[str],
                 contrasts: Sequence[tuple[str, str]]) -> dict[str, Any]:
    """Analyze each seed, fleet policy and denominator as a separate Holm family."""
    by_cell = suite["records"]
    if set(by_cell) != {f"{seed}:{arm}" for seed in seeds for arm in arms} or any(
        len(rows) != suite["instance_count"] for rows in by_cell.values()
    ):
        raise ValueError("m35v2_evaluation_roster_or_instance_count_mismatch")
    per_seed = {}
    for seed in seeds:
        fleets = {}
        for fleet in ("exact_k", "free_fleet"):
            denominators = {}
            for denominator in ("overall", "common_completed"):
                rows = [
                    {"arm": arm, "comparator": comparator, **_paired_stats(
                        by_cell[f"{seed}:{arm}"], by_cell[f"{seed}:{comparator}"], seed=seed,
                        exact_k=fleet == "exact_k", common_completed=denominator == "common_completed",
                    )}
                    for arm, comparator in contrasts
                ]
                adjusted = holm_bonferroni_adjust([
                    row["wilcoxon"]["p_two_sided"] if row["wilcoxon"] is not None else 1.0 for row in rows
                ])
                for row, p_value in zip(rows, adjusted, strict=True):
                    row["wilcoxon_p_holm"] = p_value if row["wilcoxon"] is not None else None
                denominators[denominator] = rows
            fleets[fleet] = denominators
        per_seed[str(seed)] = fleets
    return {key: suite[key] for key in ("split", "vehicle_limit_policy", "instance_count", "instance_set_sha256")} | {
        "per_seed": per_seed,
    }
