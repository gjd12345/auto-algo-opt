"""Import completed durable assessments without repeating an external effect."""

import json
from pathlib import Path

from optics_backend.artifacts import canonical, digest, strict
from optics_backend.offline import reload_facts
from optics_backend.ranking import compare, rank_key
from .store import SessionError, change, config, dumps, event, evidence, read, record


def reconcile_completed(db, run):
    run = Path(run).resolve()
    conf = config(db)
    recovered = []
    # Include COMPLETE rows: a crash can follow the assessment commit but precede
    # candidate/incumbent acceptance. Both windows use the same idempotent path.
    for item in db.execute("SELECT * FROM assessments ORDER BY rowid").fetchall():
        directory = run / "assessments" / item["id"]
        terminal = directory / "terminal.json"
        if not terminal.exists():
            continue
        if strict(terminal.read_bytes()).get("status") != "complete":
            continue
        facts = reload_facts(directory, conf["task_contract_hash"])
        request = strict((directory / "execution_request.json").read_bytes())
        identity = facts["evaluation_identity"]
        source = Path(item["artifact"]).resolve()
        if (Path(request["candidate"]).resolve() != source or request["mode"] != item["mode"]
                or facts["mode"] != item["mode"] or request["task_contract_hash"] != conf["task_contract_hash"]
                or Path(request["bundle"]).resolve() != Path(conf["bundle"]).resolve()
                or any(identity[k] != conf[k] for k in ("assessment_adapter_hash", "environment_manifest_hash"))
                or digest(canonical(strict(source.read_bytes()))) != identity["canonical_artifact_sha256"]):
            raise SessionError("RECOVERY_ASSESSMENT_IDENTITY_MISMATCH")
        effects = db.execute("SELECT * FROM effects WHERE assessment=? ORDER BY id", (item["id"],)).fetchall()
        expected = 1 if item["mode"] == "online" else 4
        if len(effects) != expected:
            raise SessionError("RECOVERY_EFFECT_COUNT_MISMATCH")
        for index, effect in enumerate(effects):
            completed = strict((directory / "profiles" / f"{index:04d}.completed.json").read_bytes(), 20_000_000)
            detail = json.loads(effect["detail"])
            if (effect["id"] != f"{item['id']}-{index}" or effect["state"] != "COMPLETE"
                    or detail.get("profile_id") != completed["profile_id"]
                    or detail.get("profile_spec_hash") != completed["profile_spec_hash"]
                    or detail.get("result_sha256") != digest(canonical(completed["result"]))):
                raise SessionError("RECOVERY_EFFECT_EVIDENCE_MISMATCH")
        ref = {"directory": directory.relative_to(run).as_posix(),
               "facts_sha256": digest(canonical(facts)), "assessment_id": item["id"]}
        if item["facts"] and json.loads(item["facts"]) != ref:
            raise SessionError("RECOVERY_FACTS_CONFLICT")
        if item["state"] != "COMPLETE":
            if item["state"] not in ("RESERVED", "INCOMPLETE"):
                raise SessionError("RECOVERY_TERMINAL_CONFLICT")
            sequence = db.execute("SELECT COALESCE(MAX(sequence),0)+1 FROM assessments").fetchone()[0]
            db.execute("UPDATE assessments SET state='COMPLETE',facts=?,sequence=? WHERE id=?", (dumps(ref), sequence, item["id"]))
            event(db, "assessment_recovered", {"assessment_id": item["id"], "facts": ref})
            recovered.append(item["id"])
        if item["mode"] != "online":
            continue
        root = record(db)
        if source == (Path(conf["bundle"]) / "assets/initial_prescription.json").resolve():
            if not root["baseline"]:
                change(db, baseline=dumps(ref), incumbent=dumps(ref) if rank_key(facts) is not None else root["incumbent"])
            continue
        cid = source.parent.name
        candidate = db.execute("SELECT * FROM candidates WHERE id=?", (cid,)).fetchone()
        if source != run / "candidates" / cid / "prescription.json" or not candidate or candidate["round"] != item["round"]:
            raise SessionError("RECOVERY_CANDIDATE_SOURCE_MISMATCH")
        if candidate["state"] == "COMPLETE":
            if json.loads(candidate["detail"]).get("assessment_ref") != ref:
                raise SessionError("RECOVERY_CANDIDATE_CONFLICT")
            continue
        if root["seal"]:
            raise SessionError("RECOVERY_AFTER_SEAL_CONFLICT")
        original_request = strict((source.parent / "request.json").read_bytes())
        if json.loads(candidate["detail"]).get("prompt_sha256") != digest(canonical(original_request)):
            raise SessionError("RECOVERY_REQUEST_HASH_MISMATCH")
        parent_hash = digest(canonical(original_request["context"]["parent_prescription"]))
        parent, previous = None, None
        for old in db.execute("SELECT facts FROM assessments WHERE mode='online' AND state='COMPLETE' AND id!=? ORDER BY sequence", (item["id"],)):
            old_ref = json.loads(old[0])
            old_facts = reload_facts(run / old_ref["directory"], conf["task_contract_hash"])
            if old_facts["evaluation_identity"]["canonical_artifact_sha256"] == parent_hash:
                parent, previous = old_ref, old_facts
                break
        if parent is None:
            raise SessionError("RECOVERY_PARENT_MISSING")
        comparison = compare(previous, facts)
        provider = strict((source.parent / "provider.json").read_bytes())
        result = {"candidate_id": cid, "parent_ref": parent, "provider": provider,
                  "request_ref": {"path": f"candidates/{cid}/request.json", "sha256": digest(canonical(original_request))},
                  "assessment_ref": ref, "ranking_key": facts["ranking_key"], "online_feasible": facts["online_feasible"],
                  "comparison": comparison, "recovered": True}
        incumbent = json.loads(root["incumbent"]) if root["incumbent"] else None
        incumbent_facts = reload_facts(run / incumbent["directory"], conf["task_contract_hash"]) if incumbent else None
        if compare(incumbent_facts, facts)["decision"] == "accept":
            change(db, incumbent=dumps(ref))
        db.execute("UPDATE candidates SET state='COMPLETE',detail=? WHERE id=?", (dumps(result), cid))
        event(db, "candidate_recovered", result)
    return recovered


def interrupted_round(db, run, round_id):
    from .ledger import counts
    row = db.execute("SELECT * FROM rounds WHERE id=?", (round_id,)).fetchone()
    if not row or row["facts"] or not row["plan"]:
        return
    root, conf = record(db), config(db)
    candidates = []
    for c in db.execute("SELECT * FROM candidates WHERE round=? ORDER BY rowid", (round_id,)):
        detail = json.loads(c["detail"])
        if c["state"] == "RESERVED":
            detail = {"candidate_id": c["id"], "error": "WORKER_INTERRUPTED", "state": "UNKNOWN"}
        candidates.append(detail)
    before = None  # Not reconstructible in every pre-existing run; never invent it.
    if candidates:
        before = candidates[0].get("parent_ref")
    facts = {"round_id": round_id, "plan_ref": json.loads(row["plan"]), "incumbent_before": before,
             "incumbent_after": json.loads(root["incumbent"]) if root["incumbent"] else None,
             "candidates": candidates, "counts": counts(db), "stop_reason": "WORKER_INTERRUPTED",
             "controller_contract_hash": conf["controller_contract_hash"]}
    ref = evidence(run, f"rounds/{round_id:04d}/recovered_online_facts.json", facts)
    db.execute("UPDATE rounds SET state='EVALUATE_SKIPPED',facts=? WHERE id=?", (dumps(ref), round_id))
