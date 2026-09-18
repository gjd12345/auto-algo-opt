"""Explicit online-only continuation, with fresh evaluation and unchanged baseline."""

import json
from pathlib import Path
import sqlite3

from optics_backend.artifacts import canonical, digest
from optics_backend.offline import reload_facts
from optics_backend.ranking import compare, rank_key
from .store import SessionError, change, config, dumps, event, read, record


def freeze_parent(value, task_hash):
    keys = {"source_run", "assessment_id", "facts_sha256", "canonical_artifact_sha256"}
    if not isinstance(value, dict) or set(value) != keys:
        raise SessionError("ONLINE_PARENT_FIELDS")
    aid = value["assessment_id"]
    if not isinstance(aid, str) or len(aid) != 32 or any(c not in "0123456789abcdef" for c in aid):
        raise SessionError("ONLINE_PARENT_ASSESSMENT_ID")
    source = Path(value["source_run"]).resolve()
    # Read-only SQLite: missing sources must not create an empty database.
    db = sqlite3.connect((source / "session.sqlite").as_uri() + "?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    try:
        conf, root = config(db), record(db)
        if (conf["task_contract_hash"] != task_hash or not root["seal"]
                or root["state"] not in ("SEARCH_SEALED", "COMPLETED", "STOPPED")
                or db.execute("SELECT 1 FROM tasks WHERE state IN ('STARTING','RUNNING')").fetchone()):
            raise SessionError("ONLINE_PARENT_SOURCE_NOT_SEALED_OR_TASK_MISMATCH")
        item = db.execute("SELECT * FROM assessments WHERE id=?", (aid,)).fetchone()
        if not item or item["mode"] != "online" or item["state"] != "COMPLETE":
            raise SessionError("ONLINE_PARENT_NOT_COMPLETE_ONLINE")
        ref = json.loads(item["facts"])
        if ref != {"directory": f"assessments/{aid}", "facts_sha256": value["facts_sha256"], "assessment_id": aid}:
            raise SessionError("ONLINE_PARENT_REFERENCE_MISMATCH")
        folder = source / ref["directory"]
        if source not in folder.resolve().parents:
            raise SessionError("ONLINE_PARENT_PATH_ESCAPE")
        facts = reload_facts(folder, task_hash)
        if (digest(canonical(facts)) != value["facts_sha256"] or facts["mode"] != "online"
                or facts["evaluation_identity"]["canonical_artifact_sha256"] != value["canonical_artifact_sha256"]
                or rank_key(facts) is None):
            raise SessionError("ONLINE_PARENT_FACTS_MISMATCH")
        body = (folder / facts["artifact_ref"] / "prescription.json").read_bytes()
        prescription = json.loads(body)
        if digest(canonical(prescription)) != value["canonical_artifact_sha256"]:
            raise SessionError("ONLINE_PARENT_ARTIFACT_MISMATCH")
        # Freeze the artifact, not historical scores or audit observations.
        return {**value, "source_run": str(source), "source_config_hash": root["config_hash"],
                "prescription": prescription}
    finally:
        db.close()


def parent_path(run):
    return Path(run).resolve() / "imports/online_parent/prescription.json"


def accepted_receipt(db):
    row = db.execute("SELECT body FROM events WHERE kind='online_parent_assessed' ORDER BY sequence LIMIT 1").fetchone()
    return json.loads(row[0]) if row else None


def accept_parent(db, run, ref, facts):
    conf = config(db)
    seed = conf["online_parent"]
    read(run, {"path": "imports/online_parent/prescription.json", "sha256": seed["canonical_artifact_sha256"]})
    if (facts["mode"] != "online" or rank_key(facts) is None
            or facts["evaluation_identity"]["canonical_artifact_sha256"] != seed["canonical_artifact_sha256"]):
        raise SessionError("ONLINE_PARENT_REASSESSMENT_INVALID")
    previous = accepted_receipt(db)
    if previous:
        if previous["assessment_ref"] != ref:
            raise SessionError("ONLINE_PARENT_REASSESSMENT_CONFLICT")
        return previous
    root = record(db)
    if root["seal"]:
        raise SessionError("ONLINE_PARENT_ACCEPT_AFTER_SEAL")
    incumbent = json.loads(root["incumbent"]) if root["incumbent"] else None
    old = reload_facts(Path(run) / incumbent["directory"], conf["task_contract_hash"]) if incumbent else None
    comparison = compare(old, facts)
    if comparison["decision"] == "accept":
        change(db, incumbent=dumps(ref))
    receipt = {"assessment_ref": ref, "source_assessment_id": seed["assessment_id"],
               "source_run": seed["source_run"], "comparison": comparison,
               "origin": "inherited_online_parent", "new_discovery": False}
    event(db, "online_parent_assessed", receipt)
    return receipt
