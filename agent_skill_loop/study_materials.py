"""Deterministic outer-controller material for the island605 content study.

Historical material is delivered to the controller only. It is never added to
the EoH request context by this module.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from agent_skill_loop import session_runtime as db
from agent_skill_loop.memory.backend import open_memory_backend
from agent_skill_loop.session_actions import complete_reads


STUDY_ID = "island605_bp_memory_content_control_v1"
POLICY = "outer_controller_history_v1"
MAX_BODY_CHARS = 1200


def _hash(value: bytes | str) -> str:
    return hashlib.sha256(value.encode("utf-8") if isinstance(value, str) else value).hexdigest()


def _round(con, run_id: str, round_id: int):
    return con.execute("SELECT * FROM rounds WHERE run_id=? AND round_id=?", (run_id, round_id)).fetchone()


@contextmanager
def _session(run: Path, round_id: int, expected_arm: str | None = None):
    root = Path(run).resolve()
    config = json.loads((root / "config_frozen.json").read_text(encoding="utf-8"))
    extra = config["experiment_manifest"]["document"]["extra"]
    arm = extra.get("study_arm")
    if extra.get("study_id") != STUDY_ID or extra.get("controller_material_policy") != POLICY:
        raise ValueError("study_material_contract_mismatch")
    if arm not in {"R", "F", "M"} or (expected_arm and arm != expected_arm):
        raise ValueError("study_material_arm_mismatch")
    con = db._connect(root / "session.sqlite3")
    try:
        row = db._require_run(con, action="study-material", run_id=None)
        rd = db._round(con, row)
        if rd["round_id"] != round_id or rd["state"] != "WAITING_FOR_PLAN":
            raise ValueError("study_material_requires_waiting_for_plan")
        yield root, con, row, rd, arm
    finally:
        con.close()


def _history_note(root: Path, con, run_id: str, round_id: int) -> tuple[dict[str, Any], dict[str, Any]] | None:
    rd = _round(con, run_id, round_id)
    if rd is None or not rd["submitted_evaluation_ref"] or not rd["submitted_evaluation_sha256"]:
        return None
    ref = rd["submitted_evaluation_ref"]
    path = root / ref
    if not path.is_file() or _hash(path.read_bytes()) != rd["submitted_evaluation_sha256"]:
        raise ValueError("historical_note_identity_mismatch")
    note = json.loads(path.read_text(encoding="utf-8"))
    return note, {"round_id": round_id, "ref": ref, "sha256": rd["submitted_evaluation_sha256"]}


def _fact_material(root: Path, con, run_id: str, current_round: int) -> tuple[str, dict[str, Any] | None]:
    for earlier in range(current_round - 1, 0, -1):
        found = _history_note(root, con, run_id, earlier)
        if found is None:
            continue
        note, source = found
        selected: list[dict[str, Any]] = []
        for observation in note.get("observations", []):
            if not isinstance(observation, dict):
                continue
            claim = observation.get("claim")
            refs = observation.get("evidence_refs")
            if not isinstance(claim, str) or not isinstance(refs, list) or not refs:
                continue
            candidate = selected + [{"claim": claim, "evidence_refs": refs}]
            text = json.dumps({"observations": candidate}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            if len(text) <= MAX_BODY_CHARS:
                selected = candidate
        if selected:
            body = json.dumps({"observations": selected}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            return body, source
    return "", None


def _published_reference(root: Path, con, run_id: str, current_round: int) -> tuple[str, dict[str, Any]] | None:
    for earlier in range(current_round - 1, 0, -1):
        ref = f"rounds/round_{earlier:04d}/memory_consumption.json"
        path = root / ref
        if not path.is_file():
            continue
        raw = path.read_bytes()
        report = json.loads(raw)
        if report.get("run_id") != run_id or report.get("round_id") != earlier:
            raise ValueError("historical_memory_consumption_identity_mismatch")
        writes = report.get("publication", {}).get("writes", [])
        published = sorted({w["reference"] for w in writes if w.get("status") == "published" and w.get("reference")})
        ledger = {
            item[0] for item in con.execute(
                "SELECT reference FROM memory_writes WHERE run_id=? AND round_id=? AND status='published'",
                (run_id, earlier),
            ) if item[0]
        }
        if set(published) != ledger:
            raise ValueError("historical_memory_publication_ledger_mismatch")
        if published:
            return published[0], {"round_id": earlier, "ref": ref, "sha256": _hash(raw)}
    return None


def select_memory_reference(run: Path, round_id: int) -> dict[str, Any]:
    with _session(run, round_id, "M") as (root, con, row, _rd, _arm):
        selected = _published_reference(root, con, row["run_id"], round_id)
        return {"reference": selected[0], "source": selected[1]} if selected else {"reference": None, "source": None}


def prepare_material(run: Path, round_id: int) -> dict[str, Any]:
    with _session(run, round_id) as (root, con, row, _rd, arm):
        body = ""
        source = None
        if arm == "F":
            body, source = _fact_material(root, con, row["run_id"], round_id)
        elif arm == "M":
            selected = _published_reference(root, con, row["run_id"], round_id)
            if selected:
                reference, source = selected
                page = open_memory_backend(Path(row["memory_store"]), policy_id=row["memory_policy_id"]).read_version(reference)
                provenance = page.get("provenance") or {}
                if (page["truncated"] or provenance.get("source_run_id") != row["run_id"]
                        or provenance.get("round_id") != source["round_id"]):
                    raise ValueError("historical_memory_provenance_mismatch")
                if complete_reads(con, row["run_id"], round_id).get(reference) != page["body_sha256"]:
                    raise ValueError("historical_memory_not_completely_read")
                body = page["body"]
                source = {**source, "reference": reference, "body_sha256": page["body_sha256"]}
        if len(body) > MAX_BODY_CHARS:
            raise ValueError("historical_material_exceeds_frozen_limit")
        result = {
            "schema_version": "island605-controller-material/v1",
            "study_id": STUDY_ID,
            "policy": POLICY,
            "run_id": row["run_id"],
            "round_id": round_id,
            "arm": arm,
            "source": source,
            "body": body,
            "body_chars": len(body),
            "body_sha256": _hash(body),
            "max_body_chars": MAX_BODY_CHARS,
        }
        target = root / f"rounds/round_{round_id:04d}/controller_material.json"
        db._atomic_write(target, db._json(result) + "\n")
        return result


def verify_delivery(run: Path, round_id: int, prompt: Path) -> dict[str, Any]:
    root = Path(run).resolve()
    material_path = root / f"rounds/round_{round_id:04d}/controller_material.json"
    material = json.loads(material_path.read_text(encoding="utf-8"))
    if material.get("round_id") != round_id or material.get("body_sha256") != _hash(material.get("body", "")):
        raise ValueError("controller_material_identity_mismatch")
    prompt_text = Path(prompt).read_text(encoding="utf-8")
    marker = "MATERIAL SHA256: " + material["body_sha256"]
    if marker not in prompt_text or (material["body"] and material["body"] not in prompt_text):
        raise ValueError("controller_prompt_missing_exact_material")
    result = {
        "schema_version": "island605-controller-delivery/v1",
        "run_id": material["run_id"],
        "round_id": round_id,
        "arm": material["arm"],
        "material_sha256": _hash(material_path.read_bytes()),
        "body_sha256": material["body_sha256"],
        "prompt_sha256": _hash(prompt_text),
    }
    target = root / f"rounds/round_{round_id:04d}/controller_delivery.json"
    db._atomic_write(target, db._json(result) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("select-memory", "prepare", "verify-delivery"))
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--round-id", required=True, type=int)
    parser.add_argument("--prompt", type=Path)
    args = parser.parse_args()
    if args.action == "select-memory":
        result = select_memory_reference(args.run, args.round_id)
    elif args.action == "prepare":
        result = prepare_material(args.run, args.round_id)
    else:
        if args.prompt is None:
            parser.error("verify-delivery requires --prompt")
        result = verify_delivery(args.run, args.round_id, args.prompt)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
