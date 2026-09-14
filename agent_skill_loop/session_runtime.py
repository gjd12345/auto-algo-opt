"""SQLite Session control plane and crash-recoverable audit projection."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from agent_skill_loop.contracts import (
    DEFAULT_COUNT,
    DEFAULT_SEED,
    DEFAULT_SIZE,
    DEFAULT_SOLVER_TIMEOUT,
    EOH_COMMIT,
    PROBLEM_CVRP,
)
from agent_skill_loop.evaluator import evaluator_source_hash
from agent_skill_loop.journal import digest, verify_audit_journal
from agent_skill_loop.contracts import AUDIT_JOURNAL_SCHEMA
from agent_skill_loop.session_contracts import SEARCH_POLICY_MINIMUMS, SEARCH_POLICY_KEYS
from agent_skill_loop.problems.base import get_problem


SCHEMA_VERSION = "algorithm-optimization-session/v1.1"
CONFIG_SCHEMA = "algorithm-optimization-session-config/v1.1"
RUNTIME_VERSION = "1.1.0"
OPTIMIZATION_SKILL_ID = "algorithm-optimization"
OPTIMIZATION_SKILL_VERSION = "v1.1"
MEMORY_POLICY_ID = "markdown-memory"
MEMORY_POLICY_VERSION = "v2"
DEFAULT_MEMORY_STORE_ENV = "ALGORITHM_OPTIMIZATION_MEMORY_STORE"
REPAIR_POLICY_VERSION = "bounded_v2"
SEARCH_POLICY_DEFAULTS = {"pop_size": 4, "n_pop": 2, "max_sample_nums": 8}
SEARCH_POLICY_LIMITS = {"pop_size": (2, 8), "n_pop": (1, 5), "max_sample_nums": (1, 16)}


def default_memory_store() -> Path:
    configured = os.environ.get(DEFAULT_MEMORY_STORE_ENV)
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / ".codex" / "algorithm-optimization" / "memory").resolve()

RUN_STATES = frozenset({"RUNNING", "STOPPING", "COMPLETED", "STOPPED", "FAILED"})
ROUND_STATES = frozenset({
    "WAITING_FOR_PLAN",
    "READY_TO_EXECUTE",
    "EXECUTING",
    "WAITING_FOR_EVALUATION",
    "READY_TO_FINISH",
    "ROUND_COMPLETED",
    "STOPPED",
    "FAILED",
})


class SessionError(RuntimeError):
    """A machine-readable session contract or storage failure."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        action: str,
        retryable: bool = False,
        run_id: str | None = None,
        round_id: int | None = None,
        state_version: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.action = action
        self.retryable = retryable
        self.run_id = run_id
        self.round_id = round_id
        self.state_version = state_version

    @property
    def exit_code(self) -> int:
        if self.code in {"OPERATION_ID_CONFLICT", "STATE_VERSION_CONFLICT", "RUN_ID_MISMATCH"}:
            return 2
        if self.code in {
            "ACTION_NOT_ALLOWED",
            "LIVE_TASK_EXISTS",
            "EFFECTFUL_TASK_ALREADY_EXISTS",
            "TASK_NOT_TERMINAL",
            "RUN_TERMINAL",
            "RUN_STOPPING",
        }:
            return 5
        if self.code.endswith("_FAILED") or self.code in {"SQLITE_ERROR", "SCHEMA_MISMATCH"}:
            return 10
        return 3


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha256(value: str | bytes) -> str:
    data = value.encode("utf-8") if isinstance(value, str) else value
    return hashlib.sha256(data).hexdigest()


def _normalize_explicit_seed_set(
    payload: Any,
    *,
    problem_spec_hash: str,
    suite_hash: str,
    evaluator_hash: str,
    data_manifest_hash: str | None,
    metric_spec_hash: str | None,
) -> dict[str, Any]:
    """Normalize a user seed set without trusting supplied fitness facts.

    Explicit seeds are code inputs, not evaluated candidates.  Scores,
    evaluation IDs, and lineage supplied by a caller are intentionally
    discarded; the Session task performs the complete re-evaluation.
    """
    if isinstance(payload, Mapping):
        members = payload.get("selected_members", payload.get("members"))
        for name, expected in (
            ("problem_spec_hash", problem_spec_hash),
            ("suite_hash", suite_hash),
            ("evaluator_hash", evaluator_hash),
            ("data_manifest_hash", data_manifest_hash),
            ("metric_spec_hash", metric_spec_hash),
        ):
            if name in payload and payload.get(name) != expected:
                raise ValueError(f"explicit_seed_{name}_mismatch")
    else:
        members = payload
    if not isinstance(members, Sequence) or isinstance(members, (str, bytes)) or not members:
        raise ValueError("explicit_seed_set_must_be_nonempty_list")
    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, item in enumerate(members):
        if not isinstance(item, Mapping) or not isinstance(item.get("code"), str) or not item["code"].strip():
            raise ValueError(f"explicit_seed_{index}_code_required")
        code = item["code"]
        code_hash = _sha256(code)
        if item.get("code_sha256") is not None and item.get("code_sha256") != code_hash:
            raise ValueError(f"explicit_seed_{index}_code_hash_mismatch")
        algorithm = str(item.get("algorithm") or f"Explicit seed {index + 1}")
        algorithm_hash = _sha256(algorithm)
        if item.get("algorithm_text_sha256") is not None and item.get("algorithm_text_sha256") != algorithm_hash:
            raise ValueError(f"explicit_seed_{index}_algorithm_hash_mismatch")
        if code_hash in seen:
            continue
        seen.add(code_hash)
        normalized.append({
            "algorithm": algorithm,
            "algorithm_text_sha256": algorithm_hash,
            "code": code,
            "code_sha256": code_hash,
        })
    if not normalized:
        raise ValueError("explicit_seed_set_has_no_unique_code")
    return {
        "schema_version": "algorithm-optimization-explicit-seed-set/v1",
        "problem_spec_hash": problem_spec_hash,
        "suite_hash": suite_hash,
        "data_manifest_hash": data_manifest_hash,
        "evaluator_hash": evaluator_hash,
        "metric_spec_hash": metric_spec_hash,
        "members": normalized,
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _runtime_source_hash() -> str:
    root = Path(__file__).resolve().parents[1]
    digest = hashlib.sha256()
    for package in ("agent_skill_loop", "eoh_frozen"):
        package_root = root / package
        for path in sorted(package_root.rglob("*.py")):
            digest.update(path.relative_to(root).as_posix().encode("utf-8"))
            digest.update(path.read_bytes())
    return digest.hexdigest()


def _skill_content_hash() -> str:
    """Hash actual shipped instructions identically in checkout and wheel.

    Missing resources are an installation error, never a descriptor-only
    substitute for the frozen Skill identity. Interpreter caches are not
    policy resources and must not change the hash after an import.
    """
    root = Path(__file__).resolve().parents[1]
    skill_root = root / "skills" / "algorithm-optimization"
    if not skill_root.is_dir():
        import algorithm_optimization_skill
        skill_root = Path(algorithm_optimization_skill.__file__).resolve().parent
    if not (skill_root / "SKILL.md").is_file():
        raise ValueError("optimization_skill_resources_missing")
    digest = hashlib.sha256()
    for path in sorted(p for p in skill_root.rglob("*") if p.is_file() and p.suffix in {".md", ".yaml"}):
        name = "skills/algorithm-optimization/" + path.relative_to(skill_root).as_posix()
        digest.update(name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _required_skill_content_hash(action: str) -> str:
    """Map a missing packaged Skill resource to the Session error contract."""
    try:
        return _skill_content_hash()
    except (ImportError, OSError, ValueError) as exc:
        if isinstance(exc, (ImportError, OSError)) or str(exc) == "optimization_skill_resources_missing":
            raise SessionError(
                "SKILL_RESOURCES_MISSING",
                "Algorithm Optimization Skill resources are missing",
                action=action,
            ) from exc
        raise


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            temporary.unlink()
        except OSError:
            pass
        raise


@contextmanager
def _transaction(connection: sqlite3.Connection) -> Iterator[None]:
    connection.execute("BEGIN IMMEDIATE")
    try:
        yield
    except Exception:
        connection.rollback()
        raise
    else:
        connection.commit()


def _connect(database: Path) -> sqlite3.Connection:
    try:
        connection = sqlite3.connect(str(database), timeout=5.0, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = FULL")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection
    except sqlite3.Error as exc:
        raise SessionError(
            "SQLITE_ERROR", str(exc), action="session", retryable=True
        ) from exc


def _create_schema(connection: sqlite3.Connection) -> None:
    # Do not use executescript here.  sqlite3.executescript implicitly commits
    # before executing its script, which would make init's seed rows non-atomic
    # with schema creation.  Each statement stays inside the caller's
    # BEGIN IMMEDIATE transaction.
    statements = [
        """
        CREATE TABLE IF NOT EXISTS schema_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )""",
        """
        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            output_root TEXT NOT NULL UNIQUE,
            state TEXT NOT NULL CHECK (state IN ('RUNNING','STOPPING','COMPLETED','STOPPED','FAILED')),
            state_version INTEGER NOT NULL CHECK (state_version >= 1),
            active_round_id INTEGER,
            problem TEXT NOT NULL,
            problem_spec_hash TEXT,
            benchmark_id TEXT,
            benchmark_profile TEXT,
            benchmark_spec_hash TEXT,
            data_manifest_hash TEXT,
            reference_manifest_hash TEXT,
            metric_spec_hash TEXT,
            inheritance_mode TEXT NOT NULL DEFAULT 'incumbent_only',
            feedback_mode TEXT NOT NULL DEFAULT 'runtime_facts',
            agent_guidance INTEGER NOT NULL DEFAULT 1 CHECK (agent_guidance IN (0,1)),
            experiment_manifest_sha256 TEXT,
            max_rounds INTEGER CHECK (max_rounds IS NULL OR max_rounds >= 1),
            round_budget INTEGER CHECK (round_budget IS NULL OR round_budget >= 1),
            suite_hash TEXT NOT NULL,
            evaluator_hash TEXT NOT NULL,
            objective_direction TEXT NOT NULL,
            baseline_code_sha256 TEXT NOT NULL,
            optimization_skill_id TEXT NOT NULL,
            optimization_skill_version TEXT NOT NULL,
            optimization_skill_sha256 TEXT NOT NULL,
            runtime_version TEXT NOT NULL,
            runtime_source_sha256 TEXT NOT NULL,
            memory_enabled INTEGER NOT NULL CHECK (memory_enabled IN (0,1)),
            memory_store TEXT,
            memory_policy_id TEXT,
            memory_policy_version TEXT,
            eoh_commit TEXT NOT NULL,
            eoh_model TEXT NOT NULL,
            eoh_endpoint TEXT NOT NULL,
            eoh_api_key_env TEXT NOT NULL,
            repair_mode TEXT NOT NULL CHECK (repair_mode IN ('off','bounded')),
            repair_policy_version TEXT,
            eoh_max_requests INTEGER CHECK (eoh_max_requests IS NULL OR eoh_max_requests >= 0),
            eoh_round_max_requests INTEGER CHECK (eoh_round_max_requests IS NULL OR eoh_round_max_requests >= 0),
            max_solver_calls INTEGER CHECK (max_solver_calls IS NULL OR max_solver_calls >= 0),
            repair_max_requests INTEGER CHECK (repair_max_requests IS NULL OR repair_max_requests >= 0),
            engine_wall_seconds REAL CHECK (engine_wall_seconds IS NULL OR engine_wall_seconds >= 0),
            round_wall_seconds REAL CHECK (round_wall_seconds IS NULL OR round_wall_seconds >= 0),
            solution_threshold REAL,
            solution_policy_id TEXT,
            created_at_utc TEXT NOT NULL,
            finished_at_utc TEXT,
            config_ref TEXT NOT NULL,
            config_sha256 TEXT NOT NULL,
            init_operation_id TEXT NOT NULL UNIQUE,
            search_policy_defaults_json TEXT,
            search_policy_limits_json TEXT
        )""",
        """
        CREATE TABLE IF NOT EXISTS rounds (
            run_id TEXT NOT NULL,
            round_id INTEGER NOT NULL CHECK (round_id >= 1),
            state TEXT NOT NULL CHECK (state IN (
                'WAITING_FOR_PLAN','READY_TO_EXECUTE','EXECUTING',
                'WAITING_FOR_EVALUATION','READY_TO_FINISH','ROUND_COMPLETED',
                'STOPPED','FAILED'
            )),
            updated_state_version INTEGER NOT NULL,
            previous_round_id INTEGER,
            feedback_ref TEXT,
            incumbent_before_ref TEXT,
            incumbent_before_objective REAL,
            incumbent_after_ref TEXT,
            incumbent_after_objective REAL,
            submitted_plan_ref TEXT,
            submitted_plan_sha256 TEXT,
            normalized_plan_ref TEXT,
            normalized_plan_sha256 TEXT,
            round_context_ref TEXT,
            round_context_sha256 TEXT,
            context_manifest_ref TEXT,
            population_snapshot_ref TEXT,
            population_snapshot_sha256 TEXT,
            seed_selection_ref TEXT,
            seed_selection_sha256 TEXT,
            evaluation_facts_ref TEXT,
            evaluation_facts_sha256 TEXT,
            submitted_evaluation_ref TEXT,
            submitted_evaluation_sha256 TEXT,
            memory_proposal_ref TEXT,
            memory_commit_status TEXT,
            task_id TEXT,
            decision TEXT CHECK (decision IS NULL OR decision IN ('continue','complete')),
            stop_reason TEXT,
            created_at_utc TEXT NOT NULL,
            finished_at_utc TEXT,
            PRIMARY KEY (run_id, round_id),
            FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
        )""",
        """
        CREATE TABLE IF NOT EXISTS operations (
            operation_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            round_id INTEGER,
            action TEXT NOT NULL,
            input_sha256 TEXT NOT NULL,
            expected_state_version INTEGER,
            result_state_version INTEGER,
            status TEXT NOT NULL CHECK (status IN ('PENDING','SUCCEEDED','FAILED')),
            receipt_json TEXT,
            error_code TEXT,
            created_at_utc TEXT NOT NULL,
            finished_at_utc TEXT,
            FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE,
            FOREIGN KEY (run_id, round_id) REFERENCES rounds(run_id, round_id)
        )""",
        """
        CREATE TABLE IF NOT EXISTS tasks (
            task_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            round_id INTEGER NOT NULL,
            state TEXT NOT NULL CHECK (state IN ('CREATED','STARTING','RUNNING','STOP_REQUESTED','EXITED','COLLECTED')),
            external_effect_started INTEGER NOT NULL DEFAULT 0 CHECK (external_effect_started IN (0,1)),
            terminal_reason TEXT,
            terminal_ref TEXT,
            terminal_sha256 TEXT,
            process_id INTEGER,
            heartbeat_at_utc TEXT,
            engine_elapsed_seconds REAL NOT NULL DEFAULT 0,
            hard_deadline_utc TEXT,
            created_at_utc TEXT NOT NULL,
            started_at_utc TEXT,
            finished_at_utc TEXT,
            FOREIGN KEY (run_id, round_id) REFERENCES rounds(run_id, round_id)
        )""",
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_live_task
        ON tasks(run_id, round_id)
        WHERE state IN ('CREATED','STARTING','RUNNING','STOP_REQUESTED')""",
        """CREATE UNIQUE INDEX IF NOT EXISTS uq_effectful_task
        ON tasks(run_id, round_id) WHERE external_effect_started=1""",
        """
        CREATE TABLE IF NOT EXISTS requests (
            request_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            round_id INTEGER,
            task_id TEXT,
            sequence INTEGER NOT NULL,
            purpose TEXT NOT NULL CHECK (purpose IN ('eoh_probe','eoh_generation','eoh_repair')),
            model TEXT,
            state TEXT NOT NULL CHECK (state IN ('reserved','sent','complete','failed','unknown')),
            status INTEGER,
            input_tokens INTEGER,
            output_tokens INTEGER,
            elapsed_seconds REAL,
            error_code TEXT,
            finish_reason TEXT,
            created_at_utc TEXT NOT NULL,
            finished_at_utc TEXT,
            UNIQUE(run_id, sequence),
            FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
        )""",
        """
        CREATE TABLE IF NOT EXISTS solver_calls (
            solver_call_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            round_id INTEGER NOT NULL,
            task_id TEXT,
            candidate_id TEXT,
            revision TEXT,
            origin TEXT,
            evaluation_id TEXT NOT NULL UNIQUE,
            suite_hash TEXT NOT NULL,
            evaluator_hash TEXT NOT NULL,
            metric_spec_hash TEXT,
            code_sha256 TEXT NOT NULL,
            state TEXT NOT NULL CHECK (state IN ('reserved','started','complete','failed','interrupted','unknown')),
            objective REAL,
            valid INTEGER,
            error_code TEXT,
            started_at_utc TEXT,
            finished_at_utc TEXT,
            UNIQUE(run_id, evaluation_id),
            FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
        )""",
        """
        CREATE TABLE IF NOT EXISTS task_processes (
            task_id TEXT PRIMARY KEY REFERENCES tasks(task_id),
            process_id INTEGER NOT NULL,
            started_at_utc TEXT NOT NULL
        )""",
        """
        CREATE TABLE IF NOT EXISTS memory_reads (
            read_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            round_id INTEGER NOT NULL,
            reference TEXT NOT NULL,
            body_sha256 TEXT NOT NULL,
            offset_chars INTEGER NOT NULL,
            returned_chars INTEGER NOT NULL,
            total_chars INTEGER NOT NULL,
            read_at_utc TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
        )""",
        """
        CREATE TABLE IF NOT EXISTS memory_writes (
            write_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            round_id INTEGER NOT NULL,
            operation_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            proposal_ref TEXT,
            status TEXT NOT NULL CHECK (status IN ('proposed','accepted','rejected','published','failed')),
            error_code TEXT,
            reference TEXT,
            created_at_utc TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
        )""",
        """
        CREATE TABLE IF NOT EXISTS audit_events (
            event_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            sequence INTEGER NOT NULL,
            state_version INTEGER NOT NULL,
            kind TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('pending','flushed')),
            created_at_utc TEXT NOT NULL,
            UNIQUE(run_id, sequence),
            FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
        )""",
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_one_active_round_per_run
        ON rounds(run_id)
        WHERE state IN ('WAITING_FOR_PLAN','READY_TO_EXECUTE','EXECUTING',
                        'WAITING_FOR_EVALUATION','READY_TO_FINISH')""",
        """
        INSERT OR IGNORE INTO schema_meta(key, value)
        VALUES ('schema_version', ?)""",
    ]
    for statement in statements[:-1]:
        connection.execute(statement)
    # A database created by an earlier v1.1 commit may already exist. Add new
    # frozen fields without rewriting existing rows; old sessions remain
    # readable but cannot silently acquire a new search-policy envelope.
    table_columns = {
        "runs": {str(row[1]) for row in connection.execute("PRAGMA table_info(runs)")},
        "rounds": {str(row[1]) for row in connection.execute("PRAGMA table_info(rounds)")},
        "solver_calls": {str(row[1]) for row in connection.execute("PRAGMA table_info(solver_calls)")},
    }
    for name, definition in {
        "problem_spec_hash": "TEXT",
        "benchmark_id": "TEXT",
        "benchmark_profile": "TEXT",
        "benchmark_spec_hash": "TEXT",
        "data_manifest_hash": "TEXT",
        "reference_manifest_hash": "TEXT",
        "metric_spec_hash": "TEXT",
        "inheritance_mode": "TEXT NOT NULL DEFAULT 'incumbent_only'",
        "feedback_mode": "TEXT NOT NULL DEFAULT 'runtime_facts'",
        "agent_guidance": "INTEGER NOT NULL DEFAULT 1",
        "experiment_manifest_sha256": "TEXT",
        "max_rounds": "INTEGER",
        "round_budget": "INTEGER",
    }.items():
        if name not in table_columns["runs"]:
            connection.execute(f"ALTER TABLE runs ADD COLUMN {name} {definition}")
    for name, definition in {
        "population_snapshot_ref": "TEXT",
        "population_snapshot_sha256": "TEXT",
        "seed_selection_ref": "TEXT",
        "seed_selection_sha256": "TEXT",
    }.items():
        if name not in table_columns["rounds"]:
            connection.execute(f"ALTER TABLE rounds ADD COLUMN {name} {definition}")
    for name, definition in {"metric_spec_hash": "TEXT", "origin": "TEXT"}.items():
        if name not in table_columns["solver_calls"]:
            connection.execute(f"ALTER TABLE solver_calls ADD COLUMN {name} {definition}")
    for name, definition in {
        "search_policy_defaults_json": "TEXT",
        "search_policy_limits_json": "TEXT",
        "solver_timeout": "REAL",
        "request_timeout": "REAL",
    }.items():
        if name not in table_columns["runs"]:
            connection.execute(f"ALTER TABLE runs ADD COLUMN {name} {definition}")
    connection.execute(statements[-1], (SCHEMA_VERSION,))
    connection.execute("UPDATE schema_meta SET value=? WHERE key='schema_version'", (SCHEMA_VERSION,))


def _row(connection: sqlite3.Connection, query: str, parameters: tuple[Any, ...]) -> sqlite3.Row | None:
    return connection.execute(query, parameters).fetchone()


def _require_run(
    connection: sqlite3.Connection,
    *,
    action: str,
    run_id: str | None,
) -> sqlite3.Row:
    found = _row(connection, "SELECT * FROM runs LIMIT 1", ())
    if found is None:
        raise SessionError("RUN_NOT_FOUND", "session run does not exist", action=action)
    if run_id is not None and run_id != found["run_id"]:
        raise SessionError(
            "RUN_ID_MISMATCH",
            f"expected run_id {run_id}, actual {found['run_id']}",
            action=action,
            run_id=str(found["run_id"]),
            state_version=int(found["state_version"]),
        )
    return found


def _require_schema(connection: sqlite3.Connection, *, action: str) -> None:
    row = _row(connection, "SELECT value FROM schema_meta WHERE key='schema_version'", ())
    if row is None or row["value"] != SCHEMA_VERSION:
        raise SessionError("SCHEMA_MISMATCH", "create a new session; legacy config lacks frozen execution parameters", action=action)


def _round(connection: sqlite3.Connection, run: sqlite3.Row) -> sqlite3.Row:
    query = "SELECT * FROM rounds WHERE run_id=? AND round_id=?"
    found = _row(connection, query, (run["run_id"], run["active_round_id"]))
    if found is None:
        found = _row(
            connection,
            "SELECT * FROM rounds WHERE run_id=? ORDER BY round_id DESC LIMIT 1",
            (run["run_id"],),
        )
    if found is None:
        raise SessionError(
            "SCHEMA_MISMATCH", "session has no round", action="session", run_id=str(run["run_id"])
        )
    return found


def _allowed_actions(run_state: str, round_state: str) -> list[str]:
    if run_state == "STOPPING":
        return ["state", "collect"]
    if run_state in {"COMPLETED", "STOPPED", "FAILED"}:
        return ["state", "read_evaluation"]
    if round_state == "WAITING_FOR_PLAN":
        return ["state", "memory_search", "memory_read", "submit_plan", "stop"]
    if round_state == "READY_TO_EXECUTE":
        return ["state", "execute", "stop"]
    if round_state == "EXECUTING":
        return ["state", "collect", "stop"]
    if round_state == "WAITING_FOR_EVALUATION":
        return ["state", "read_evaluation", "submit_evaluation", "stop"]
    if round_state == "READY_TO_FINISH":
        return ["state", "read_evaluation", "finish_round", "stop"]
    return ["state"]


def _policy_identity(run: sqlite3.Row) -> dict[str, Any]:
    result = {
        "optimization_skill": {
            "id": run["optimization_skill_id"],
            "version": run["optimization_skill_version"],
            "content_sha256": run["optimization_skill_sha256"],
        },
        "runtime": {
            "version": run["runtime_version"],
            "source_sha256": run["runtime_source_sha256"],
        },
        "memory_policy": {
            "id": run["memory_policy_id"],
            "version": run["memory_policy_version"],
        },
        "eoh_policy": {
            "engine": "official_eoh",
            "commit": run["eoh_commit"],
            "repair_policy": run["repair_policy_version"] or "off",
            "search_policy": _run_search_policy(run),
        },
    }
    result["benchmark"] = {
        "id": run["benchmark_id"] if "benchmark_id" in run.keys() else None,
        "profile": run["benchmark_profile"] if "benchmark_profile" in run.keys() else None,
        "problem_spec_hash": run["problem_spec_hash"] if "problem_spec_hash" in run.keys() else None,
        "benchmark_spec_hash": run["benchmark_spec_hash"] if "benchmark_spec_hash" in run.keys() else None,
        "data_manifest_hash": run["data_manifest_hash"] if "data_manifest_hash" in run.keys() else None,
        "reference_manifest_hash": run["reference_manifest_hash"] if "reference_manifest_hash" in run.keys() else None,
        "metric_spec_hash": run["metric_spec_hash"] if "metric_spec_hash" in run.keys() else None,
        "inheritance_mode": run["inheritance_mode"] if "inheritance_mode" in run.keys() else "incumbent_only",
        "feedback_mode": run["feedback_mode"] if "feedback_mode" in run.keys() else "runtime_facts",
        "agent_guidance": bool(run["agent_guidance"]) if "agent_guidance" in run.keys() else True,
        "experiment_manifest_sha256": run["experiment_manifest_sha256"] if "experiment_manifest_sha256" in run.keys() else None,
    }
    return result


def _run_search_policy(run: sqlite3.Row) -> dict[str, Any] | None:
    # A v1.1 Session created before search-policy ownership was introduced has
    # no new columns.  It remains readable as an immutable historical Session;
    # mutation identity gates reject it before this value is needed.
    if not all(name in run.keys() for name in ("search_policy_defaults_json", "search_policy_limits_json")):
        return None
    if run["search_policy_defaults_json"] is None or run["search_policy_limits_json"] is None:
        return None
    try:
        defaults = json.loads(run["search_policy_defaults_json"])
        limits = json.loads(run["search_policy_limits_json"])
    except (TypeError, json.JSONDecodeError):
        return None
    return {"defaults": defaults, "limits": limits}


def _budget_view(connection: sqlite3.Connection, run: sqlite3.Row) -> dict[str, Any]:
    # Count durable reservations, including unknown/interrupted effects.
    requests_used = 0
    solver_used = 0
    table_names = {str(r[0]) for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "requests" in table_names:
        requests_used = int(connection.execute("SELECT COUNT(*) FROM requests WHERE run_id=?", (run["run_id"],)).fetchone()[0])
    if "solver_calls" in table_names:
        solver_used = int(connection.execute("SELECT COUNT(*) FROM solver_calls WHERE run_id=?", (run["run_id"],)).fetchone()[0])
    active_round_id = run["active_round_id"]
    round_solver_used = 0
    if "solver_calls" in table_names and active_round_id is not None:
        round_solver_used = int(connection.execute(
            "SELECT COUNT(*) FROM solver_calls WHERE run_id=? AND round_id=?",
            (run["run_id"], active_round_id),
        ).fetchone()[0])
    dual = {
        "total_evaluation_attempts": solver_used,
        "novel_candidate_evaluations": 0,
        "seed_reevaluation_attempts": 0,
        "baseline_attempts": 0,
        "repair_attempts": 0,
    }
    if "solver_calls" in table_names:
        rows = connection.execute(
            "SELECT candidate_id, revision, code_sha256, origin "
            "FROM solver_calls WHERE run_id=?",
            (run["run_id"],),
        ).fetchall()
        novel_hashes: set[str] = set()
        for item in rows:
            candidate_id = str(item["candidate_id"] or "")
            revision = str(item["revision"] or "")
            code_hash = str(item["code_sha256"] or "")
            origin = str(item["origin"] or "")
            if candidate_id == "baseline":
                dual["baseline_attempts"] += 1
            elif candidate_id == "explicit_parent" or candidate_id.startswith("seed_"):
                dual["seed_reevaluation_attempts"] += 1
            elif origin == "generated" and revision != "repair_1":
                if code_hash and code_hash not in novel_hashes:
                    novel_hashes.add(code_hash)
                    dual["novel_candidate_evaluations"] += 1
            if revision == "repair_1":
                dual["repair_attempts"] += 1
    max_requests = run["eoh_max_requests"]
    max_solver_calls = run["max_solver_calls"]
    return {
        "eoh_max_requests": max_requests,
        "eoh_requests_used": requests_used,
        "eoh_requests_remaining": None if max_requests is None else max(0, int(max_requests) - requests_used),
        "eoh_round_max_requests": run["eoh_round_max_requests"],
        "max_solver_calls": max_solver_calls,
        "solver_calls_used": solver_used,
        "solver_calls_remaining": None if max_solver_calls is None else max(0, int(max_solver_calls) - solver_used),
        "round_budget": run["round_budget"] if "round_budget" in run.keys() else None,
        "round_solver_calls_used": round_solver_used,
        "round_solver_calls_remaining": (
            None if "round_budget" not in run.keys() or run["round_budget"] is None
            else max(0, int(run["round_budget"]) - round_solver_used)
        ),
        "engine_wall_seconds": run["engine_wall_seconds"],
        "round_wall_seconds": run["round_wall_seconds"],
        "repair_max_requests": run["repair_max_requests"],
        **dual,
    }


def _envelope(
    connection: sqlite3.Connection,
    run: sqlite3.Row,
    current_round: sqlite3.Row,
    *,
    action: str,
    operation_id: str | None = None,
    result: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    actions = _allowed_actions(run["state"], current_round["state"])
    if current_round["state"] == "READY_TO_EXECUTE" and _live_task_exists(connection, run["run_id"], current_round["round_id"]):
        actions = ["state", "collect", "stop"]
    if not current_round["evaluation_facts_ref"]:
        actions = [x for x in actions if x != "read_evaluation"]
    return {
        "ok": True,
        "action": action,
        "run_id": run["run_id"],
        "round_id": current_round["round_id"],
        "run_state": run["state"],
        "state": current_round["state"],
        "state_version": run["state_version"],
        "allowed_actions": actions,
        "operation_id": operation_id,
        "evidence_refs": [current_round[key] for key in (
            "normalized_plan_ref", "round_context_ref", "context_manifest_ref",
            "evaluation_facts_ref", "submitted_evaluation_ref", "memory_proposal_ref"
        ) if current_round[key]],
        "result": dict(result or {}),
    }


def _write_initial_files(output: Path, config: Mapping[str, Any], suite: Mapping[str, Any]) -> tuple[str, str]:
    config_text = json.dumps(config, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    suite_text = json.dumps(suite, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    _atomic_write(output / "dev_suite.json", suite_text)
    _atomic_write(output / "config_frozen.json", config_text)
    return _sha256(config_text), _sha256(suite_text)


def _queue_audit(connection, run_id, state_version, events):
    sequence = connection.execute("SELECT COALESCE(MAX(sequence),0) FROM audit_events WHERE run_id=?", (run_id,)).fetchone()[0]
    for kind, payload in events:
        sequence += 1
        connection.execute("INSERT INTO audit_events VALUES (?,?,?,?,?,?,'pending',?)",
                           (uuid.uuid4().hex, run_id, sequence, state_version, kind, _json(payload), _utc_now()))


def flush_audit(output: Path) -> bool:
    """Repairable hash-chained projection, serialized by the SQLite write lock.

    Publishing the whole deterministic projection atomically also recovers a
    crash between the file replacement and the outbox acknowledgement.
    """
    connection = _connect(output / "session.sqlite3")
    try:
        with _transaction(connection):
            rows = connection.execute("SELECT * FROM audit_events ORDER BY sequence").fetchall()
            previous = "0" * 64
            lines = []
            for row in rows:
                record = dict(schema_version=AUDIT_JOURNAL_SCHEMA, sequence=row["sequence"],
                              event_id=row["event_id"], kind=row["kind"], actor="session_runtime",
                              run_id=row["run_id"], state_version=row["state_version"],
                              previous_hash=previous, payload=json.loads(row["payload_json"]))
                record["content_hash"] = digest(record)
                previous = record["content_hash"]
                lines.append(_json(record))
            _atomic_write(output / "journal/events.jsonl", "\n".join(lines) + "\n")
            connection.execute("UPDATE audit_events SET status='flushed'")
        return True
    except (OSError, ValueError, sqlite3.Error):
        return False
    finally:
        connection.close()


def _verify_files(output: Path, run, *, action: str):
    read_only = action in {"state", "read-evaluation", "memory_search", "memory_read"}
    if not read_only and _runtime_source_hash() != run["runtime_source_sha256"]:
        raise SessionError("RUNTIME_IDENTITY_MISMATCH", "Restore the frozen runtime before mutating this Session", action=action)
    if not read_only and _required_skill_content_hash(action) != run["optimization_skill_sha256"]:
        raise SessionError("SKILL_IDENTITY_MISMATCH", "Restore the frozen Algorithm Optimization Skill before mutating this Session", action=action)
    try:
        config_bytes = (output / "config_frozen.json").read_bytes()
        config = json.loads(config_bytes)
        if _sha256(config_bytes) != run["config_sha256"]:
            raise ValueError("config_hash_mismatch")
        if config.get("schema_version") != CONFIG_SCHEMA and not read_only:
            raise ValueError("config_schema_mismatch")
        suite = json.loads((output / "dev_suite.json").read_text(encoding="utf-8"))
        spec = get_problem(run["problem"])
        spec.validate_suite(suite)
        for key in ("run_id", "problem", "problem_spec_hash", "suite_hash", "evaluator_hash"):
            if key not in config:
                if key == "problem_spec_hash" and run[key] is None:
                    continue
                raise ValueError(f"{key}_missing")
            if config[key] != run[key]:
                raise ValueError(f"{key}_mismatch")
        if "benchmark_id" in run.keys() and run["benchmark_id"]:
            benchmark_config = config.get("benchmark")
            if not isinstance(benchmark_config, Mapping) or benchmark_config.get("id") != run["benchmark_id"] or benchmark_config.get("profile") != run["benchmark_profile"]:
                raise ValueError("benchmark_identity_mismatch")
            for name in ("problem_spec_hash", "benchmark_spec_hash", "data_manifest_hash", "reference_manifest_hash", "metric_spec_hash"):
                if benchmark_config.get(name) != run[name]:
                    raise ValueError(f"{name}_mismatch")
        if "experiment_manifest_sha256" in run.keys() and run["experiment_manifest_sha256"]:
            manifest_config = config.get("experiment_manifest")
            if not isinstance(manifest_config, Mapping) or manifest_config.get("sha256") != run["experiment_manifest_sha256"]:
                raise ValueError("experiment_manifest_identity_mismatch")
        if run["inheritance_mode"] == "explicit_seeds":
            seed_config = (config.get("inheritance") or {}).get("explicit_seed_set")
            if not isinstance(seed_config, Mapping) or not isinstance(seed_config.get("ref"), str) or not isinstance(seed_config.get("sha256"), str):
                raise ValueError("explicit_seed_set_config_missing")
            seed_path = (output / seed_config["ref"]).resolve()
            if not seed_path.is_relative_to(output.resolve()):
                raise ValueError("explicit_seed_set_identity_mismatch")
            if not seed_path.is_file() or _sha256(seed_path.read_bytes()) != seed_config["sha256"]:
                raise ValueError("explicit_seed_set_identity_mismatch")
            seed_payload = json.loads(seed_path.read_text(encoding="utf-8"))
            if (not isinstance(seed_payload, Mapping)
                    or seed_payload.get("problem_spec_hash") != run["problem_spec_hash"]
                    or seed_payload.get("suite_hash") != run["suite_hash"]
                    or seed_payload.get("data_manifest_hash") != run["data_manifest_hash"]
                    or seed_payload.get("evaluator_hash") != run["evaluator_hash"]
                    or seed_payload.get("metric_spec_hash") != run["metric_spec_hash"]):
                raise ValueError("explicit_seed_set_identity_mismatch")
        if suite["content_hash"] != run["suite_hash"] or suite["problem"] != run["problem"]:
            raise ValueError("suite_identity_mismatch")
        if evaluator_source_hash() != run["evaluator_hash"] or _sha256(spec.baseline_code) != run["baseline_code_sha256"]:
            raise ValueError("execution_identity_changed")
        if not read_only:
            defaults, limits = _normalize_search_policy_config(
                action=action,
                defaults=config.get("eoh", {}).get("search_policy_defaults"),
                limits=config.get("eoh", {}).get("search_policy_limits"),
            )
            if _run_search_policy(run) != {
                "defaults": defaults,
                "limits": {key: list(value) for key, value in limits.items()},
            }:
                raise ValueError("search_policy_identity_mismatch")
        return config, suite
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise SessionError("EVIDENCE_INTEGRITY_FAILED", str(exc), action=action) from exc


def _init_input(
    *,
    output: Path,
    problem: str,
    operation_id: str,
    eoh_model: str,
    eoh_endpoint: str,
    eoh_api_key_env: str,
    eoh_max_requests: int | None,
    eoh_round_max_requests: int | None,
    engine_wall_seconds: float | None,
    round_wall_seconds: float | None,
    max_solver_calls: int | None,
    repair_mode: str,
    repair_max_requests: int | None,
    memory_store: str | None,
    solution_threshold: float | None,
    seed: int,
    size: int,
    count: int,
    search_policy_defaults: Mapping[str, int],
    search_policy_limits: Mapping[str, tuple[int, int]],
    solver_timeout: float,
    request_timeout: float,
    eoh_thinking: str = "provider-default",
    benchmark_id: str | None = None,
    benchmark_profile_name: str | None = None,
    benchmark_spec_hash: str | None = None,
    data_manifest_hash: str | None = None,
    reference_manifest_hash: str | None = None,
    metric_spec_hash: str | None = None,
    inheritance_mode: str = "incumbent_only",
    feedback_mode: str = "runtime_facts",
    agent_guidance: bool = True,
    experiment_manifest_sha256: str | None = None,
    problem_spec_hash: str | None = None,
    max_rounds: int | None = None,
    round_budget: int | None = None,
    explicit_seed_set_sha256: str | None = None,
) -> dict[str, Any]:
    return {
        "output": str(output),
        "problem": problem,
        "problem_spec_hash": problem_spec_hash,
        "max_rounds": max_rounds,
        "round_budget": round_budget,
        "explicit_seed_set_sha256": explicit_seed_set_sha256,
        "operation_id": operation_id,
        "eoh_model": eoh_model,
        "eoh_endpoint": eoh_endpoint,
        "eoh_api_key_env": eoh_api_key_env,
        "eoh_max_requests": eoh_max_requests,
        "eoh_round_max_requests": eoh_round_max_requests,
        "engine_wall_seconds": engine_wall_seconds,
        "round_wall_seconds": round_wall_seconds,
        "max_solver_calls": max_solver_calls,
        "repair_mode": repair_mode,
        "repair_max_requests": repair_max_requests,
        "memory_store": memory_store,
        "solution_threshold": solution_threshold,
        "seed": seed,
        "size": size,
        "count": count,
        "search_policy_defaults": dict(search_policy_defaults),
        "search_policy_limits": {key: list(value) for key, value in search_policy_limits.items()},
        "solver_timeout": solver_timeout,
        "request_timeout": request_timeout,
        "eoh_thinking": eoh_thinking,
        "benchmark_id": benchmark_id,
        "benchmark_profile": benchmark_profile_name,
        "benchmark_spec_hash": benchmark_spec_hash,
        "data_manifest_hash": data_manifest_hash,
        "reference_manifest_hash": reference_manifest_hash,
        "metric_spec_hash": metric_spec_hash,
        "inheritance_mode": inheritance_mode,
        "feedback_mode": feedback_mode,
        "agent_guidance": bool(agent_guidance),
        "experiment_manifest_sha256": experiment_manifest_sha256,
    }


def _validate_experiment_manifest(
    payload: Mapping[str, Any],
    *,
    benchmark: Any,
    benchmark_spec_hash: str | None,
    metric_spec_hash: str | None,
    runtime_hash: str,
    skill_hash: str,
    eoh_model: str,
    eoh_endpoint: str,
    inheritance_mode: str,
    feedback_mode: str,
    agent_guidance: bool,
    repair_mode: str,
    memory_enabled: bool,
    evaluation_budget: int,
    population_size: int,
    max_rounds: int,
    round_budget: int,
    search_seed: int,
) -> tuple[dict[str, Any], str]:
    """Validate and canonicalize a user-supplied benchmark manifest.

    A manifest is an experiment identity, not an annotation.  Accepting a
    caller-provided hash without checking the frozen runtime values would let
    results from different evaluators or policies be mixed under one label.
    """
    if benchmark is None:
        raise SessionError("INVALID_ARGUMENT", "experiment manifest requires a benchmark", action="init")
    from agent_skill_loop.benchmark import ExperimentManifest

    values = dict(payload)
    declared_hash = values.pop("experiment_manifest_sha256", None)
    values.pop("schema_version", None)
    values.pop("manifest_version", None)
    try:
        manifest = ExperimentManifest(**values)
    except (TypeError, ValueError) as exc:
        raise SessionError("INVALID_ARGUMENT", f"invalid experiment manifest: {exc}", action="init") from exc
    if declared_hash is not None and declared_hash != manifest.content_hash:
        raise SessionError("INVALID_ARGUMENT", "experiment_manifest_hash_mismatch", action="init")
    expected = {
        "benchmark_spec_hash": benchmark_spec_hash,
        "metric_spec_hash": metric_spec_hash,
        "eoh_commit": EOH_COMMIT,
        "runtime_hash": runtime_hash,
        "skill_hash": skill_hash,
        "model": eoh_model,
        "endpoint_identity": eoh_endpoint,
        "inheritance_mode": inheritance_mode,
        "feedback_mode": feedback_mode,
        "agent_guidance": agent_guidance,
        "repair_mode": repair_mode,
        "memory_enabled": memory_enabled,
        "evaluation_budget": evaluation_budget,
        "population_size": population_size,
        "rounds": max_rounds,
        "round_budget": round_budget,
        "search_seed": search_seed,
    }
    for name, actual in expected.items():
        if getattr(manifest, name) != actual:
            raise SessionError("INVALID_ARGUMENT", f"experiment_manifest_{name}_mismatch", action="init")
    return manifest.as_dict(), manifest.content_hash


def _normalize_search_policy_config(
    *,
    action: str,
    defaults: Mapping[str, Any] | None,
    limits: Mapping[str, Any] | None,
) -> tuple[dict[str, int], dict[str, tuple[int, int]]]:
    """Validate the frozen search envelope independently of resource budgets."""
    raw_defaults = dict(SEARCH_POLICY_DEFAULTS if defaults is None else defaults)
    raw_limits = dict(SEARCH_POLICY_LIMITS if limits is None else limits)
    if set(raw_defaults) != set(SEARCH_POLICY_KEYS) or set(raw_limits) != set(SEARCH_POLICY_KEYS):
        raise SessionError("INVALID_ARGUMENT", "search policy must contain pop_size, n_pop and max_sample_nums", action=action)
    normalized_limits: dict[str, tuple[int, int]] = {}
    for name in SEARCH_POLICY_KEYS:
        value = raw_limits[name]
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            raise SessionError("INVALID_ARGUMENT", f"search policy limit for {name} must be [min, max]", action=action)
        lower, upper = value
        if any(isinstance(item, bool) or not isinstance(item, int) for item in (lower, upper)):
            raise SessionError("INVALID_ARGUMENT", f"search policy limit for {name} must be integer-valued", action=action)
        minimum = SEARCH_POLICY_MINIMUMS[name]
        if lower < minimum or upper < lower:
            raise SessionError("INVALID_ARGUMENT", f"search policy limit for {name} is invalid", action=action)
        normalized_limits[name] = (lower, upper)
    normalized_defaults: dict[str, int] = {}
    for name in SEARCH_POLICY_KEYS:
        value = raw_defaults[name]
        if isinstance(value, bool) or not isinstance(value, int):
            raise SessionError("INVALID_ARGUMENT", f"search policy default for {name} must be an integer", action=action)
        lower, upper = normalized_limits[name]
        if value < lower or value > upper:
            raise SessionError("INVALID_ARGUMENT", f"search policy default for {name} is outside its limits", action=action)
        normalized_defaults[name] = value
    return normalized_defaults, normalized_limits


def search_policy_limits(config: Mapping[str, Any]) -> dict[str, tuple[int, int]]:
    eoh = config.get("eoh")
    if not isinstance(eoh, Mapping):
        raise ValueError("search_policy_config_missing")
    _defaults, limits = _normalize_search_policy_config(
        action="search-policy",
        defaults=eoh.get("search_policy_defaults"),
        limits=eoh.get("search_policy_limits"),
    )
    return limits


def effective_search_policy(config: Mapping[str, Any], requested: Mapping[str, Any] | None) -> dict[str, int]:
    eoh = config.get("eoh")
    if not isinstance(eoh, Mapping):
        raise ValueError("search_policy_config_missing")
    defaults, limits = _normalize_search_policy_config(
        action="search-policy",
        defaults=eoh.get("search_policy_defaults"),
        limits=eoh.get("search_policy_limits"),
    )
    if requested is None:
        return defaults
    if not isinstance(requested, Mapping) or not set(requested).issubset(SEARCH_POLICY_KEYS):
        raise ValueError("PLAN_SEARCH_POLICY_OUT_OF_BOUNDS")
    result = dict(defaults)
    for name, value in requested.items():
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("PLAN_SEARCH_POLICY_OUT_OF_BOUNDS")
        lower, upper = limits[name]
        if value < lower or value > upper:
            raise ValueError("PLAN_SEARCH_POLICY_OUT_OF_BOUNDS")
        result[name] = value
    return result


def _validate_init_values(
    *,
    action: str,
    eoh_model: str,
    eoh_endpoint: str,
    eoh_api_key_env: str,
    repair_mode: str,
    eoh_max_requests: int | None,
    eoh_round_max_requests: int | None,
    engine_wall_seconds: float | None,
    round_wall_seconds: float | None,
    max_solver_calls: int | None,
    repair_max_requests: int | None,
    solution_threshold: float | None,
    search_policy_defaults: Mapping[str, Any] | None,
    search_policy_limits: Mapping[str, Any] | None,
    solver_timeout: float,
    request_timeout: float,
) -> None:
    if not isinstance(eoh_model, str) or not eoh_model.strip():
        raise SessionError("INVALID_ARGUMENT", "--eoh-model must be non-empty", action=action)
    if not isinstance(eoh_endpoint, str) or not eoh_endpoint.strip():
        raise SessionError("INVALID_ARGUMENT", "--eoh-endpoint must be non-empty", action=action)
    if not isinstance(eoh_api_key_env, str) or not eoh_api_key_env.strip() or not eoh_api_key_env.replace("_", "").isalnum():
        raise SessionError("INVALID_ARGUMENT", "--eoh-api-key-env is invalid", action=action)
    if repair_mode not in {"off", "bounded"}:
        raise SessionError("INVALID_ARGUMENT", "--repair-mode must be off or bounded", action=action)
    integer_values = {
        "eoh_max_requests": eoh_max_requests,
        "eoh_round_max_requests": eoh_round_max_requests,
        "max_solver_calls": max_solver_calls,
        "repair_max_requests": repair_max_requests,
    }
    for name, value in integer_values.items():
        if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
            raise SessionError("INVALID_ARGUMENT", f"{name} must be a non-negative integer", action=action)
    for name, value in {
        "engine_wall_seconds": engine_wall_seconds,
        "round_wall_seconds": round_wall_seconds,
        "solver_timeout": solver_timeout,
        "request_timeout": request_timeout,
        "solution_threshold": solution_threshold,
    }.items():
        if value is not None:
            try:
                import math
                valid = math.isfinite(float(value)) and float(value) >= 0
            except (TypeError, ValueError, OverflowError):
                valid = False
            if not valid or (name == "solver_timeout" and float(value) <= 1) or (name == "request_timeout" and float(value) <= 0):
                raise SessionError("INVALID_ARGUMENT", f"{name} is invalid", action=action)
    _normalize_search_policy_config(
        action=action,
        defaults=search_policy_defaults,
        limits=search_policy_limits,
    )


def initialize_session(
    *,
    output: Path,
    operation_id: str,
    problem: str = PROBLEM_CVRP,
    eoh_model: str,
    eoh_endpoint: str = "https://api.deepseek.com/v1/chat/completions",
    eoh_api_key_env: str = "DEEPSEEK_API_KEY",
    eoh_max_requests: int | None = 32,
    eoh_round_max_requests: int | None = None,
    engine_wall_seconds: float | None = 420.0,
    round_wall_seconds: float | None = None,
    max_solver_calls: int | None = None,
    repair_mode: str | None = None,
    repair_max_requests: int | None = None,
    memory_store: str | None = None,
    memory_enabled: bool | None = None,
    solution_threshold: float | None = None,
    seed: int = DEFAULT_SEED,
    size: int = DEFAULT_SIZE,
    count: int = DEFAULT_COUNT,
    search_policy_defaults: Mapping[str, int] | None = None,
    search_policy_limits: Mapping[str, Any] | None = None,
    solver_timeout: float = DEFAULT_SOLVER_TIMEOUT,
    request_timeout: float = 180.0,
    eoh_thinking: str = "provider-default",
    benchmark_id: str | None = None,
    benchmark_profile_name: str = "obp_mini",
    inheritance_mode: str | None = None,
    feedback_mode: str | None = None,
    agent_guidance: bool | None = None,
    experiment_manifest: Mapping[str, Any] | None = None,
    max_rounds: int | None = None,
    round_budget: int | None = None,
    explicit_seed_set: Sequence[Mapping[str, Any]] | Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    action = "init"
    if eoh_thinking not in {"provider-default", "enabled", "disabled"}:
        raise SessionError("INVALID_ARGUMENT", "invalid eoh thinking mode", action=action)
    output = Path(output).resolve()
    if not isinstance(operation_id, str) or not operation_id.strip():
        raise SessionError("INVALID_ARGUMENT", "--operation-id must be non-empty", action=action)
    manifest_hints = dict(experiment_manifest) if isinstance(experiment_manifest, Mapping) else {}
    if repair_mode is None:
        repair_mode = str(manifest_hints.get("repair_mode") or "off")
    if inheritance_mode is None:
        inheritance_mode = str(manifest_hints.get("inheritance_mode") or "incumbent_only")
    if feedback_mode is None:
        feedback_mode = str(manifest_hints.get("feedback_mode") or "runtime_facts")
    if agent_guidance is None:
        agent_guidance = bool(manifest_hints.get("agent_guidance", True))
    if memory_enabled is None:
        if "memory_enabled" in manifest_hints:
            memory_enabled = bool(manifest_hints["memory_enabled"])
        elif memory_store is not None:
            memory_enabled = True
        else:
            # Ordinary optimization Sessions share lightweight Memory by
            # default. Controlled benchmark Sessions remain isolated/off
            # unless their ExperimentManifest explicitly enables it.
            memory_enabled = benchmark_id is None
    if not isinstance(memory_enabled, bool):
        raise SessionError("INVALID_ARGUMENT", "memory_enabled must be boolean", action=action)
    if not memory_enabled and memory_store is not None:
        raise SessionError("INVALID_ARGUMENT", "memory_store conflicts with disabled memory", action=action)
    memory_store = str(Path(memory_store).expanduser().resolve()) if memory_store else (
        str(default_memory_store()) if memory_enabled else None
    )
    if inheritance_mode not in {"incumbent_only", "population_seeds", "explicit_seeds"}:
        raise SessionError("INVALID_ARGUMENT", "invalid inheritance mode", action=action)
    if inheritance_mode == "explicit_seeds" and explicit_seed_set is None:
        raise SessionError("INVALID_ARGUMENT", "explicit_seeds requires an explicit seed set", action=action)
    if inheritance_mode != "explicit_seeds" and explicit_seed_set is not None:
        raise SessionError("INVALID_ARGUMENT", "explicit seed set requires explicit_seeds mode", action=action)
    if benchmark_id is not None and (count != DEFAULT_COUNT or size != DEFAULT_SIZE):
        raise SessionError("INVALID_ARGUMENT", "benchmark sessions use the frozen suite; count and size are not configurable", action=action)
    if feedback_mode not in {"off", "runtime_facts"}:
        raise SessionError("INVALID_ARGUMENT", "invalid feedback mode", action=action)
    if not isinstance(agent_guidance, bool):
        raise SessionError("INVALID_ARGUMENT", "agent_guidance must be boolean", action=action)
    if max_rounds is None:
        if manifest_hints.get("rounds") is not None:
            max_rounds = manifest_hints["rounds"]
        elif benchmark_id is not None:
            # Benchmark manifests and reports need a finite round identity;
            # ordinary Sessions retain the historical agent-controlled limit.
            max_rounds = 1
    if round_budget is None and manifest_hints.get("round_budget") is not None:
        round_budget = manifest_hints.get("round_budget")
    if max_solver_calls is None and manifest_hints.get("evaluation_budget") is not None:
        max_solver_calls = manifest_hints.get("evaluation_budget")
    if experiment_manifest is not None and search_policy_defaults is None:
        search_policy_defaults = (manifest_hints.get("extra") or {}).get("search_policy_defaults") or {
            "pop_size": manifest_hints.get("population_size", SEARCH_POLICY_DEFAULTS["pop_size"]),
            "n_pop": SEARCH_POLICY_DEFAULTS["n_pop"],
            "max_sample_nums": SEARCH_POLICY_DEFAULTS["max_sample_nums"],
        }
    if experiment_manifest is not None and search_policy_limits is None:
        search_policy_limits = (manifest_hints.get("extra") or {}).get("search_policy_limits")
        if search_policy_limits is None:
            search_policy_limits = {key: list(value) for key, value in SEARCH_POLICY_LIMITS.items()}
            search_policy_limits["pop_size"][1] = max(
                search_policy_limits["pop_size"][1], int(search_policy_defaults["pop_size"])
            )
    if max_rounds is not None and (isinstance(max_rounds, bool) or not isinstance(max_rounds, int) or max_rounds < 1):
        raise SessionError("INVALID_ARGUMENT", "max_rounds must be a positive integer", action=action)
    if round_budget is not None and (isinstance(round_budget, bool) or not isinstance(round_budget, int) or round_budget < 1):
        raise SessionError("INVALID_ARGUMENT", "round_budget must be a positive integer", action=action)
    _validate_init_values(
        action=action,
        eoh_model=eoh_model,
        eoh_endpoint=eoh_endpoint,
        eoh_api_key_env=eoh_api_key_env,
        repair_mode=repair_mode,
        eoh_max_requests=eoh_max_requests,
        eoh_round_max_requests=eoh_round_max_requests,
        engine_wall_seconds=engine_wall_seconds,
        round_wall_seconds=round_wall_seconds,
        max_solver_calls=max_solver_calls,
        repair_max_requests=repair_max_requests,
        solution_threshold=solution_threshold,
        search_policy_defaults=search_policy_defaults,
        search_policy_limits=search_policy_limits,
        solver_timeout=solver_timeout,
        request_timeout=request_timeout,
    )
    benchmark = None
    metric = None
    problem_spec_hash = None
    benchmark_spec_hash = data_manifest_hash = reference_manifest_hash = metric_spec_hash = None
    if benchmark_id:
        try:
            from agent_skill_loop.benchmark import benchmark_profile, load_profile_suite
            benchmark, metric, _benchmark_item = benchmark_profile(benchmark_id, benchmark_profile_name)
            if problem == PROBLEM_CVRP:
                problem = benchmark.problem_id
            if problem != benchmark.problem_id:
                raise ValueError("benchmark_problem_mismatch")
            suite = dict(load_profile_suite(benchmark_id, benchmark_profile_name, split="dev_train"))
            benchmark_spec_hash = benchmark.content_hash
            data_manifest_hash = benchmark.train_manifest_hash
            reference_manifest_hash = benchmark.reference_manifest_hash
            metric_spec_hash = metric.content_hash
        except (OSError, TypeError, ValueError, KeyError) as exc:
            raise SessionError("INVALID_ARGUMENT", str(exc), action=action) from exc
    else:
        try:
            spec = get_problem(problem)
        except ValueError as exc:
            raise SessionError("INVALID_ARGUMENT", str(exc), action=action) from exc
    try:
        if benchmark is None:
            suite = dict(spec.build_suite(seed, split="dev_train", count=count, size=size))
        else:
            spec = get_problem(problem)
        spec.validate_suite(suite)
    except (TypeError, ValueError) as exc:
        raise SessionError("INVALID_ARGUMENT", f"invalid problem suite: {exc}", action=action) from exc
    problem_spec_hash = spec.content_hash

    normalized_search_defaults, normalized_search_limits = _normalize_search_policy_config(
        action=action,
        defaults=search_policy_defaults,
        limits=search_policy_limits,
    )
    if benchmark_id is not None and experiment_manifest is not None:
        manifest_extra = manifest_hints.get("extra")
        manifest_search_defaults = manifest_extra.get("search_policy_defaults") if isinstance(manifest_extra, Mapping) else None
        manifest_search_limits = manifest_extra.get("search_policy_limits") if isinstance(manifest_extra, Mapping) else None
        expected_defaults = manifest_search_defaults if isinstance(manifest_search_defaults, Mapping) else {
            "pop_size": manifest_hints.get("population_size"),
            "n_pop": SEARCH_POLICY_DEFAULTS["n_pop"],
            "max_sample_nums": SEARCH_POLICY_DEFAULTS["max_sample_nums"],
        }
        population_value = expected_defaults.get("pop_size") if isinstance(expected_defaults, Mapping) else None
        if isinstance(population_value, bool) or not isinstance(population_value, int):
            raise SessionError("INVALID_ARGUMENT", "experiment manifest population_size is invalid", action=action)
        expected_limits = manifest_search_limits if isinstance(manifest_search_limits, Mapping) else {
            "pop_size": [2, max(SEARCH_POLICY_LIMITS["pop_size"][1], population_value)],
            "n_pop": list(SEARCH_POLICY_LIMITS["n_pop"]),
            "max_sample_nums": list(SEARCH_POLICY_LIMITS["max_sample_nums"]),
        }
        expected_defaults_normalized, expected_limits_normalized = _normalize_search_policy_config(
            action=action,
            defaults=expected_defaults,
            limits=expected_limits,
        )
        if normalized_search_defaults != expected_defaults_normalized or normalized_search_limits != expected_limits_normalized:
            raise SessionError("INVALID_ARGUMENT", "benchmark_search_policy_manifest_mismatch", action=action)
    if round_budget is None and benchmark_id is not None:
        # Benchmark runs need a finite, manifest-visible per-round cap. Keep
        # ordinary Sessions backward-compatible: their round count and
        # search budget remain controlled by the existing EoH policy unless a
        # caller explicitly supplies round_budget.
        round_budget = normalized_search_defaults["max_sample_nums"] + 1

    explicit_seed_payload = None
    explicit_seed_set_sha256 = None
    if explicit_seed_set is not None:
        try:
            explicit_seed_payload = _normalize_explicit_seed_set(
                explicit_seed_set,
                problem_spec_hash=problem_spec_hash,
                suite_hash=str(suite["content_hash"]),
                evaluator_hash=evaluator_source_hash(),
                data_manifest_hash=data_manifest_hash,
                metric_spec_hash=metric_spec_hash,
            )
        except (TypeError, ValueError) as exc:
            raise SessionError("INVALID_ARGUMENT", str(exc), action=action) from exc
        if len(explicit_seed_payload["members"]) < normalized_search_defaults["pop_size"]:
            raise SessionError("INVALID_ARGUMENT", "explicit seed set is smaller than target population", action=action)
        explicit_seed_text = _json(explicit_seed_payload) + "\n"
        explicit_seed_set_sha256 = _sha256(explicit_seed_text)

    input_payload = _init_input(
        eoh_thinking=eoh_thinking,
        output=output,
        problem=problem,
        operation_id=operation_id,
        eoh_model=eoh_model,
        eoh_endpoint=eoh_endpoint,
        eoh_api_key_env=eoh_api_key_env,
        eoh_max_requests=eoh_max_requests,
        eoh_round_max_requests=eoh_round_max_requests,
        engine_wall_seconds=engine_wall_seconds,
        round_wall_seconds=round_wall_seconds,
        max_solver_calls=max_solver_calls,
        repair_mode=repair_mode,
        repair_max_requests=repair_max_requests,
        memory_store=memory_store,
        solution_threshold=solution_threshold,
        seed=seed,
        size=size,
        count=count,
        search_policy_defaults=normalized_search_defaults,
        search_policy_limits=normalized_search_limits,
        solver_timeout=solver_timeout,
        request_timeout=request_timeout,
        benchmark_id=benchmark_id,
        benchmark_profile_name=benchmark_profile_name if benchmark else None,
        benchmark_spec_hash=benchmark_spec_hash,
        data_manifest_hash=data_manifest_hash,
        reference_manifest_hash=reference_manifest_hash,
        metric_spec_hash=metric_spec_hash,
        inheritance_mode=inheritance_mode,
        feedback_mode=feedback_mode,
        agent_guidance=agent_guidance,
        experiment_manifest_sha256=(experiment_manifest or {}).get("experiment_manifest_sha256") if isinstance(experiment_manifest, Mapping) else None,
        problem_spec_hash=problem_spec_hash,
        max_rounds=max_rounds,
        round_budget=round_budget,
        explicit_seed_set_sha256=explicit_seed_set_sha256,
    )
    input_hash = _sha256(_json(input_payload))

    database = output / "session.sqlite3"
    if output.exists():
        if not database.is_file():
            raise SessionError("OUTPUT_EXISTS", f"output directory must be new: {output}", action=action)
        connection = _connect(database)
        try:
            _require_schema(connection, action=action)
            existing = _row(connection, "SELECT * FROM operations WHERE operation_id=?", (operation_id,))
            if existing is None:
                raise SessionError("OUTPUT_EXISTS", f"output directory already contains a different session: {output}", action=action)
            if existing["input_sha256"] != input_hash:
                raise SessionError("OPERATION_ID_CONFLICT", "operation_id was used with different init input", action=action, retryable=False)
            if existing["receipt_json"] is None:
                raise SessionError("SQLITE_ERROR", "init operation has no receipt", action=action, retryable=True)
            flush_audit(output)
            return json.loads(existing["receipt_json"])
        finally:
            connection.close()

    run_id = f"run_{uuid.uuid4().hex}"
    created_at = _utc_now()
    suite_hash = str(suite["content_hash"])
    evaluator_hash = evaluator_source_hash()
    runtime_hash = _runtime_source_hash()
    skill_hash = _required_skill_content_hash(action)
    memory_path = memory_store
    manifest_payload = None
    manifest_hash = None
    from eoh_frozen.generation_contract import generation_contract
    experiment_contracts = {
        "search_policy_defaults": normalized_search_defaults,
        "search_policy_limits": {key: list(value) for key, value in normalized_search_limits.items()},
        "generation_contract": generation_contract(eoh_model, eoh_endpoint, eoh_thinking, request_timeout),
        "resource_contract": {
            "request_budget": eoh_max_requests, "round_request_budget": eoh_round_max_requests,
            "wall_clock_budget": engine_wall_seconds, "round_wall_clock_budget": round_wall_seconds,
            "evaluation_budget": max_solver_calls, "round_evaluation_budget": round_budget,
            "solver_timeout_seconds": solver_timeout, "repair_request_budget": repair_max_requests,
        },
    }
    if isinstance(experiment_manifest, Mapping):
        manifest_payload, manifest_hash = _validate_experiment_manifest(
            experiment_manifest,
            benchmark=benchmark,
            benchmark_spec_hash=benchmark_spec_hash,
            metric_spec_hash=metric_spec_hash,
            runtime_hash=runtime_hash,
            skill_hash=skill_hash,
            eoh_model=eoh_model,
            eoh_endpoint=eoh_endpoint,
            inheritance_mode=inheritance_mode,
            feedback_mode=feedback_mode,
            agent_guidance=agent_guidance,
            repair_mode=repair_mode,
            memory_enabled=memory_path is not None,
            evaluation_budget=max_solver_calls or 0,
            population_size=normalized_search_defaults["pop_size"],
            max_rounds=max_rounds,
            round_budget=round_budget,
            search_seed=seed,
        )
    elif benchmark is not None:
        from agent_skill_loop.benchmark import ExperimentManifest
        generated_manifest = ExperimentManifest(
            benchmark_spec_hash=benchmark_spec_hash,
            metric_spec_hash=metric_spec_hash,
            eoh_commit=EOH_COMMIT,
            runtime_hash=runtime_hash,
            skill_hash=skill_hash,
            model=eoh_model,
            endpoint_identity=eoh_endpoint,
            inheritance_mode=inheritance_mode,
            feedback_mode=feedback_mode,
            agent_guidance=agent_guidance,
            repair_mode=repair_mode,
            memory_enabled=memory_path is not None,
            evaluation_budget=max_solver_calls or 0,
            population_size=normalized_search_defaults["pop_size"],
            rounds=max_rounds,
            round_budget=round_budget,
            search_seed=seed,
        )
        generated_manifest = ExperimentManifest(**{**generated_manifest.__dict__, "extra": experiment_contracts})
        manifest_payload = generated_manifest.as_dict()
        manifest_hash = generated_manifest.content_hash
    if isinstance(experiment_manifest, Mapping):
        for contract_name, actual_contract in experiment_contracts.items():
            if manifest_payload["extra"].get(contract_name) != actual_contract:
                raise SessionError("INVALID_ARGUMENT", f"experiment_manifest_{contract_name}_mismatch", action="init")
    config: dict[str, Any] = {
        "schema_version": CONFIG_SCHEMA,
        "run_id": run_id,
        "problem": problem,
        "problem_spec_hash": problem_spec_hash,
        "entrypoint": spec.entrypoint,
        "interface_version": spec.interface_version,
        "suite_hash": suite_hash,
        "evaluator_hash": evaluator_hash,
        "objective_direction": spec.objective_direction,
        "benchmark": {
            "id": benchmark_id,
            "profile": benchmark_profile_name if benchmark is not None else None,
            "problem_spec_hash": problem_spec_hash,
            "benchmark_spec_hash": benchmark_spec_hash,
            "data_manifest_hash": data_manifest_hash,
            "reference_manifest_hash": reference_manifest_hash,
            "metric_spec_hash": metric_spec_hash,
            "reference_kind": metric.reference_kind if metric is not None else None,
        } if benchmark is not None else None,
        "inheritance": {
            "mode": inheritance_mode,
            "population_snapshot_contract": "official_final_population_order_preserved",
            "explicit_seed_set": {
                "ref": "seeds/explicit_seeds.json",
                "sha256": explicit_seed_set_sha256,
            } if explicit_seed_payload is not None else None,
        },
        "experiment": {"max_rounds": max_rounds, "round_budget": round_budget},
        "feedback": {"mode": feedback_mode, "source": "runtime_facts" if feedback_mode == "runtime_facts" else None},
        "agent_guidance": bool(agent_guidance),
        "experiment_manifest": {"sha256": manifest_hash, "document": manifest_payload} if manifest_payload is not None else None,
        "baseline": {
            "code_sha256": _sha256(spec.baseline_code),
            "description": spec.baseline_description,
        },
        "optimization_skill": {
            "id": OPTIMIZATION_SKILL_ID,
            "version": OPTIMIZATION_SKILL_VERSION,
            "content_sha256": skill_hash,
        },
        "runtime": {"version": RUNTIME_VERSION, "source_sha256": runtime_hash},
        "memory": {
            "enabled": memory_path is not None,
            "store": memory_path,
            "policy_id": MEMORY_POLICY_ID if memory_path else None,
            "policy_version": MEMORY_POLICY_VERSION if memory_path else None,
        },
        "eoh": {
            "commit": EOH_COMMIT,
            "model": eoh_model,
            "endpoint": eoh_endpoint,
            "api_key_env": eoh_api_key_env,
            "request_timeout": request_timeout,
            "thinking": eoh_thinking,
            "search_policy_defaults": normalized_search_defaults,
            "search_policy_limits": {key: list(value) for key, value in normalized_search_limits.items()},
        },
        "evaluator": {"solver_timeout": solver_timeout},
        "repair": {
            "mode": repair_mode,
            "policy_version": REPAIR_POLICY_VERSION if repair_mode == "bounded" else None,
            "max_requests": repair_max_requests,
        },
        "budgets": {
            "eoh_max_requests": eoh_max_requests,
            "eoh_round_max_requests": eoh_round_max_requests,
            "max_solver_calls": max_solver_calls,
            "engine_wall_seconds": engine_wall_seconds,
            "round_wall_seconds": round_wall_seconds,
            "solution_threshold": solution_threshold,
        },
        "suite_generation": {
            "split": "dev_train",
            "seed": seed,
            "count": count,
            "size": size,
        },
        "search_seed": seed,
        "search_seed_derivation": "base_plus_round_id_minus_one",
        "init": {"provider_requests": 0, "solver_calls": 0},
    }
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=f".{output.name}.init-", dir=str(output.parent)))
        config_sha256, _ = _write_initial_files(staging, config, suite)
        if explicit_seed_payload is not None:
            _atomic_write(staging / "seeds/explicit_seeds.json", explicit_seed_text)
    except OSError as exc:
        raise SessionError("STORAGE_FAILED", str(exc), action=action, retryable=True) from exc
    database = staging / "session.sqlite3"
    connection = _connect(database)
    try:
        with _transaction(connection):
            _create_schema(connection)
            connection.execute(
                """
                INSERT INTO runs(
                    run_id, output_root, state, state_version, active_round_id,
                    problem, problem_spec_hash, benchmark_id, benchmark_profile, benchmark_spec_hash,
                    data_manifest_hash, reference_manifest_hash, metric_spec_hash,
                    inheritance_mode, feedback_mode, agent_guidance, experiment_manifest_sha256,
                    max_rounds, round_budget,
                    suite_hash, evaluator_hash, objective_direction,
                    baseline_code_sha256, optimization_skill_id, optimization_skill_version,
                    optimization_skill_sha256, runtime_version, runtime_source_sha256,
                    memory_enabled, memory_store, memory_policy_id, memory_policy_version,
                    eoh_commit, eoh_model, eoh_endpoint, eoh_api_key_env,
                    repair_mode, repair_policy_version, eoh_max_requests,
                    eoh_round_max_requests, max_solver_calls, repair_max_requests,
                    engine_wall_seconds, round_wall_seconds, solution_threshold,
                    solution_policy_id, created_at_utc, config_ref, config_sha256,
                    init_operation_id, search_policy_defaults_json, search_policy_limits_json,
                    solver_timeout, request_timeout
                ) VALUES (
                    ?,?,?,?,?,?,?,?,?,?,
                    ?,?,?,?,?,?,?,?,?,?,
                    ?,?,?,?,?,?,?,?,?,?,
                    ?,?,?,?,?,?,?,?,?,?,
                    ?,?,?,?,?,?,?,?,?,?,
                    ?,?,?,?
                )
                """,
                (
                    run_id, str(output), "RUNNING", 1, 1,
                     problem, problem_spec_hash, benchmark_id, benchmark_profile_name if benchmark is not None else None, benchmark_spec_hash,
                     data_manifest_hash, reference_manifest_hash, metric_spec_hash,
                     inheritance_mode, feedback_mode, 1 if agent_guidance else 0, manifest_hash,
                     max_rounds, round_budget,
                    suite_hash, evaluator_hash, spec.objective_direction,
                    _sha256(spec.baseline_code), OPTIMIZATION_SKILL_ID, OPTIMIZATION_SKILL_VERSION,
                    skill_hash, RUNTIME_VERSION, runtime_hash,
                    1 if memory_path else 0, memory_path,
                    MEMORY_POLICY_ID if memory_path else None, MEMORY_POLICY_VERSION if memory_path else None,
                    EOH_COMMIT, eoh_model, eoh_endpoint, eoh_api_key_env,
                    repair_mode, REPAIR_POLICY_VERSION if repair_mode == "bounded" else None,
                    eoh_max_requests, eoh_round_max_requests, max_solver_calls, repair_max_requests,
                    engine_wall_seconds, round_wall_seconds, solution_threshold, None,
                    created_at, "config_frozen.json", config_sha256, operation_id,
                    _json(normalized_search_defaults), _json({key: list(value) for key, value in normalized_search_limits.items()}),
                    solver_timeout, request_timeout,
                ),
            )
            connection.execute(
                """
                INSERT INTO rounds(run_id, round_id, state, updated_state_version, created_at_utc)
                VALUES (?, 1, 'WAITING_FOR_PLAN', 1, ?)
                """,
                (run_id, created_at),
            )
            receipt = _envelope(
                connection,
                _row(connection, "SELECT * FROM runs WHERE run_id=?", (run_id,)),
                _row(connection, "SELECT * FROM rounds WHERE run_id=? AND round_id=1", (run_id,)),
                action=action,
                operation_id=operation_id,
                result={
                    "config_ref": "config_frozen.json",
                    "suite_ref": "dev_suite.json",
                    "suite_hash": suite_hash,
                    "provider_requests": 0,
                    "solver_calls": 0,
                },
            )
            connection.execute(
                """
                INSERT INTO operations(
                    operation_id, run_id, round_id, action, input_sha256,
                    expected_state_version, result_state_version, status,
                    receipt_json, created_at_utc, finished_at_utc
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    operation_id, run_id, 1, action, input_hash, None, 1,
                    "SUCCEEDED", _json(receipt), created_at, created_at,
                ),
            )
            _queue_audit(connection, run_id, 1, [
                ("run_started", {"problem": problem, "suite_hash": suite_hash, "evaluator_hash": evaluator_hash}),
                ("operation_receipt", {"operation_id": operation_id, "action": action, "input_sha256": input_hash}),
            ])
        flush_audit(staging)
        try:
            connection.close()
            os.rename(staging, output)
        except OSError as exc:
            raise SessionError("STORAGE_FAILED", str(exc), action=action, retryable=True) from exc
        return receipt
    except SessionError:
        raise
    except sqlite3.Error as exc:
        raise SessionError("SQLITE_ERROR", str(exc), action=action, retryable=True) from exc
    finally:
        connection.close()
        if staging.exists() and not output.exists():
            shutil.rmtree(staging, ignore_errors=True)


def read_state(*, run: Path, expected_run_id: str | None = None) -> dict[str, Any]:
    action = "state"
    database = Path(run).resolve() / "session.sqlite3"
    if not database.is_file():
        raise SessionError("RUN_NOT_FOUND", f"session database not found: {database}", action=action)
    connection = _connect(database)
    try:
        # All fields in a state response must describe the same SQLite snapshot.
        # Autocommit SELECTs can otherwise combine an old version with a new
        # task terminal while the detached supervisor commits concurrently.
        connection.execute("BEGIN")
        _require_schema(connection, action=action)
        current_run = _require_run(connection, action=action, run_id=expected_run_id)
        _verify_files(Path(run).resolve(), current_run, action=action)
        current_round = _round(connection, current_run)
        skill_hash = _required_skill_content_hash(action)
        live_task = None
        table_names = {str(r[0]) for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "tasks" in table_names:
            task = _row(
                connection,
                "SELECT * FROM tasks WHERE run_id=? AND round_id=? ORDER BY created_at_utc DESC LIMIT 1",
                (current_run["run_id"], current_round["round_id"]),
            )
            live_task = dict(task) if task is not None else None
        result = {
            "integrity": {
                "config": "ok",
                "suite": "ok",
                "runtime_identity": "ok" if _runtime_source_hash() == current_run["runtime_source_sha256"] else "mismatch",
                "skill_identity": "ok" if skill_hash == current_run["optimization_skill_sha256"] else "mismatch",
                "audit": "pending" if connection.execute("SELECT 1 FROM audit_events WHERE status='pending' LIMIT 1").fetchone() else "ok",
            },
            "policy_identity": _policy_identity(current_run),
            "search_policy": _run_search_policy(current_run),
            "budgets": _budget_view(connection, current_run),
            "incumbent": {
                "ref": current_round["incumbent_after_ref"],
                "objective": current_round["incumbent_after_objective"],
            } if current_round["incumbent_after_ref"] else None,
            "feedback_ref": current_round["feedback_ref"],
            "feedback_basis": {
                "round_id": current_round["round_id"] - 1,
                "evaluation_ref": current_round["feedback_ref"],
                "suite_hash": current_run["suite_hash"],
            } if current_round["feedback_ref"] else None,
            "benchmark": {
                "id": current_run["benchmark_id"],
                "profile": current_run["benchmark_profile"],
                "problem_spec_hash": current_run["problem_spec_hash"],
                "benchmark_spec_hash": current_run["benchmark_spec_hash"],
                "data_manifest_hash": current_run["data_manifest_hash"],
                "reference_manifest_hash": current_run["reference_manifest_hash"],
                "metric_spec_hash": current_run["metric_spec_hash"],
                "inheritance_mode": current_run["inheritance_mode"],
                "feedback_mode": current_run["feedback_mode"],
                "agent_guidance": bool(current_run["agent_guidance"]),
                "experiment_manifest_sha256": current_run["experiment_manifest_sha256"],
            } if "benchmark_id" in current_run.keys() and current_run["benchmark_id"] else None,
            "experiment": {
                "max_rounds": current_run["max_rounds"] if "max_rounds" in current_run.keys() else None,
                "round_budget": current_run["round_budget"] if "round_budget" in current_run.keys() else None,
            },
            "population_snapshot": {
                "ref": current_round["population_snapshot_ref"],
                "sha256": current_round["population_snapshot_sha256"],
                "seed_selection_ref": current_round["seed_selection_ref"],
                "seed_selection_sha256": current_round["seed_selection_sha256"],
            } if "population_snapshot_ref" in current_round.keys() and current_round["population_snapshot_ref"] else None,
            "task": live_task,
            "config_ref": current_run["config_ref"],
            "config_sha256": current_run["config_sha256"],
            "memory": {
                "enabled": bool(current_run["memory_enabled"]),
                "store": current_run["memory_store"],
            },
        }
        if result["integrity"]["audit"] == "ok":
            try:
                audit = verify_audit_journal(Path(run).resolve() / "journal/events.jsonl", expected_run_id=current_run["run_id"])
                count = connection.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]
                if audit["events"] != count:
                    result["integrity"]["audit"] = "out_of_sync"
            except (OSError, ValueError):
                result["integrity"]["audit"] = "invalid"
        response = _envelope(connection, current_run, current_round, action=action, result=result)
        if result["integrity"]["runtime_identity"] == "mismatch" or result["integrity"]["skill_identity"] == "mismatch":
            response["allowed_actions"] = [x for x in response["allowed_actions"] if x in {"state", "stop", "read_evaluation", "memory_search"}]
        # Keep the high-value state fields at the envelope level as required
        # by the CLI contract.  ``result`` remains populated for callers that
        # treat every action uniformly.
        response.update({
            "integrity": result["integrity"],
            "policy_identity": result["policy_identity"],
            "search_policy": result["search_policy"],
            "budgets": result["budgets"],
            "incumbent": result["incumbent"],
            "feedback_ref": result["feedback_ref"],
            "feedback_basis": result["feedback_basis"],
            "task": result["task"],
            "memory": result["memory"],
        })
        return response
    except sqlite3.Error as exc:
        raise SessionError("SQLITE_ERROR", str(exc), action=action, retryable=True) from exc
    finally:
        connection.close()


def _live_task_exists(connection: sqlite3.Connection, run_id: str, round_id: int) -> bool:
    table = _row(connection, "SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'", ())
    if table is None:
        return False
    row = _row(
        connection,
        """
        SELECT 1 FROM tasks
        WHERE run_id=? AND round_id=? AND state IN ('CREATED','STARTING','RUNNING','STOP_REQUESTED')
        LIMIT 1
        """,
        (run_id, round_id),
    )
    return row is not None


def stop_session(
    *,
    run: Path,
    operation_id: str,
    expected_state_version: int,
    reason: str = "user_requested",
    expected_run_id: str | None = None,
) -> dict[str, Any]:
    action = "stop"
    if not isinstance(operation_id, str) or not operation_id.strip():
        raise SessionError("INVALID_ARGUMENT", "--operation-id must be non-empty", action=action)
    if isinstance(expected_state_version, bool) or not isinstance(expected_state_version, int) or expected_state_version < 1:
        raise SessionError("INVALID_ARGUMENT", "--expected-state-version must be a positive integer", action=action)
    if not isinstance(reason, str) or not reason.strip() or len(reason.strip()) > 256:
        raise SessionError("INVALID_ARGUMENT", "--reason must be 1-256 characters", action=action)
    database = Path(run).resolve() / "session.sqlite3"
    if not database.is_file():
        raise SessionError("RUN_NOT_FOUND", f"session database not found: {database}", action=action)
    connection = _connect(database)
    input_hash: str | None = None
    try:
        _require_schema(connection, action=action)
        flush_audit(Path(run).resolve())
        # The lock is acquired before the idempotency/version decision.  Two
        # concurrent stop calls therefore cannot both observe the same token.
        with _transaction(connection):
            current_run = _require_run(connection, action=action, run_id=expected_run_id)
            input_hash = _sha256(_json({"action": action, "run_id": current_run["run_id"], "reason": reason.strip()}))
            existing = _row(connection, "SELECT * FROM operations WHERE operation_id=?", (operation_id,))
            if existing is not None:
                if existing["input_sha256"] != input_hash:
                    raise SessionError(
                        "OPERATION_ID_CONFLICT",
                        "operation_id was used with different stop input",
                        action=action,
                        run_id=str(current_run["run_id"]),
                        round_id=int(current_run["active_round_id"]),
                        state_version=int(current_run["state_version"]),
                    )
                if existing["receipt_json"] is None:
                    raise SessionError("SQLITE_ERROR", "stop operation has no receipt", action=action, retryable=True)
                return json.loads(existing["receipt_json"])

            current_round = _round(connection, current_run)
            current_version = int(current_run["state_version"])
            # Check the token before terminal-state policy.  A stale caller
            # must receive STATE_VERSION_CONFLICT even if another caller has
            # already stopped the run.
            if current_version != expected_state_version:
                raise SessionError(
                    "STATE_VERSION_CONFLICT",
                    f"expected state_version {expected_state_version}, current is {current_version}",
                    action=action,
                    retryable=True,
                    run_id=str(current_run["run_id"]),
                    round_id=int(current_round["round_id"]),
                    state_version=current_version,
                )
            if current_run["state"] == "STOPPING":
                raise SessionError(
                    "RUN_STOPPING", "run is already stopping", action=action,
                    run_id=str(current_run["run_id"]), round_id=int(current_round["round_id"]), state_version=current_version,
                )
            if current_run["state"] in {"COMPLETED", "STOPPED", "FAILED"}:
                raise SessionError(
                    "RUN_TERMINAL", "run is already terminal", action=action,
                    run_id=str(current_run["run_id"]), round_id=int(current_round["round_id"]), state_version=current_version,
                )
            now = _utc_now()
            new_version = current_version + 1
            live_task = connection.execute("SELECT 1 FROM tasks WHERE run_id=? AND round_id=? AND state!='COLLECTED' LIMIT 1", (current_run["run_id"],current_round["round_id"])).fetchone() is not None
            if live_task:
                connection.execute(
                    "UPDATE runs SET state='STOPPING', state_version=? WHERE run_id=? AND state_version=?",
                    (new_version, current_run["run_id"], expected_state_version),
                )
                connection.execute(
                    "UPDATE tasks SET state='STOP_REQUESTED' WHERE run_id=? AND round_id=? AND state IN ('CREATED','STARTING','RUNNING')",
                    (current_run["run_id"], current_round["round_id"]),
                )
                connection.execute(
                    "UPDATE rounds SET updated_state_version=?, stop_reason=? WHERE run_id=? AND round_id=?",
                    (new_version, reason.strip(), current_run["run_id"], current_round["round_id"]),
                )
            else:
                connection.execute(
                    "UPDATE runs SET state='STOPPED', state_version=?, finished_at_utc=? WHERE run_id=? AND state_version=?",
                    (new_version, now, current_run["run_id"], expected_state_version),
                )
                connection.execute(
                    "UPDATE rounds SET state='STOPPED', updated_state_version=?, stop_reason=?, finished_at_utc=? WHERE run_id=? AND round_id=?",
                    (new_version, reason.strip(), now, current_run["run_id"], current_round["round_id"]),
                )
            updated_run = _row(connection, "SELECT * FROM runs WHERE run_id=?", (current_run["run_id"],))
            updated_round = _row(connection, "SELECT * FROM rounds WHERE run_id=? AND round_id=?", (current_run["run_id"], current_round["round_id"]))
            receipt = _envelope(
                connection,
                updated_run,
                updated_round,
                action=action,
                operation_id=operation_id,
                result={"reason": reason.strip(), "live_task_requested": live_task},
            )
            connection.execute(
                """
                INSERT INTO operations(
                    operation_id, run_id, round_id, action, input_sha256,
                    expected_state_version, result_state_version, status,
                    receipt_json, created_at_utc, finished_at_utc
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    operation_id, current_run["run_id"], current_round["round_id"], action, input_hash,
                    expected_state_version, new_version, "SUCCEEDED", _json(receipt), now, now,
                ),
            )
            events = [("state_transition", {"state": updated_run["state"]}),
                      ("operation_receipt", {"operation_id": operation_id, "action": action, "input_sha256": input_hash})]
            if not live_task:
                events.append(("run_finished", {"state": "STOPPED", "stop_reason": reason.strip()}))
            _queue_audit(connection, current_run["run_id"], new_version, events)
        flush_audit(Path(run).resolve())
        return receipt
    except SessionError:
        raise
    except sqlite3.Error as exc:
        raise SessionError("SQLITE_ERROR", str(exc), action=action, retryable=True) from exc
    finally:
        connection.close()


def error_envelope(error: SessionError) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": False,
        "action": error.action,
        "run_id": error.run_id,
        "round_id": error.round_id,
        "state_version": error.state_version,
        "error": {
            "code": error.code,
            "message": error.message,
            "retryable": error.retryable,
        },
    }
    return payload
