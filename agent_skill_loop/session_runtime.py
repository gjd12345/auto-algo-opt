"""Phase 1 session control plane.

This module deliberately stops at the control-plane boundary.  It creates a
recoverable SQLite run/round record and exposes read-only state plus a safe
stop transition.  It does not import or call a provider, EoH, or solver.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping

from agent_skill_loop.contracts import (
    DEFAULT_COUNT,
    DEFAULT_SEED,
    DEFAULT_SIZE,
    DEFAULT_SOLVER_TIMEOUT,
    EOH_COMMIT,
    PROBLEM_CVRP,
)
from agent_skill_loop.evaluator import evaluator_source_hash
from agent_skill_loop.journal import AuditJournal
from agent_skill_loop.problems.base import get_problem


SCHEMA_VERSION = "algorithm-optimization-session/v1"
CONFIG_SCHEMA = "algorithm-optimization-session-config/v1"
RUNTIME_VERSION = "0.1.0"
OPTIMIZATION_SKILL_ID = "algorithm-optimization"
OPTIMIZATION_SKILL_VERSION = "v1.1"
MEMORY_POLICY_ID = "markdown-memory"
MEMORY_POLICY_VERSION = "v1"
REPAIR_POLICY_VERSION = "bounded_v2"

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
    # The actual Coding Agent skill package is introduced in Phase 5.  Phase 1
    # still freezes an explicit identity descriptor rather than pretending a
    # mutable documentation file is executable skill content.
    descriptor = _json({
        "id": OPTIMIZATION_SKILL_ID,
        "version": OPTIMIZATION_SKILL_VERSION,
        "control_plane": "session-cli-v1",
    })
    return _sha256(descriptor)


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
    connection.executescript(
        """
        CREATE TABLE schema_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE runs (
            run_id TEXT PRIMARY KEY,
            output_root TEXT NOT NULL UNIQUE,
            state TEXT NOT NULL CHECK (state IN ('RUNNING','STOPPING','COMPLETED','STOPPED','FAILED')),
            state_version INTEGER NOT NULL CHECK (state_version >= 1),
            active_round_id INTEGER,
            problem TEXT NOT NULL,
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
            init_operation_id TEXT NOT NULL UNIQUE
        );

        CREATE TABLE rounds (
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
        );

        CREATE UNIQUE INDEX uq_one_active_round_per_run
        ON rounds(run_id)
        WHERE state IN (
            'WAITING_FOR_PLAN','READY_TO_EXECUTE','EXECUTING',
            'WAITING_FOR_EVALUATION','READY_TO_FINISH'
        );

        CREATE TABLE operations (
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
        );

        INSERT INTO schema_meta(key, value)
        VALUES ('schema_version', 'algorithm-optimization-session/v1');
        """
    )


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
        raise SessionError("SCHEMA_MISMATCH", "unsupported session schema", action=action)


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
    return {
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
        },
    }


def _budget_view(connection: sqlite3.Connection, run: sqlite3.Row) -> dict[str, Any]:
    # Phase 1 has no request or solver execution tables.  Keeping these fields
    # explicit makes the zero-effect init/state contract inspectable and leaves
    # room for Phase 3 ledger migrations without changing the CLI envelope.
    requests_used = 0
    solver_used = 0
    table_names = {str(r[0]) for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "requests" in table_names:
        requests_used = int(connection.execute("SELECT COUNT(*) FROM requests WHERE run_id=?", (run["run_id"],)).fetchone()[0])
    if "solver_calls" in table_names:
        solver_used = int(connection.execute("SELECT COUNT(*) FROM solver_calls WHERE run_id=?", (run["run_id"],)).fetchone()[0])
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
        "engine_wall_seconds": run["engine_wall_seconds"],
        "round_wall_seconds": run["round_wall_seconds"],
        "repair_max_requests": run["repair_max_requests"],
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
    return {
        "ok": True,
        "action": action,
        "run_id": run["run_id"],
        "round_id": current_round["round_id"],
        "run_state": run["state"],
        "state": current_round["state"],
        "state_version": run["state_version"],
        "allowed_actions": _allowed_actions(run["state"], current_round["state"]),
        "operation_id": operation_id,
        "result": dict(result or {}),
    }


def _write_initial_files(output: Path, config: Mapping[str, Any], suite: Mapping[str, Any]) -> tuple[str, str]:
    config_text = json.dumps(config, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    suite_text = json.dumps(suite, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    _atomic_write(output / "dev_suite.json", suite_text)
    _atomic_write(output / "config_frozen.json", config_text)
    return _sha256(config_text), _sha256(suite_text)


def _append_audit(
    output: Path,
    *,
    run_id: str,
    state_version: int,
    events: list[tuple[str, dict[str, Any]]],
    create: bool,
    action: str,
) -> None:
    try:
        audit = AuditJournal(output / "journal", run_id=run_id, create=create)
        for kind, payload in events:
            audit.append(kind, payload, state_version=state_version)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise SessionError(
            "STORAGE_FAILED", f"audit journal error: {type(exc).__name__}",
            action=action, retryable=True, run_id=run_id, state_version=state_version,
        ) from exc


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
    pop_size: int,
    n_pop: int,
    max_sample_nums: int | None,
    solver_timeout: float,
    request_timeout: float,
) -> dict[str, Any]:
    return {
        "output": str(output),
        "problem": problem,
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
        "pop_size": pop_size,
        "n_pop": n_pop,
        "max_sample_nums": max_sample_nums,
        "solver_timeout": solver_timeout,
        "request_timeout": request_timeout,
    }


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
    pop_size: int,
    n_pop: int,
    max_sample_nums: int | None,
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
        "max_sample_nums": max_sample_nums,
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
    if isinstance(pop_size, bool) or not isinstance(pop_size, int) or pop_size < 2:
        raise SessionError("INVALID_ARGUMENT", "pop_size must be >= 2", action=action)
    if isinstance(n_pop, bool) or not isinstance(n_pop, int) or n_pop < 0:
        raise SessionError("INVALID_ARGUMENT", "n_pop must be non-negative", action=action)


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
    repair_mode: str = "off",
    repair_max_requests: int | None = None,
    memory_store: str | None = None,
    solution_threshold: float | None = None,
    seed: int = DEFAULT_SEED,
    size: int = DEFAULT_SIZE,
    count: int = DEFAULT_COUNT,
    pop_size: int = 4,
    n_pop: int = 5,
    max_sample_nums: int | None = None,
    solver_timeout: float = DEFAULT_SOLVER_TIMEOUT,
    request_timeout: float = 180.0,
) -> dict[str, Any]:
    action = "init"
    output = Path(output).resolve()
    if not isinstance(operation_id, str) or not operation_id.strip():
        raise SessionError("INVALID_ARGUMENT", "--operation-id must be non-empty", action=action)
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
        pop_size=pop_size,
        n_pop=n_pop,
        max_sample_nums=max_sample_nums,
        solver_timeout=solver_timeout,
        request_timeout=request_timeout,
    )
    try:
        spec = get_problem(problem)
    except ValueError as exc:
        raise SessionError("INVALID_ARGUMENT", str(exc), action=action) from exc
    try:
        suite = dict(spec.build_suite(seed, split="dev_train", count=count, size=size))
        spec.validate_suite(suite)
    except (TypeError, ValueError) as exc:
        raise SessionError("INVALID_ARGUMENT", f"invalid problem suite: {exc}", action=action) from exc

    input_payload = _init_input(
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
        pop_size=pop_size,
        n_pop=n_pop,
        max_sample_nums=max_sample_nums,
        solver_timeout=solver_timeout,
        request_timeout=request_timeout,
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
            return json.loads(existing["receipt_json"])
        finally:
            connection.close()

    try:
        output.mkdir(parents=True, exist_ok=False)
    except OSError as exc:
        raise SessionError("STORAGE_FAILED", str(exc), action=action, retryable=True) from exc

    run_id = f"run_{uuid.uuid4().hex}"
    created_at = _utc_now()
    suite_hash = str(suite["content_hash"])
    evaluator_hash = evaluator_source_hash()
    runtime_hash = _runtime_source_hash()
    skill_hash = _skill_content_hash()
    memory_path = str(Path(memory_store).resolve()) if memory_store else None
    config: dict[str, Any] = {
        "schema_version": CONFIG_SCHEMA,
        "run_id": run_id,
        "problem": problem,
        "entrypoint": spec.entrypoint,
        "interface_version": spec.interface_version,
        "suite_hash": suite_hash,
        "evaluator_hash": evaluator_hash,
        "objective_direction": spec.objective_direction,
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
        },
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
        "init": {"provider_requests": 0, "solver_calls": 0},
    }
    config_sha256, _ = _write_initial_files(output, config, suite)
    connection = _connect(database)
    try:
        with _transaction(connection):
            _create_schema(connection)
            connection.execute(
                """
                INSERT INTO runs(
                    run_id, output_root, state, state_version, active_round_id,
                    problem, suite_hash, evaluator_hash, objective_direction,
                    baseline_code_sha256, optimization_skill_id, optimization_skill_version,
                    optimization_skill_sha256, runtime_version, runtime_source_sha256,
                    memory_enabled, memory_store, memory_policy_id, memory_policy_version,
                    eoh_commit, eoh_model, eoh_endpoint, eoh_api_key_env,
                    repair_mode, repair_policy_version, eoh_max_requests,
                    eoh_round_max_requests, max_solver_calls, repair_max_requests,
                    engine_wall_seconds, round_wall_seconds, solution_threshold,
                    solution_policy_id, created_at_utc, config_ref, config_sha256,
                    init_operation_id
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    run_id, str(output), "RUNNING", 1, 1,
                    problem, suite_hash, evaluator_hash, spec.objective_direction,
                    _sha256(spec.baseline_code), OPTIMIZATION_SKILL_ID, OPTIMIZATION_SKILL_VERSION,
                    skill_hash, RUNTIME_VERSION, runtime_hash,
                    1 if memory_path else 0, memory_path,
                    MEMORY_POLICY_ID if memory_path else None, MEMORY_POLICY_VERSION if memory_path else None,
                    EOH_COMMIT, eoh_model, eoh_endpoint, eoh_api_key_env,
                    repair_mode, REPAIR_POLICY_VERSION if repair_mode == "bounded" else None,
                    eoh_max_requests, eoh_round_max_requests, max_solver_calls, repair_max_requests,
                    engine_wall_seconds, round_wall_seconds, solution_threshold, None,
                    created_at, "config_frozen.json", config_sha256, operation_id,
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
        _append_audit(
            output,
            run_id=run_id,
            state_version=1,
            create=True,
            action=action,
            events=[
                ("run_started", {
                    "problem": problem,
                    "suite_hash": suite_hash,
                    "evaluator_hash": evaluator_hash,
                    "optimization_skill_id": OPTIMIZATION_SKILL_ID,
                    "optimization_skill_version": OPTIMIZATION_SKILL_VERSION,
                    "eoh_commit": EOH_COMMIT,
                    "eoh_model": eoh_model,
                    "eoh_endpoint": eoh_endpoint,
                    "eoh_api_key_env": eoh_api_key_env,
                }),
                ("operation_receipt", {
                    "operation_id": operation_id,
                    "action": action,
                    "result_state_version": 1,
                    "input_sha256": input_hash,
                }),
            ],
        )
        return receipt
    except SessionError:
        raise
    except sqlite3.Error as exc:
        raise SessionError("SQLITE_ERROR", str(exc), action=action, retryable=True) from exc
    finally:
        connection.close()


def read_state(*, run: Path, expected_run_id: str | None = None) -> dict[str, Any]:
    action = "state"
    database = Path(run).resolve() / "session.sqlite3"
    if not database.is_file():
        raise SessionError("RUN_NOT_FOUND", f"session database not found: {database}", action=action)
    connection = _connect(database)
    try:
        _require_schema(connection, action=action)
        current_run = _require_run(connection, action=action, run_id=expected_run_id)
        current_round = _round(connection, current_run)
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
            "policy_identity": _policy_identity(current_run),
            "budgets": _budget_view(connection, current_run),
            "incumbent": {
                "ref": current_round["incumbent_after_ref"],
                "objective": current_round["incumbent_after_objective"],
            } if current_round["incumbent_after_ref"] else None,
            "feedback_ref": current_round["feedback_ref"],
            "task": live_task,
            "config_ref": current_run["config_ref"],
            "config_sha256": current_run["config_sha256"],
            "memory": {
                "enabled": bool(current_run["memory_enabled"]),
                "store": current_run["memory_store"],
            },
        }
        response = _envelope(connection, current_run, current_round, action=action, result=result)
        # Keep the high-value state fields at the envelope level as required
        # by the CLI contract.  ``result`` remains populated for callers that
        # treat every action uniformly.
        response.update({
            "policy_identity": result["policy_identity"],
            "budgets": result["budgets"],
            "incumbent": result["incumbent"],
            "feedback_ref": result["feedback_ref"],
            "task": result["task"],
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
        now = _utc_now()
        new_version = current_version + 1
        live_task = _live_task_exists(connection, str(current_run["run_id"]), int(current_round["round_id"]))
        with _transaction(connection):
            if live_task:
                connection.execute(
                    "UPDATE runs SET state='STOPPING', state_version=? WHERE run_id=?",
                    (new_version, current_run["run_id"]),
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
                    "UPDATE runs SET state='STOPPED', state_version=?, finished_at_utc=? WHERE run_id=?",
                    (new_version, now, current_run["run_id"]),
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
        audit_events = [
            ("state_transition", {
                "from_run_state": current_run["state"],
                "to_run_state": "STOPPING" if live_task else "STOPPED",
                "from_round_state": current_round["state"],
                "to_round_state": current_round["state"] if live_task else "STOPPED",
                "reason": reason.strip(),
            }),
            ("operation_receipt", {
                "operation_id": operation_id,
                "action": action,
                "result_state_version": new_version,
                "input_sha256": input_hash,
            }),
        ]
        if not live_task:
            audit_events.append(("run_finished", {"state": "STOPPED", "stop_reason": reason.strip()}))
        _append_audit(
            Path(run).resolve(),
            run_id=str(current_run["run_id"]),
            state_version=new_version,
            events=audit_events,
            create=False,
            action=action,
        )
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
