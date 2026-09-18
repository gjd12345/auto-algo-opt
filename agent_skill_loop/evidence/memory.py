"""Read-only Memory consumption projection from durable Session evidence.

"Compiled" and "gateway attempted" are deliberately distinct.  Neither
state asserts that a provider understood the memory or improved a candidate.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_skill_loop import session_runtime as db


SCHEMA_VERSION = "algorithm-optimization-memory-consumption/v1"


def _verified(root: Path, ref: str, digest: str | None = None) -> tuple[bytes, str]:
    path = (root / ref).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("memory_evidence_reference_outside_run")
    body = path.read_bytes()
    value = db._sha256(body)
    if digest is not None and value != digest:
        raise ValueError("memory_evidence_hash_mismatch")
    return body, value


def project_memory_consumption(root: Path, con: Any, run: Any, rd: Any, task: Any) -> dict[str, Any]:
    searches = [dict(x) for x in con.execute(
        "SELECT * FROM memory_searches WHERE run_id=? AND round_id=? ORDER BY search_id", (run["run_id"],rd["round_id"]))]
    reads = [dict(x) for x in con.execute(
        "SELECT * FROM memory_reads WHERE run_id=? AND round_id=? ORDER BY read_id", (run["run_id"],rd["round_id"]))]
    writes = [dict(x) for x in con.execute(
        "SELECT * FROM memory_writes WHERE run_id=? AND round_id=? ORDER BY write_id", (run["run_id"],rd["round_id"]))]
    manifest = {}
    context = None
    context_payload = None
    if rd["context_manifest_ref"]:
        manifest_bytes, manifest_sha = _verified(root, rd["context_manifest_ref"])
        manifest = json.loads(manifest_bytes)
        if not isinstance(manifest, dict):
            raise ValueError("memory_context_manifest_invalid")
        context_bytes, context_hash = _verified(root, rd["round_context_ref"], rd["round_context_sha256"])
        context = context_bytes.decode("utf-8")
        if context_hash != manifest.get("context_sha256"):
            raise ValueError("memory_context_manifest_hash_mismatch")
        context_payload = json.loads(context.split("\n", 1)[1])
        injected_refs = {item.get("reference"): item for item in manifest.get("injected", [])}
        if (set(injected_refs) != {item.get("reference") for item in context_payload.get("memory", [])}
                or any(db._sha256(item.get("body", "")) != injected_refs[item.get("reference")].get("injected_sha256")
                       or item.get("body_sha256") != injected_refs[item.get("reference")].get("body_sha256")
                       for item in context_payload.get("memory", []))):
            raise ValueError("memory_context_excerpts_mismatch")
        if set(manifest.get("adopted_refs") or []) != set(injected_refs) | set(manifest.get("omitted_refs") or []):
            raise ValueError("memory_context_selection_mismatch")
    else:
        manifest_sha = None
    request_receipts = []
    if task is not None:
        from agent_skill_loop.session_supervisor import task_output
        output = task_output(root, con, task)
        for request in con.execute("SELECT * FROM requests WHERE task_id=? AND purpose IN ('eoh_generation','eoh_repair') ORDER BY sequence", (task["task_id"],)):
            ref = (output / "results/request_inputs" / f"request_{request['sequence']}.json").relative_to(root).as_posix()
            entry = {"request_id": request["request_id"], "sequence": request["sequence"],
                     "purpose": request["purpose"], "request_state": request["state"],
                     "input_ref": None, "input_sha256": None,
                     "context_status": "not_sent", "memory": []}
            input_path = root / ref
            if input_path.is_file():
                data, digest = _verified(root, ref)
                payload = json.loads(data)
                messages = payload.get("messages") if isinstance(payload, dict) else None
                if not isinstance(messages, list):
                    raise ValueError("memory_request_payload_invalid")
                prompt = "\n".join(item.get("content", "") for item in messages if isinstance(item, dict) and isinstance(item.get("content"), str))
                entry.update(input_ref=ref, input_sha256=digest)
                if request["state"] != "reserved":
                    if context is not None and prompt.count(context) == 1:
                        # The entire canonical context, including its parsed
                        # excerpts, occurs once in the final gateway payload.
                        entry["context_status"] = "gateway_attempt_exact_context"
                        entry["memory"] = [{"reference":x["reference"],"body_sha256":x["body_sha256"],
                                            "injected_sha256":x["injected_sha256"],"status":"gateway_attempt"}
                                           for x in manifest.get("injected", [])]
                    else:
                        entry["context_status"] = "missing_or_modified_context"
                        entry["memory"] = [{"reference":x["reference"],"status":"omitted_at_gateway"}
                                           for x in manifest.get("injected", [])]
            elif request["state"] != "reserved":
                raise ValueError("memory_request_input_missing")
            request_receipts.append(entry)
    return {
        "schema_version": SCHEMA_VERSION, "run_id": run["run_id"], "round_id": rd["round_id"],
        "memory_enabled": bool(run["memory_enabled"]),
        "search_status": "disabled" if not run["memory_enabled"] else "not_searched" if not searches else searches[-1]["status"],
        "searched": [{"search_id":x["search_id"], "query_sha256":x["query_sha256"],
                      "filters":json.loads(x["filters_json"]), "results":json.loads(x["result_refs_json"]),
                      "status":x["status"], "error_code":x["error_code"]} for x in searches],
        "read": [{"read_id":x["read_id"],"reference":x["reference"],"body_sha256":x["body_sha256"] or None,
                  "offset_chars":x["offset_chars"],"returned_chars":x["returned_chars"],"total_chars":x["total_chars"],
                  "status":x["status"],"error_code":x["error_code"]} for x in reads],
        "selected": list(manifest.get("adopted_refs") or []),
        "compiled": [{**item, "version":next((part.get("version") for part in (context_payload or {}).get("memory", [])
                                                  if part.get("reference") == item["reference"]), None),
                      "status":"compiled_into_context"} for item in manifest.get("injected", [])],
        "omitted": [{"reference":x,"reason":"context_size_limit"} for x in manifest.get("omitted_refs", [])],
        "context_manifest_ref": rd["context_manifest_ref"], "context_manifest_sha256": manifest_sha,
        "gateway_requests": request_receipts,
        "publication": {"status":rd["memory_commit_status"] or "not_decided",
                        "writes":[{"operation_id":x["operation_id"],"kind":x["kind"],"status":x["status"],
                                   "reference":x["reference"],"error_code":x["error_code"],"proposal_ref":x["proposal_ref"]} for x in writes]},
    }
