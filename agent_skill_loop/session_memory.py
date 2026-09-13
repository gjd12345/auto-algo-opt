"""Recoverable Memory publication, separate from accepting Agent evaluation."""
import json
from pathlib import Path

from agent_skill_loop import session_runtime as db
from agent_skill_loop.memory.api import MemoryAPI, MemoryEntry
from agent_skill_loop.problems.base import get_problem
from agent_skill_loop.skill_store import load_skill
from agent_skill_loop.contracts_3plus1 import MemoryAction, strict_json_object


def commit_pending(root, operation_id):
    con=db._connect(root/"session.sqlite3")
    try:
        with db._transaction(con):
            proposal=con.execute("SELECT * FROM memory_writes WHERE operation_id=? AND status IN ('proposed','accepted')",(operation_id,)).fetchone()
            if proposal is None: return
            row=db._require_run(con,action="memory-commit",run_id=None)
            rd=con.execute("SELECT * FROM rounds WHERE run_id=? AND round_id=?",(row["run_id"],proposal["round_id"])).fetchone()
            status,error,reference="rejected",None,None
            try:
                raw=json.loads((root/proposal["proposal_ref"]).read_text(encoding="utf-8"))
                submitted=(root/rd["submitted_evaluation_ref"]).read_text(encoding="utf-8")
                if db._sha256(submitted)!=rd["submitted_evaluation_sha256"]:
                    raise ValueError("evaluation_submission_hash_mismatch")
                expected=MemoryAction.from_dict(strict_json_object(submitted).get("memory_action"),enabled=bool(row["memory_enabled"]))
                if raw!=expected.as_dict():
                    raise ValueError("memory_proposal_identity_mismatch")
                spec=get_problem(row["problem"])
                if raw["project"]!=row["problem"] or raw["scene"]!=spec.entrypoint: raise ValueError("memory_scene_identity_mismatch")
                facts_text=(root/rd["evaluation_facts_ref"]).read_text(encoding="utf-8")
                if db._sha256(facts_text)!=rd["evaluation_facts_sha256"]: raise ValueError("facts_hash_mismatch")
                facts=json.loads(facts_text)
                based_on=raw.get("based_on")
                if raw["kind"]=="solution":
                    if row["solution_threshold"] is None: raise ValueError("solution_threshold_required")
                    ref=facts.get("best_generated_ref")
                    if not ref or based_on!=ref: raise ValueError("solution_candidate_reference_mismatch")
                    if raw.get("evidence_ref") not in facts["evidence_refs"]: raise ValueError("solution_evidence_reference_mismatch")
                    skill=load_skill(root/ref)
                    matches=[x for x in facts["candidates"] if f"evaluation:{x['evaluation_id']}"==raw["evidence_ref"] and x["code_sha256"]==skill.code_sha256 and x["objective"]==skill.mean_objective and x["valid"] and x["origin"] in {"generated","generated_repair"}]
                    if not matches or skill.suite_hash!=row["suite_hash"] or skill.evaluator_hash!=row["evaluator_hash"]: raise ValueError("solution_evidence_identity_mismatch")
                    baseline=facts.get("baseline") or {}
                    improvement=spec.solution_improvement(baseline.get("objective",0),skill.mean_objective)
                    if improvement is None or improvement<=0 or improvement<row["solution_threshold"]: raise ValueError("solution_threshold_not_met")
                    based_on=None  # skill provenance is not a Markdown same-entry CAS
                elif raw.get("evidence_ref") and raw["evidence_ref"] not in facts["evidence_refs"]:
                    raise ValueError("memory_evidence_reference_mismatch")
                con.execute("UPDATE memory_writes SET status='accepted' WHERE write_id=?",(proposal["write_id"],))
                status="failed"
                entry=MemoryEntry(name=raw["name"],description=raw["description"],type=raw["kind"],project=raw["project"],scene=raw["scene"],body=raw["body"])
                written=MemoryAPI(Path(row["memory_store"])).write(entry,based_on=based_on,operation_key=f"{row['run_id']}:{operation_id}")
                reference=written["reference"]
                status="published"
            except (ValueError,OSError,KeyError,TypeError) as exc:
                error=str(exc)[:256]
            con.execute("UPDATE memory_writes SET status=?,error_code=?,reference=? WHERE write_id=?",(status,error,reference,proposal["write_id"]))
            version=row["state_version"]+1
            con.execute("UPDATE rounds SET memory_commit_status=?,updated_state_version=? WHERE run_id=? AND round_id=?",(status,version,row["run_id"],rd["round_id"]))
            con.execute("UPDATE runs SET state_version=? WHERE run_id=?",(version,row["run_id"]))
            receipt=json.loads(con.execute("SELECT receipt_json FROM operations WHERE operation_id=?",(operation_id,)).fetchone()[0])
            receipt["state_version"]=version
            receipt["result"]["memory"]={"status":status,"error_code":error,"reference":reference}
            con.execute("UPDATE operations SET receipt_json=?,result_state_version=? WHERE operation_id=?",(db._json(receipt),version,operation_id))
            db._queue_audit(con,row["run_id"],version,[("state_transition",{"memory_status":status,"operation_id":operation_id,"reference":reference})])
    finally: con.close()
