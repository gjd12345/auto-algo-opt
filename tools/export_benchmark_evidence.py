"""Export compact, hash-checked Session evidence without provider transcripts.

This is an audit bundle, not a portable Session/checkpoint. Source references
to omitted provider exchanges remain historical references, not bundled files.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PureWindowsPath
import re
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_skill_loop.benchmark import build_archive_from_session, build_report, ExperimentManifest, FrozenSelection


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def verify_bundle(root):
    root = Path(root).resolve()
    hashes = json.loads((root / "SHA256SUMS.json").read_text(encoding="utf-8"))
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    if actual != set(hashes) | {"SHA256SUMS.json"}:
        raise ValueError("bundle_inventory_mismatch")
    for name, expected in hashes.items():
        path = (root / name).resolve()
        if not path.is_relative_to(root) or digest(path.read_bytes()) != expected:
            raise ValueError("bundle_hash_mismatch:" + name)
    return {"verified": True, "files": len(hashes)}


def export_bundle(run, output, report_dir=None):
    run, output = Path(run).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError("bundle_output_already_exists")
    con = sqlite3.connect((run / "session.sqlite3").as_uri() + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        con.execute("BEGIN")
        state = dict(con.execute("SELECT * FROM runs").fetchone())
        if state["state"] not in {"FAILED", "STOPPED", "COMPLETED"}:
            raise ValueError("bundle_requires_terminal_session")
        config_bytes = (run / state["config_ref"]).read_bytes()
        if digest(config_bytes.decode("utf-8").replace("\r\n", "\n").encode()) != state["config_sha256"]:
            raise ValueError("config_hash_mismatch")
        config = json.loads(config_bytes)
        files = {"experiment_manifest.json": encoded(config["experiment_manifest"]),
                 "archive.json": encoded(build_archive_from_session(run))}
        rounds = [dict(row) for row in con.execute("SELECT * FROM rounds ORDER BY round_id")]
        source_hashes = {}
        for row in rounds:
            for stem in ("evaluation_facts", "population_snapshot", "seed_selection",
                         "normalized_plan", "submitted_evaluation", "round_context"):
                ref, expected = row.get(stem + "_ref"), row.get(stem + "_sha256")
                if not ref:
                    continue
                if Path(ref).is_absolute() or PureWindowsPath(ref).drive or ".." in ref.replace("\\", "/").split("/"):
                    raise ValueError("invalid_source_ref")
                path = (run / ref).resolve()
                if not path.is_relative_to(run) or not expected:
                    raise ValueError("invalid_source_ref")
                raw = path.read_bytes()
                # Session text identities use newline-normalized UTF-8.
                if digest(raw.decode("utf-8").replace("\r\n", "\n").encode()) != expected:
                    raise ValueError("source_hash_mismatch:" + ref)
                files[ref] = raw
                source_hashes[ref] = expected
        requests = [dict(row) for row in con.execute(
            "SELECT sequence,round_id,purpose,state,input_tokens,output_tokens,"
            "elapsed_seconds,error_code,finish_reason FROM requests ORDER BY sequence")]
        solver = [dict(row) for row in con.execute("SELECT * FROM solver_calls ORDER BY rowid")]
        tasks = [dict(row) for row in con.execute(
            "SELECT round_id,state,external_effect_started,terminal_reason FROM tasks ORDER BY round_id")]
        files["budget_receipt.json"] = encoded({
            "requests": requests, "solver_calls": solver, "tasks": tasks,
            "total_request_reservations": len(requests), "total_evaluation_attempts": len(solver)})
        files["bundle.json"] = encoded({
            "schema_version": "compact-session-evidence/v1", "run_id": state["run_id"],
            "run_state": state["state"], "state_version": state["state_version"],
            "experiment_manifest_sha256": state["experiment_manifest_sha256"],
            "source_config_sha256": state["config_sha256"], "source_text_hashes": source_hashes,
            "scope": "training facts, population, seed selection, plans and budget; not a resumable Session",
            "omitted": ["provider raw exchanges", "credentials", "SQLite", "heldout results not supplied"],
            "rounds": [{k: row[k] for k in ("round_id", "state", "stop_reason", "decision")} for row in rounds]})
    finally:
        con.close()
    if report_dir is not None:
        for kind in ("incumbent_top1", "archive_topk", "final_population_set"):
            name = kind + ".inputs.json"
            raw = (Path(report_dir) / name).read_bytes()
            inputs = json.loads(raw)
            inputs["manifest"] = ExperimentManifest(**{k: v for k, v in inputs["manifest"].items() if k != "schema_version"})
            if inputs["manifest"].content_hash != state["experiment_manifest_sha256"]:
                raise ValueError("report_experiment_mismatch")
            inputs["selection"] = FrozenSelection.from_dict(inputs["selection"])
            report = build_report(**inputs)
            if report != json.loads((Path(report_dir) / (kind + ".report.json")).read_text(encoding="utf-8")):
                raise ValueError("report_rebuild_mismatch")
            files[name] = raw
            files[kind + ".report.json"] = encoded(report)
        bundle = json.loads(files["bundle.json"])
        bundle["omitted"].remove("heldout results not supplied")
        bundle["report_rebuild_verified"] = True
        files["bundle.json"] = encoded(bundle)
    for name, raw in files.items():
        if re.search(rb"sk-[A-Za-z0-9_-]{16,}|Bearer\s+[A-Za-z0-9_.-]{16,}", raw):
            raise ValueError("potential_secret_in_evidence:" + name)
    output.mkdir(parents=True, exist_ok=False)
    for name, raw in files.items():
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    (output / "SHA256SUMS.json").write_bytes(encoded({name: digest(raw) for name, raw in sorted(files.items())}))
    return verify_bundle(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify", type=Path)
    parser.add_argument("--report-dir", type=Path)
    args = parser.parse_args()
    if args.verify:
        print(json.dumps(verify_bundle(args.verify)))
    elif args.run and args.output:
        print(json.dumps(export_bundle(args.run, args.output, args.report_dir)))
    else:
        parser.error("use --verify DIR or --run SESSION --output NEW_DIR")
