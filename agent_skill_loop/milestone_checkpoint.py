"""Authoritative SQLite settled-prefix checkpoint ledger for M3.2 scaling runs."""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Mapping, Sequence

from .interface_design.model_routing import compute_attempt_cost_usd, ensure_routing_table


def _utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _connect(ledger_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(ledger_path), timeout=30.0, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=FULL")
    con.execute("PRAGMA busy_timeout=5000")
    return con


def ensure_milestone_tables(con: sqlite3.Connection) -> None:
    """Create authoritative M3.2 checkpoint & candidate provenance tables inside SQLite."""
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS milestone_checkpoints (
            run_id TEXT NOT NULL,
            ckpt_budget INTEGER NOT NULL,
            state TEXT NOT NULL CHECK (state IN ('scheduled','draining','sealed','unreached')),
            draining_started_ordinal INTEGER,
            settled_through_ordinal INTEGER,
            winner_source_ordinal INTEGER,
            winner_solver_sha256 TEXT,
            canonical_payload_json TEXT,
            payload_sha256 TEXT,
            policy_sha256 TEXT,
            created_at_utc TEXT NOT NULL,
            updated_at_utc TEXT NOT NULL,
            PRIMARY KEY (run_id, ckpt_budget)
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS candidate_provenance (
            attempt_token TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            logical_call_id TEXT,
            physical_request_id TEXT,
            global_ordinal INTEGER NOT NULL,
            purpose TEXT NOT NULL,
            generation_status TEXT NOT NULL CHECK (
                generation_status IN (
                    'pending','valid_candidate','invalid_candidate','malformed_response',
                    'eoh_skipped','probe','provider_failed','interrupted_unknown','baseline_seed'
                )
            ),
            eval_id TEXT,
            code_sha256 TEXT,
            bundle_hash TEXT,
            solver_manifest_json TEXT,
            validation_passed INTEGER,
            dev_all_feasible INTEGER,
            dev_completion_rate REAL,
            dev_penalized_mean REAL,
            dev_valid_mean REAL,
            dev_suite_hash TEXT,
            solve_budget_ms REAL,
            eligible INTEGER NOT NULL DEFAULT 0 CHECK (eligible IN (0,1)),
            settled_at_utc TEXT
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS run_wall_clock (
            run_id TEXT PRIMARY KEY,
            wall_offset_seconds REAL NOT NULL DEFAULT 0.0,
            updated_at_utc TEXT NOT NULL
        )
        """
    )
    ensure_routing_table(con)


def get_run_wall_offset_seconds(ledger_path: Path, run_id: str) -> float:
    con = _connect(ledger_path)
    try:
        ensure_milestone_tables(con)
        row = con.execute(
            "SELECT wall_offset_seconds FROM run_wall_clock WHERE run_id=?",
            (run_id,),
        ).fetchone()
        return float(row["wall_offset_seconds"]) if row is not None and row["wall_offset_seconds"] is not None else 0.0
    finally:
        con.close()


def set_run_wall_offset_seconds(ledger_path: Path, run_id: str, wall_seconds: float) -> float:
    now = _utc_now()
    target = max(0.0, float(wall_seconds))
    con = _connect(ledger_path)
    try:
        con.execute("BEGIN IMMEDIATE")
        ensure_milestone_tables(con)
        row = con.execute(
            "SELECT wall_offset_seconds FROM run_wall_clock WHERE run_id=?",
            (run_id,),
        ).fetchone()
        prev = float(row["wall_offset_seconds"]) if row is not None and row["wall_offset_seconds"] is not None else 0.0
        merged = max(prev, target)
        con.execute(
            """
            INSERT INTO run_wall_clock(run_id, wall_offset_seconds, updated_at_utc)
            VALUES (?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                wall_offset_seconds=MAX(run_wall_clock.wall_offset_seconds, excluded.wall_offset_seconds),
                updated_at_utc=excluded.updated_at_utc
            """,
            (run_id, merged, now),
        )
        con.execute("COMMIT")
        return merged
    except Exception:
        try:
            con.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise
    finally:
        con.close()


def _atomic_write_once_or_verify(path: Path, text: str, expected_sha256: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        actual_sha = _sha256_text(path.read_text(encoding="utf-8"))
        if actual_sha != expected_sha256:
            raise ValueError(f"checkpoint_export_sha256_mismatch:{path.name}:{actual_sha}!={expected_sha256}")
        return
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with tmp.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


def initialize_milestone_schedule(
    ledger_path: Path,
    *,
    run_id: str,
    checkpoint_budgets: Sequence[int],
    baseline_solver: Mapping[str, Any],
    baseline_dev_eval: Mapping[str, Any],
    dev_suite_hash: str,
    solve_budget_ms: float,
    policy_meta: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist milestone checkpoint schedule and verified ordinal-0 baseline champion."""
    ledger_path = Path(ledger_path)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoints = sorted({int(x) for x in checkpoint_budgets if int(x) > 0})
    policy_sha = _sha256_text(_canonical_json(dict(policy_meta or {})))
    baseline_json = _canonical_json(dict(baseline_solver))
    baseline_sha = _sha256_text(baseline_json)
    penalized = baseline_dev_eval.get("penalized_mean_tour_length", baseline_dev_eval.get("penalized_mean_objective"))
    if penalized is None:
        penalized = baseline_dev_eval.get("mean_tour_length", baseline_dev_eval.get("mean_objective"))
    valid_mean = baseline_dev_eval.get("valid_only_mean_tour_length", baseline_dev_eval.get("valid_only_mean_objective"))
    all_feas = bool(baseline_dev_eval.get("all_feasible", False))
    comp_rate = float(baseline_dev_eval.get("completion_rate") or 0.0)
    eligible = int(penalized is not None and comp_rate > 0.0)
    now = _utc_now()

    con = _connect(ledger_path)
    try:
        con.execute("BEGIN IMMEDIATE")
        ensure_milestone_tables(con)
        for ckpt in checkpoints:
            existing = con.execute(
                "SELECT policy_sha256 FROM milestone_checkpoints WHERE run_id=? AND ckpt_budget=?",
                (run_id, ckpt),
            ).fetchone()
            if existing is not None:
                if existing["policy_sha256"] and existing["policy_sha256"] != policy_sha:
                    raise ValueError(f"milestone_policy_sha256_mismatch:{ckpt}")
                continue
            con.execute(
                """
                INSERT INTO milestone_checkpoints(
                    run_id, ckpt_budget, state, policy_sha256, created_at_utc, updated_at_utc
                ) VALUES (?, ?, 'scheduled', ?, ?, ?)
                """,
                (run_id, ckpt, policy_sha, now, now),
            )
        con.execute(
            """
            INSERT OR IGNORE INTO candidate_provenance(
                attempt_token, run_id, logical_call_id, physical_request_id, global_ordinal,
                purpose, generation_status, code_sha256, bundle_hash, solver_manifest_json,
                validation_passed, dev_all_feasible, dev_completion_rate, dev_penalized_mean,
                dev_valid_mean, dev_suite_hash, solve_budget_ms, eligible, settled_at_utc
            ) VALUES (?, ?, 'baseline_0', 'baseline_0', 0, 'baseline', 'baseline_seed',
                      ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"{run_id}:baseline:0",
                run_id,
                str(baseline_solver.get("hook_code_sha256") or baseline_sha),
                baseline_solver.get("bundle_hash"),
                baseline_json,
                int(all_feas),
                comp_rate,
                float(penalized) if penalized is not None else None,
                float(valid_mean) if valid_mean is not None else None,
                dev_suite_hash,
                float(solve_budget_ms),
                eligible,
                now,
            ),
        )
        con.execute("COMMIT")
        return {"run_id": run_id, "checkpoints": checkpoints, "policy_sha256": policy_sha}
    except Exception:
        try:
            con.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise
    finally:
        con.close()


def register_attempt_provenance(
    ledger_path: Path,
    *,
    attempt_token: str,
    run_id: str,
    logical_call_id: str | None,
    physical_request_id: str,
    global_ordinal: int,
    purpose: str,
    generation_status: str = "pending",
) -> None:
    con = _connect(ledger_path)
    try:
        con.execute("BEGIN IMMEDIATE")
        ensure_milestone_tables(con)
        settled_at = _utc_now() if generation_status != "pending" else None
        con.execute(
            """
            INSERT OR IGNORE INTO candidate_provenance(
                attempt_token, run_id, logical_call_id, physical_request_id,
                global_ordinal, purpose, generation_status, eligible, settled_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)
            """,
            (attempt_token, run_id, logical_call_id, physical_request_id, int(global_ordinal), purpose, generation_status, settled_at),
        )
        con.execute("COMMIT")
    except Exception:
        try:
            con.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise
    finally:
        con.close()


def claim_latest_pending_attempt_token(
    ledger_path: Path,
    run_id: str,
    *,
    eval_id: str,
) -> str | None:
    """Atomically claim the latest completed pending attempt token across spawned workers."""
    con = _connect(ledger_path)
    try:
        con.execute("BEGIN IMMEDIATE")
        ensure_milestone_tables(con)
        row = con.execute(
            """
            SELECT p.attempt_token
            FROM candidate_provenance p
            JOIN budget_requests r ON r.request_id = p.physical_request_id
            WHERE p.run_id=?
              AND p.generation_status='pending'
              AND p.purpose IN ('eoh_generation', 'eoh_repair')
              AND r.state='complete'
              AND p.eval_id IS NULL
            ORDER BY p.global_ordinal DESC
            LIMIT 1
            """,
            (run_id,),
        ).fetchone()
        if row is None:
            con.execute("ROLLBACK")
            return None
        tok = str(row["attempt_token"])
        cur = con.execute(
            """
            UPDATE candidate_provenance
            SET eval_id=?
            WHERE attempt_token=? AND generation_status='pending' AND eval_id IS NULL
            """,
            (eval_id, tok),
        )
        con.execute("COMMIT")
        return tok if cur.rowcount == 1 else None
    except Exception:
        try:
            con.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise
    finally:
        con.close()


def settle_attempt_provenance(
    ledger_path: Path,
    *,
    attempt_token: str,
    generation_status: str,
    eval_id: str | None = None,
    code_sha256: str | None = None,
    bundle_hash: str | None = None,
    solver_manifest: Mapping[str, Any] | None = None,
    validation_passed: bool | None = None,
    dev_eval: Mapping[str, Any] | None = None,
    dev_suite_hash: str | None = None,
    solve_budget_ms: float | None = None,
    only_if_pending: bool = False,
) -> None:
    now = _utc_now()
    manifest_json = _canonical_json(dict(solver_manifest)) if solver_manifest is not None else None
    all_feas = bool(dev_eval.get("all_feasible", False)) if isinstance(dev_eval, Mapping) else None
    comp_rate = float(dev_eval.get("completion_rate") or 0.0) if isinstance(dev_eval, Mapping) else None
    pen_mean = (
        dev_eval.get("penalized_mean_tour_length", dev_eval.get("penalized_mean_objective"))
        if isinstance(dev_eval, Mapping)
        else None
    )
    if pen_mean is None and isinstance(dev_eval, Mapping):
        pen_mean = dev_eval.get("mean_tour_length", dev_eval.get("mean_objective"))
    val_mean = (
        dev_eval.get("valid_only_mean_tour_length", dev_eval.get("valid_only_mean_objective"))
        if isinstance(dev_eval, Mapping)
        else None
    )
    eligible = int(
        generation_status == "valid_candidate"
        and validation_passed is True
        and manifest_json is not None
        and pen_mean is not None
        and (comp_rate or 0.0) > 0.0
    )
    con = _connect(ledger_path)
    try:
        con.execute("BEGIN IMMEDIATE")
        ensure_milestone_tables(con)
        where_clause = "WHERE attempt_token=? AND generation_status='pending'"
        if only_if_pending and generation_status == "eoh_skipped":
            where_clause = "WHERE attempt_token=? AND generation_status='pending' AND eval_id IS NULL"
        con.execute(
            f"""
            UPDATE candidate_provenance
            SET generation_status=?,
                eval_id=COALESCE(?, eval_id),
                code_sha256=COALESCE(?, code_sha256),
                bundle_hash=COALESCE(?, bundle_hash),
                solver_manifest_json=COALESCE(?, solver_manifest_json),
                validation_passed=COALESCE(?, validation_passed),
                dev_all_feasible=COALESCE(?, dev_all_feasible),
                dev_completion_rate=COALESCE(?, dev_completion_rate),
                dev_penalized_mean=COALESCE(?, dev_penalized_mean),
                dev_valid_mean=COALESCE(?, dev_valid_mean),
                dev_suite_hash=COALESCE(?, dev_suite_hash),
                solve_budget_ms=COALESCE(?, solve_budget_ms),
                eligible=?,
                settled_at_utc=?
            {where_clause}
            """,
            (
                generation_status,
                eval_id,
                code_sha256,
                bundle_hash,
                manifest_json,
                int(validation_passed) if validation_passed is not None else None,
                int(all_feas) if all_feas is not None else None,
                comp_rate,
                float(pen_mean) if pen_mean is not None else None,
                float(val_mean) if val_mean is not None else None,
                dev_suite_hash,
                float(solve_budget_ms) if solve_budget_ms is not None else None,
                eligible,
                now,
                attempt_token,
            ),
        )
        con.execute("COMMIT")
    except Exception:
        try:
            con.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise
    finally:
        con.close()


def settle_pending_provenance_for_terminal_requests(
    ledger_path: Path, run_id: str, *, finished_eval_owner_epoch: str | None = None,
) -> int:
    """Close terminal requests and, for a joined evaluation owner, abandoned evaluations."""
    now = _utc_now()
    con = _connect(ledger_path)
    try:
        con.execute("BEGIN IMMEDIATE")
        ensure_milestone_tables(con)
        rows = con.execute(
            """
            SELECT p.attempt_token, p.eval_id, r.state, r.purpose
            FROM candidate_provenance p
            JOIN budget_requests r ON r.request_id = p.physical_request_id
            WHERE p.run_id=? AND p.generation_status='pending'
              AND (p.eval_id IS NULL OR r.owner_epoch=?)
              AND r.state NOT IN ('reserved','sent')
            """,
            (run_id, finished_eval_owner_epoch),
        ).fetchall()
        updated = 0
        for row in rows:
            req_state = str(row["state"])
            if str(row["purpose"]) == "eoh_probe":
                status = "probe"
            elif req_state == "unknown":
                status = "interrupted_unknown"
            elif req_state in {"failed", "http_error", "connectivity_failed", "killed_unknown"}:
                status = "provider_failed"
            elif row["eval_id"] is not None:
                status = "invalid_candidate"
            else:
                status = "eoh_skipped"
            con.execute(
                "UPDATE candidate_provenance SET generation_status=?, eligible=0, settled_at_utc=? WHERE attempt_token=? AND generation_status='pending'",
                (status, now, row["attempt_token"]),
            )
            updated += 1
        con.execute("COMMIT")
        return updated
    except Exception:
        try:
            con.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise
    finally:
        con.close()


def _champion_sort_key(row: sqlite3.Row) -> tuple[int, float, float, int, str]:
    solver = json.loads(row["solver_manifest_json"])
    solver_digest = _sha256_text(_canonical_json(solver))
    return (
        -int(bool(row["dev_all_feasible"])),
        -float(row["dev_completion_rate"] or 0.0),
        float(row["dev_penalized_mean"]),
        int(row["global_ordinal"]),
        solver_digest,
    )


def _checkpoint_usage_snapshot(con: sqlite3.Connection, run_id: str, through_ordinal: int) -> dict[str, Any]:
    rows = con.execute(
        "SELECT * FROM budget_requests WHERE run_id=? AND idx <= ? ORDER BY idx ASC",
        (run_id, through_ordinal),
    ).fetchall()
    by_state: dict[str, int] = {}
    in_tok = 0
    out_tok = 0
    cached_tok = 0
    has_in = False
    has_out = False
    has_cached = False
    provider_elapsed = 0.0
    priced_usd = 0.0
    priced_count = 0
    unpriced_count = 0
    requested_models: dict[str, int] = {}
    served_models: dict[str, int] = {}
    for row in rows:
        st = str(row["state"])
        by_state[st] = by_state.get(st, 0) + 1
        if row["elapsed_seconds"] is not None:
            provider_elapsed += float(row["elapsed_seconds"])
        req_m = row["requested_model"] if "requested_model" in row.keys() and row["requested_model"] else row["model"]
        if req_m:
            requested_models[str(req_m)] = requested_models.get(str(req_m), 0) + 1
        srv_m = row["served_model"] if "served_model" in row.keys() else None
        if srv_m:
            served_models[str(srv_m)] = served_models.get(str(srv_m), 0) + 1
        if row["input_tokens"] is not None:
            in_tok += int(row["input_tokens"])
            has_in = True
        if row["output_tokens"] is not None:
            out_tok += int(row["output_tokens"])
            has_out = True
        if "cached_tokens" in row.keys() and row["cached_tokens"] is not None:
            cached_tok += int(row["cached_tokens"])
            has_cached = True
        est_usd = row["estimated_cost_usd"] if "estimated_cost_usd" in row.keys() else None
        if est_usd is not None:
            priced_usd += float(est_usd)
            priced_count += 1
        else:
            unpriced_count += 1
    prov_rows = con.execute(
        "SELECT generation_status, COUNT(*) AS n FROM candidate_provenance WHERE run_id=? AND global_ordinal <= ? GROUP BY generation_status",
        (run_id, through_ordinal),
    ).fetchall()
    return {
        "attempted_requests": len(rows),
        "by_state": by_state,
        "input_tokens": in_tok if has_in else None,
        "output_tokens": out_tok if has_out else None,
        "cached_tokens": cached_tok if has_cached else None,
        "provider_elapsed_seconds": round(provider_elapsed, 4),
        "priced_cost_usd": round(priced_usd, 8) if priced_count else None,
        "priced_attempts": priced_count,
        "unpriced_attempts": unpriced_count,
        "requested_models": requested_models,
        "served_models": served_models,
        "provenance_counts": {str(r["generation_status"]): int(r["n"]) for r in prov_rows},
    }


def try_seal_draining_checkpoints(
    ledger_path: Path,
    run_id: str,
    *,
    wall_elapsed_seconds: float | None = None,
) -> list[int]:
    """Seal any draining (or newly reached scheduled) checkpoints whose prefix <= B is 100% settled."""
    now = _utc_now()
    newly_sealed: list[int] = []
    con = _connect(ledger_path)
    try:
        con.execute("BEGIN IMMEDIATE")
        ensure_milestone_tables(con)
        used_now = int(
            con.execute("SELECT COALESCE(MAX(idx), 0) FROM budget_requests WHERE run_id=?", (run_id,)).fetchone()[0]
        )
        rows = con.execute(
            "SELECT * FROM milestone_checkpoints WHERE run_id=? AND state IN ('draining','scheduled') ORDER BY ckpt_budget ASC",
            (run_id,),
        ).fetchall()
        for ckpt_row in rows:
            ckpt = int(ckpt_row["ckpt_budget"])
            if ckpt_row["state"] == "scheduled":
                if used_now < ckpt:
                    continue
                con.execute(
                    "UPDATE milestone_checkpoints SET state='draining', draining_started_ordinal=?, updated_at_utc=? WHERE run_id=? AND ckpt_budget=?",
                    (used_now, now, run_id, ckpt),
                )
            req_rows = con.execute(
                "SELECT request_id, idx, state, purpose, attempt_token FROM budget_requests WHERE run_id=? AND idx <= ? ORDER BY idx ASC",
                (run_id, ckpt),
            ).fetchall()
            if len(req_rows) < ckpt:
                continue
            if any(str(r["state"]) in {"reserved", "sent"} for r in req_rows):
                break
            pending_prov = con.execute(
                "SELECT COUNT(*) FROM candidate_provenance WHERE run_id=? AND global_ordinal <= ? AND generation_status='pending'",
                (run_id, ckpt),
            ).fetchone()[0]
            if int(pending_prov) > 0:
                break
            # Ensure every EoH generation/repair attempt <= ckpt either has provenance or was non-candidate
            missing_eoh = [
                r for r in req_rows
                if str(r["purpose"]) in {"eoh_generation", "eoh_repair"}
                and r["attempt_token"] is not None
                and con.execute(
                    "SELECT 1 FROM candidate_provenance WHERE attempt_token=?",
                    (r["attempt_token"],),
                ).fetchone() is None
            ]
            if missing_eoh:
                break

            eligible_rows = con.execute(
                """
                SELECT * FROM candidate_provenance
                WHERE run_id=? AND global_ordinal <= ? AND eligible=1 AND solver_manifest_json IS NOT NULL
                """,
                (run_id, ckpt),
            ).fetchall()
            if eligible_rows:
                winner = min(eligible_rows, key=_champion_sort_key)
                winner_solver = json.loads(winner["solver_manifest_json"])
                winner_ordinal = int(winner["global_ordinal"])
                winner_sha = _sha256_text(_canonical_json(winner_solver))
                winner_metrics = {
                    "all_feasible": bool(winner["dev_all_feasible"]),
                    "completion_rate": float(winner["dev_completion_rate"] or 0.0),
                    "penalized_mean_objective": float(winner["dev_penalized_mean"]) if winner["dev_penalized_mean"] is not None else None,
                    "valid_only_mean_objective": float(winner["dev_valid_mean"]) if winner["dev_valid_mean"] is not None else None,
                    "dev_suite_hash": winner["dev_suite_hash"],
                    "solve_budget_ms": winner["solve_budget_ms"],
                }
                eligibility_status = "eligible_champion"
            else:
                winner_solver = None
                winner_ordinal = None
                winner_sha = None
                winner_metrics = None
                eligibility_status = "no_eligible_solver"

            prior_walls: list[float] = []
            for prev_row in con.execute(
                "SELECT canonical_payload_json FROM milestone_checkpoints WHERE run_id=? AND ckpt_budget < ? AND state='sealed' AND canonical_payload_json IS NOT NULL",
                (run_id, ckpt),
            ).fetchall():
                try:
                    prev_wall = json.loads(str(prev_row["canonical_payload_json"])).get("wall_elapsed_seconds_at_seal")
                    if isinstance(prev_wall, (int, float)) and not isinstance(prev_wall, bool):
                        prior_walls.append(float(prev_wall))
                except (ValueError, TypeError):
                    pass
            effective_wall = wall_elapsed_seconds
            if effective_wall is not None and prior_walls:
                effective_wall = max(float(effective_wall), max(prior_walls))

            payload = {
                "schema_version": "m32-frozen-checkpoint/v1",
                "run_id": run_id,
                "checkpoint_budget": ckpt,
                "settled_through_ordinal": ckpt,
                "eligibility_status": eligibility_status,
                "winner_source_ordinal": winner_ordinal,
                "winner_solver_sha256": winner_sha,
                "best_dev_objective": winner_metrics["penalized_mean_objective"] if winner_metrics else None,
                "dev_metrics": winner_metrics,
                "frozen_solver": winner_solver,
                "usage_cutoff": _checkpoint_usage_snapshot(con, run_id, ckpt),
                "wall_elapsed_seconds_at_seal": round(float(effective_wall), 4) if effective_wall is not None else None,
            }
            canonical_text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n"
            payload_sha = _sha256_text(canonical_text)
            con.execute(
                """
                UPDATE milestone_checkpoints
                SET state='sealed',
                    settled_through_ordinal=?,
                    winner_source_ordinal=?,
                    winner_solver_sha256=?,
                    canonical_payload_json=?,
                    payload_sha256=?,
                    updated_at_utc=?
                WHERE run_id=? AND ckpt_budget=? AND state IN ('draining','scheduled')
                """,
                (ckpt, winner_ordinal, winner_sha, canonical_text, payload_sha, now, run_id, ckpt),
            )
            newly_sealed.append(ckpt)
        con.execute("COMMIT")
        return newly_sealed
    except Exception:
        try:
            con.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise
    finally:
        con.close()


def export_sealed_checkpoints(ledger_path: Path, run_id: str, checkpoints_dir: Path) -> dict[str, str]:
    """Materialize or verify deterministic byte-identical ``frozen_checkpoint_{B}.json`` files."""
    con = _connect(ledger_path)
    try:
        ensure_milestone_tables(con)
        rows = con.execute(
            "SELECT ckpt_budget, canonical_payload_json, payload_sha256 FROM milestone_checkpoints WHERE run_id=? AND state='sealed' ORDER BY ckpt_budget ASC",
            (run_id,),
        ).fetchall()
    finally:
        con.close()
    exported: dict[str, str] = {}
    checkpoints_dir = Path(checkpoints_dir)
    for row in rows:
        ckpt = int(row["ckpt_budget"])
        text = str(row["canonical_payload_json"])
        expected_sha = str(row["payload_sha256"])
        if _sha256_text(text) != expected_sha:
            raise ValueError(f"milestone_checkpoint_db_sha256_mismatch:{ckpt}")
        out_file = checkpoints_dir / f"frozen_checkpoint_{ckpt}.json"
        _atomic_write_once_or_verify(out_file, text, expected_sha)
        exported[str(ckpt)] = str(out_file)
    return exported


def read_milestone_status(ledger_path: Path, run_id: str) -> dict[str, Any]:
    con = _connect(ledger_path)
    try:
        ensure_milestone_tables(con)
        ckpts = [dict(r) for r in con.execute(
            "SELECT ckpt_budget, state, draining_started_ordinal, settled_through_ordinal, winner_source_ordinal, winner_solver_sha256, payload_sha256 FROM milestone_checkpoints WHERE run_id=? ORDER BY ckpt_budget ASC",
            (run_id,),
        ).fetchall()]
        total_used = int(con.execute("SELECT COUNT(*) FROM budget_requests WHERE run_id=?", (run_id,)).fetchone()[0])
        usage_eventual = _checkpoint_usage_snapshot(con, run_id, max(total_used, 10**9))
        return {
            "run_id": run_id,
            "attempted_requests": total_used,
            "checkpoints": ckpts,
            "usage_eventual": usage_eventual,
        }
    finally:
        con.close()


def price_ledger_records_with_rate_card(
    ledger_path: Path,
    run_id: str,
    rate_card: Mapping[str, Mapping[str, float]] | None,
    rate_card_version: str | None = None,
) -> dict[str, Any]:
    """Compute/reconcile USD costs for all terminal attempts of ``run_id`` using ``rate_card``."""
    con = _connect(ledger_path)
    try:
        rows = con.execute("SELECT * FROM budget_requests WHERE run_id=? ORDER BY idx ASC", (run_id,)).fetchall()
    finally:
        con.close()
    total_usd = 0.0
    priced = 0
    unpriced = 0
    unpriced_reasons: dict[str, int] = {}
    for row in rows:
        alias = (row["requested_model"] if "requested_model" in row.keys() and row["requested_model"] else row["model"])
        cached = row["cached_tokens"] if "cached_tokens" in row.keys() else None
        usd, ok, reason = compute_attempt_cost_usd(
            model_alias=alias,
            input_tokens=row["input_tokens"],
            output_tokens=row["output_tokens"],
            cached_tokens=cached,
            rate_card=rate_card,
        )
        if ok and usd is not None:
            total_usd += usd
            priced += 1
        else:
            unpriced += 1
            key = reason or "unpriced"
            unpriced_reasons[key] = unpriced_reasons.get(key, 0) + 1
    return {
        "rate_card_version": rate_card_version,
        "priced_cost_usd": round(total_usd, 8) if priced else None,
        "priced_attempts": priced,
        "unpriced_attempts": unpriced,
        "unpriced_reasons": unpriced_reasons,
    }
