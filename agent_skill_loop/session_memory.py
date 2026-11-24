"""Recoverable Memory publication, separate from accepting Agent evaluation."""
import ast
import json
import math
import re
from pathlib import Path

from agent_skill_loop import session_runtime as db
from agent_skill_loop.memory import open_memory_backend
from agent_skill_loop.memory.api import MemoryPublicationPending, solution_execution_ast_sha256
from agent_skill_loop.problems.base import get_problem
from agent_skill_loop.skill_store import load_skill
from agent_skill_loop.session_contracts import MemoryAction, strict_json_object


_TEMPLATE_LABEL = re.compile(
    r"^(?:\*\*|__)?(?:why|how to apply|execution|执行流|reusable experience|root cause|"
    r"applicability(?: scope)?|limitations|guardrail (?:&|and) false[- ]positive boundary)"
    r"(?=\s*[:：]|\*\*|__|$)(?:\*\*|__)?\s*[:：]?(?:\*\*|__)?\s*", re.IGNORECASE,
)


def _body_claim_text(body):
    """Ignore template labels and Markdown presentation, retaining claim text."""
    lines = []
    in_fence = False
    for line in body.splitlines():
        if re.match(r"^\s*(?:```|~~~)", line):
            in_fence = not in_fence
        if not in_fence and not re.match(r"^\s*(?:```|~~~)", line):
            line = re.sub(r"^\s*(?:#{1,6}|[-+*])\s+", "", line).strip()
            line = _TEMPLATE_LABEL.sub("", line)
            if line:
                lines.append(line)
        else:
            # Preserve fenced snippets and indentation as part of the claim.
            lines.append(line)
    return tuple(lines)


def _verified_json(root, ref, sha256):
    if not isinstance(ref, str) or not isinstance(sha256, str):
        raise ValueError("memory_evidence_binding_missing")
    path = (root / ref).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("memory_evidence_reference_invalid")
    text = path.read_text(encoding="utf-8")
    if db._sha256(text) != sha256:
        raise ValueError("memory_evidence_hash_mismatch")
    return strict_json_object(text)


def _candidate_evidence(facts, reference):
    if reference is None or reference not in facts.get("evidence_refs", []):
        return None
    candidate = next((candidate for candidate in facts.get("candidates", [])
                      if f"evaluation:{candidate.get('evaluation_id')}" == reference), None)
    if candidate is None:
        return None
    return {key: candidate.get(key) for key in ("evaluation_id", "code_sha256", "canonical_ast_sha256", "valid",
                                                "objective", "instance_objectives", "metrics", "error_code")}


def validate_revision(root, binding, memory, facts):
    old = MemoryAction.from_dict(
        _verified_json(root, binding["old_proposal_ref"], binding["old_proposal_sha256"]), enabled=True,
    )
    identity = ("kind", "name", "project", "scene", "memory_based_on")
    if any(getattr(old, key) != getattr(memory, key) for key in identity) or memory.memory_based_on != binding["card_head"]:
        raise ValueError("memory_revision_identity_mismatch")
    fields = ("description", "source_skill_ref", "evidence_ref", "applicability_scope",
              "validity_status", "evidence_tier", "code_anchor")
    if (_body_claim_text(old.body) == _body_claim_text(memory.body)
            and all(getattr(old, key) == getattr(memory, key) for key in fields)):
        return
    if binding["old_evaluation_facts_sha256"] == binding["evaluation_facts_sha256"]:
        raise ValueError("memory_revision_new_verified_evidence_required")
    old_facts = _verified_json(root, binding["old_evaluation_facts_ref"], binding["old_evaluation_facts_sha256"])
    evidence = _candidate_evidence(facts, memory.evidence_ref)
    if evidence is None or evidence == _candidate_evidence(old_facts, memory.evidence_ref):
        raise ValueError("memory_revision_new_verified_evidence_required")


def commit_pending(root, operation_id):
    from agent_skill_loop.file_lock import exclusive_file_lock
    try:
        with exclusive_file_lock(root/"locks"/(db._sha256(operation_id)+".memory.lock"), busy="memory_commit_busy"):
            _commit_pending(root, operation_id)
    except ValueError as exc:
        if str(exc)!="memory_commit_busy": raise
        # Another caller owns this exact proposal. Return its current receipt;
        # retrying this operation later recovers a crashed owner without replaying
        # any model/solver work.


def _commit_pending(root, operation_id):
    con=db._connect(root/"session.sqlite3")
    try:
        # Read a consistent control snapshot, then release the SQLite writer.
        with db._transaction(con):
            proposal=con.execute("SELECT * FROM memory_writes WHERE operation_id=? AND status IN ('proposed','accepted')",(operation_id,)).fetchone()
            if proposal is None: return
            row=db._require_run(con,action="memory-commit",run_id=None)
            rd=con.execute("SELECT * FROM rounds WHERE run_id=? AND round_id=?",(row["run_id"],proposal["round_id"])).fetchone()
        db._verify_files(root,row,action="memory-commit")
        status,error,reference="rejected",None,None
        try:
            receipt = json.loads(con.execute("SELECT receipt_json FROM operations WHERE operation_id=?", (operation_id,)).fetchone()[0])
            binding = receipt["result"]
            submitted = _verified_json(root, rd["submitted_evaluation_ref"], rd["submitted_evaluation_sha256"])
            facts = _verified_json(root, rd["evaluation_facts_ref"], rd["evaluation_facts_sha256"])
            if "proposal_sha256" in binding:
                if (binding["proposal_ref"] != proposal["proposal_ref"]
                        or binding["evaluation_facts_ref"] != rd["evaluation_facts_ref"]
                        or binding["evaluation_facts_sha256"] != rd["evaluation_facts_sha256"]):
                    raise ValueError("memory_proposal_binding_mismatch")
                raw = _verified_json(root, binding["proposal_ref"], binding["proposal_sha256"])
            else:
                raw = strict_json_object((root / proposal["proposal_ref"]).read_text(encoding="utf-8"))
            expected = MemoryAction.from_dict(submitted.get("memory_action"), enabled=bool(row["memory_enabled"]))
            if receipt["action"] == "memory-revise":
                expected = MemoryAction.from_dict(raw, enabled=bool(row["memory_enabled"]))
                if binding["new_proposal_sha256"] != binding["proposal_sha256"]:
                    raise ValueError("memory_revision_hash_mismatch")
                validate_revision(root, binding, expected, facts)
            if raw!=expected.as_dict():
                raise ValueError("memory_proposal_identity_mismatch")
            spec=get_problem(row["problem"])
            if raw["project"]!=row["problem"] or raw["scene"]!=spec.entrypoint: raise ValueError("memory_scene_identity_mismatch")
            source_skill_ref=raw.get("source_skill_ref")
            memory_based_on=raw.get("memory_based_on")
            if "card_head" in binding and binding["card_head"] != memory_based_on:
                raise ValueError("memory_card_head_binding_mismatch")
            provenance={
                "evaluation_facts_ref": rd["evaluation_facts_ref"],
                "evaluation_facts_sha256": rd["evaluation_facts_sha256"],
                "round_id": str(rd["round_id"]),
                "source_run_id": row["run_id"],
                "source_session_root": str(root.resolve()),
            }
            if receipt["action"] == "memory-revise":
                provenance.update({key: binding[key] for key in ("old_proposal_sha256", "new_proposal_sha256")})
                if memory_based_on is not None:
                    provenance["card_head"] = memory_based_on
            if raw.get("evidence_ref"):
                provenance["evidence_ref"]=raw["evidence_ref"]
            if raw["kind"]=="solution":
                if not source_skill_ref or not raw.get("evidence_ref"):
                    raise ValueError("solution_source_and_evidence_required")
                if row["solution_threshold"] is None: raise ValueError("solution_threshold_required")
                ref=facts.get("best_generated_ref")
                if not ref or source_skill_ref!=ref: raise ValueError("solution_candidate_reference_mismatch")
                if raw.get("evidence_ref") not in facts["evidence_refs"]: raise ValueError("solution_evidence_reference_mismatch")
                skill_path = (root / ref).resolve()
                if not skill_path.is_relative_to(root.resolve()):
                    raise ValueError("solution_candidate_reference_mismatch")
                skill = load_skill(skill_path)
                matches=[x for x in facts["candidates"] if f"evaluation:{x['evaluation_id']}"==raw["evidence_ref"] and x["code_sha256"]==skill.code_sha256 and x["objective"]==skill.mean_objective and x["valid"] and x["origin"] in {"generated","generated_repair"}]
                if (not matches or not skill.valid or skill.problem != row["problem"]
                        or skill.suite_hash != row["suite_hash"] or skill.evaluator_hash != row["evaluator_hash"]):
                    raise ValueError("solution_evidence_identity_mismatch")
                baseline = (facts.get("baseline") or {}).get("objective")
                if type(baseline) not in (int, float):
                    raise ValueError("solution_baseline_objective_required")
                improvement = spec.solution_improvement(baseline, skill.mean_objective)
                if improvement is None or not math.isfinite(improvement) or improvement <= max(0.0, row["solution_threshold"]):
                    raise ValueError("solution_threshold_not_met")
                provenance.update({
                    "source_skill_ref": source_skill_ref,
                    "source_evaluation_id": matches[0]["evaluation_id"],
                    "candidate_code_sha256": skill.code_sha256,
                    "suite_hash": skill.suite_hash,
                    "evaluator_hash": skill.evaluator_hash,
                })
                canonical_ast_hash = db._sha256(ast.unparse(ast.parse(skill.code)))
                anchor = expected.code_anchor or {}
                if (matches[0].get("canonical_ast_sha256", canonical_ast_hash) != canonical_ast_hash
                        or anchor.get("canonical_ast_sha256") != canonical_ast_hash
                        or anchor.get("code_sha256", skill.code_sha256) != skill.code_sha256
                        or solution_execution_ast_sha256(expected.body) != canonical_ast_hash):
                    raise ValueError("solution_canonical_ast_hash_mismatch")
                provenance["canonical_ast_sha256"] = canonical_ast_hash
                if skill.parent_version_id is not None:
                    provenance["parent_version_id"] = skill.parent_version_id
                provenance["interface_id"] = spec.entrypoint
            elif raw.get("evidence_ref") and raw["evidence_ref"] not in facts["evidence_refs"]:
                raise ValueError("memory_evidence_reference_mismatch")
            with db._transaction(con):
                _record_status(con,proposal,operation_id,"accepted",None,None)
            status="failed"
            backend=open_memory_backend(Path(row["memory_store"]),policy_id=row["memory_policy_id"])
            written=backend.write(expected.to_entry(), based_on=memory_based_on, provenance=provenance,
                                  operation_key=f"{row['run_id']}:{operation_id}", format_version=3)
            reference=written["reference"]
            status="published"
        except MemoryPublicationPending:
            # The accepted operation owns a recoverable publication. Its next
            # replay settles the existing version before the round can finish.
            return
        except (ValueError, OSError, KeyError, TypeError, SyntaxError, RecursionError) as exc:
            error=str(exc)[:256]
        with db._transaction(con):
            _record_status(con,proposal,operation_id,status,error,reference)
    finally: con.close()


def _record_status(con, proposal, operation_id, status, error, reference):
    # Concurrent stop may advance the version while filesystem work runs.
    row=db._require_run(con,action="memory-commit",run_id=None)
    version=row["state_version"]+1
    con.execute("UPDATE memory_writes SET status=?,error_code=?,reference=? WHERE write_id=?",(status,error,reference,proposal["write_id"]))
    con.execute("UPDATE rounds SET memory_commit_status=?,updated_state_version=? WHERE run_id=? AND round_id=?",(status,version,row["run_id"],proposal["round_id"]))
    con.execute("UPDATE runs SET state_version=? WHERE run_id=?",(version,row["run_id"]))
    row=db._require_run(con,action="memory-commit",run_id=None)
    rd=con.execute("SELECT * FROM rounds WHERE run_id=? AND round_id=?",(row["run_id"],proposal["round_id"])).fetchone()
    previous=json.loads(con.execute("SELECT receipt_json FROM operations WHERE operation_id=?",(operation_id,)).fetchone()[0])
    result=previous["result"]
    result["memory"]={"status":status,"error_code":error,"reference":reference}
    receipt=db._envelope(con,row,rd,action=previous["action"],operation_id=operation_id,result=result)
    con.execute("UPDATE operations SET receipt_json=?,result_state_version=? WHERE operation_id=?",(db._json(receipt),version,operation_id))
    db._queue_audit(con,row["run_id"],version,[("state_transition",{"memory_status":status,"operation_id":operation_id,"reference":reference})])
