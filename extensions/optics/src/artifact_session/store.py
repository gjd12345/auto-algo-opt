"""SQLite authority, immutable evidence and idempotent state transitions."""

from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import time

from optics_backend.artifacts import canonical, digest, save, strict


class SessionError(ValueError):
    pass


DDL = """
CREATE TABLE run(id INTEGER PRIMARY KEY CHECK(id=1), config TEXT NOT NULL, config_hash TEXT NOT NULL,
 state TEXT NOT NULL, version INTEGER NOT NULL, round INTEGER NOT NULL, reason TEXT,
 incumbent TEXT, baseline TEXT, seal TEXT, final TEXT);
CREATE TABLE rounds(id INTEGER PRIMARY KEY, state TEXT NOT NULL, plan TEXT, facts TEXT, evaluation TEXT);
CREATE TABLE operations(id TEXT PRIMARY KEY, input_hash TEXT NOT NULL, receipt TEXT NOT NULL);
CREATE TABLE tasks(id TEXT PRIMARY KEY, round INTEGER, purpose TEXT, state TEXT NOT NULL,
 pid INTEGER, birth TEXT, result TEXT);
CREATE TABLE effects(id TEXT PRIMARY KEY, kind TEXT NOT NULL, assessment TEXT, round INTEGER,
 state TEXT NOT NULL, detail TEXT NOT NULL);
CREATE TABLE assessments(id TEXT PRIMARY KEY, round INTEGER, mode TEXT NOT NULL, state TEXT NOT NULL,
 artifact TEXT, facts TEXT, sequence INTEGER);
CREATE TABLE candidates(id TEXT PRIMARY KEY, round INTEGER NOT NULL, state TEXT NOT NULL, detail TEXT NOT NULL);
CREATE TABLE memory(id TEXT NOT NULL, version INTEGER NOT NULL, ref TEXT NOT NULL,
 PRIMARY KEY(id,version));
CREATE TABLE memory_reads(id TEXT NOT NULL, version INTEGER NOT NULL, hash TEXT NOT NULL,
 PRIMARY KEY(id,version));
CREATE TABLE events(sequence INTEGER PRIMARY KEY AUTOINCREMENT, time REAL NOT NULL, kind TEXT NOT NULL,
 body TEXT NOT NULL, previous_hash TEXT, hash TEXT NOT NULL);
"""


def dumps(value):
    return canonical(value).decode()


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, kind, value, traceback):
        try:
            return super().__exit__(kind, value, traceback)
        finally:
            self.close()


def connect(run):
    db = sqlite3.connect(Path(run) / "session.sqlite", timeout=20, isolation_level=None, factory=ClosingConnection)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA synchronous=FULL")
    return db


@contextmanager
def transaction(run):
    db = connect(run)
    try:
        db.execute("BEGIN IMMEDIATE")
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def record(db):
    return dict(db.execute("SELECT * FROM run WHERE id=1").fetchone())


def config(db):
    row = record(db)
    value = json.loads(row["config"])
    if digest(canonical(value)) != row["config_hash"]:
        raise SessionError("CONFIG_HASH_MISMATCH")
    return value


def event(db, kind, body):
    previous = db.execute("SELECT hash FROM events ORDER BY sequence DESC LIMIT 1").fetchone()
    prior = previous[0] if previous else None
    stamp = time.time()
    hashed = digest(canonical({"time": stamp, "kind": kind, "body": body, "previous_hash": prior}))
    db.execute("INSERT INTO events(time,kind,body,previous_hash,hash) VALUES(?,?,?,?,?)",
               (stamp, kind, dumps(body), prior, hashed))


def change(db, **updates):
    allowed = {"state", "round", "reason", "incumbent", "baseline", "seal", "final"}
    if set(updates) - allowed:
        raise SessionError("INVALID_STATE_UPDATE")
    columns = ",".join(k + "=?" for k in updates)
    db.execute(f"UPDATE run SET {columns},version=version+1 WHERE id=1", tuple(updates.values()))


def evidence(run, relative, value):
    path = Path(run) / relative
    ref = {"path": relative, "sha256": digest(canonical(value))}
    if path.exists():
        # Recover an orphaned durable file only if its full immutable content agrees.
        read(run, ref)
    else:
        save(path, value)
    return ref


def read(run, ref):
    relative = Path(ref["path"])
    path = Path(run) / relative
    if relative.is_absolute() or ".." in relative.parts or path.is_symlink() or Path(run).resolve() not in path.resolve().parents:
        raise SessionError("EVIDENCE_PATH_ESCAPE")
    raw = path.read_bytes()
    if digest(raw) != ref["sha256"]:
        raise SessionError("EVIDENCE_HASH_MISMATCH")
    return strict(raw, max(len(raw), 1_000_000))


def operation(run, action, operation_id, expected_version, payload, mutation):
    if not isinstance(operation_id, str) or not operation_id or len(operation_id) > 128:
        raise SessionError("OPERATION_ID_REQUIRED")
    hashed = digest(canonical({"action": action, "payload": payload}))
    with transaction(run) as db:
        prior = db.execute("SELECT * FROM operations WHERE id=?", (operation_id,)).fetchone()
        if prior:
            if prior["input_hash"] != hashed:
                raise SessionError("OPERATION_ID_CONFLICT")
            return json.loads(prior["receipt"]), False
        if record(db)["version"] != expected_version:
            raise SessionError("STATE_VERSION_CONFLICT")
        result = mutation(db)
        result = {**result, "state_version": record(db)["version"], "operation_id": operation_id}
        event(db, action, {"operation_id": operation_id, "input_hash": hashed, "result": result})
        db.execute("INSERT INTO operations VALUES(?,?,?)", (operation_id, hashed, dumps(result)))
        return result, True
