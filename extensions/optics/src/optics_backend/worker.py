"""Isolated offline physics entrypoint. No provider credentials or network client."""

from __future__ import annotations

import argparse
import platform
from pathlib import Path
import sys
import time
import os
import threading
import importlib.metadata

# This file is launched with -I; only the installed, fixed adapter source is added.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from optics_backend.artifacts import (CANONICALIZATION, canonical, digest, extract_response,
                                      load_artifact, require_python, save, store_artifact, strict)
from optics_backend.sources import load_task
from optics_backend.ranking import RANKING_HASH, rank_key


def environment_identity():
    distributions = sorted({(d.metadata["Name"].lower().replace("_", "-"), d.version)
                            for d in importlib.metadata.distributions() if d.metadata["Name"]})
    return {"python": sys.version, "platform": platform.platform(),
            "architecture": platform.machine(), "implementation": platform.python_implementation(),
            "dependency_scope": "all-installed-distributions (conservative superset, not a stdlib assertion)",
            "dependencies": [{"name": name, "version": version} for name, version in distributions],
            "dependency_manifest_sha256": digest(canonical(distributions))}


def adapter_hash():
    root = Path(__file__).resolve().parent
    return digest(canonical({p.name: digest(p.read_bytes()) for p in sorted(root.glob("*.py"))}))


def physics_result(a, candidate, task, baseline, protocol, mode, output, session_run=None, assessment_id=None):
    """Mirror only orchestration/aggregation; keep frozen numerical functions untouched.

    The differential oracle is the original evaluate.py, not this implementation.
    """
    profiles = protocol["audit_sampling"] if mode == "audit" else {"ONLINE_P769_PHASE0": protocol["online_sampling"]}
    results = {}
    for index, (name, spec) in enumerate(profiles.items()):
        effect = {"effect_id": f"profile-{index:04d}", "profile_id": name,
                  "profile_spec_hash": digest(canonical(spec)), "mode": mode}
        save(output / "profiles" / f"{index:04d}.started.json", effect)
        if session_run:
            from artifact_session.ledger import start_effect
            start_effect(session_run, f"{assessment_id}-{index}", {"profile_id": name, "profile_spec_hash": effect["profile_spec_hash"]})
        timer = None
        if session_run:
            from artifact_session.store import connect, config
            with connect(session_run) as db:
                conf = config(db)
            deadline = conf["search_deadline"] if mode == "online" else conf["global_deadline"]
            timeout = min(conf["budgets"]["profile_timeout"], deadline - time.time())
            def expire():
                try:
                    save(output / "profile_timeout.json", {"profile_id": name, "assessment_id": assessment_id,
                         "status": "unknown", "reason": "PROFILE_TIMEOUT"})
                finally:
                    os._exit(5)
            timer = threading.Timer(max(.001, timeout), expire)
            timer.daemon = True
            timer.start()
        start = time.monotonic()
        sample = a.e.Sampling(**{k: tuple(v) if isinstance(v, list) else v for k, v in spec.items()})
        try:
            result = a.e.evaluate(candidate, task, sample, baseline=baseline)
        finally:
            if timer:
                timer.cancel()
        save(output / "profiles" / f"{index:04d}.completed.json",
             {**effect, "elapsed_seconds": time.monotonic() - start, "result": result})
        if session_run:
            from artifact_session.ledger import finish_effect
            finish_effect(session_run, f"{assessment_id}-{index}", "COMPLETE",
                          {"result_sha256": digest(canonical(result)), "elapsed_seconds": time.monotonic() - start})
        if result["status"] == "DESIGN_INVALID":
            raise a.InvalidSubmission(result.get("error", "invalid design"))
        results[name] = result
    statuses = {r["status"] for r in results.values()}
    if statuses - {"OK", "OPTICAL_FAIL", "NUMERICAL_UNCERTAIN"}:
        raise RuntimeError("FROZEN_EVALUATOR_UNKNOWN_STATUS")
    if "OPTICAL_FAIL" in statuses:
        return {"state": "FAIL", "profiles": results, "reward": 0, "optical_status": "FAIL",
                "reason": "FROZEN_EVALUATOR_OPTICAL_FAIL", "scope": a.e.SCOPE}
    if "NUMERICAL_UNCERTAIN" in statuses:
        return {"state": "NUMERICAL_UNCERTAIN", "profiles": results, "reward": 0,
                "optical_status": "UNKNOWN", "reason": "FROZEN_EVALUATOR_NUMERICAL_UNCERTAIN", "scope": a.e.SCOPE}
    if mode == "online":
        result = next(iter(results.values()))
        return {"state": "ONLINE_PASS" if result["judgment"]["all_hard_constraints_passed"] else "ONLINE_FAIL",
                "profiles": results, "final_audit": "NOT_RUN", "scope": a.e.SCOPE,
                "independent_wavefront_verified": False}
    rows = {c["constraint_id"]: a.gate.interval_decision(c, [r["aggregate_metrics"][c["metric"]] for r in results.values()])
            for c in task["hard_constraints"]}
    convergence = a.e.convergence_report(list(results.values()), task["hard_constraints"])
    decision = a.gate.combine(rows, convergence["status"])
    return {"state": decision, "profiles": results, "constraints": rows, "convergence": convergence,
            "reward": int(decision == "PASS"), "scope": a.e.SCOPE, "independent_wavefront_verified": False,
            "historical_data_used_for_judgment": False, "variable_and_static_physics_check": "PASS",
            "optical_status": decision if decision in ("PASS", "FAIL") else "UNKNOWN"}


def run(args):
    require_python()
    manifest = load_task(args.bundle, args.task_hash)
    sys.path.insert(0, str(args.bundle.resolve() / "physics"))
    import acceptance as a
    task, baseline, protocol, rules = a.load_context(args.bundle / "assets")
    # Bounded read and evidence commit precede any untrusted parsing.
    if args.candidate.is_symlink() or not args.candidate.is_file():
        save(args.output / "terminal.json", {"status": "submission_invalid", "error": "REGULAR_CANDIDATE_REQUIRED",
             "provider_requests": 0, "profile_executions": 0})
        return 2
    with args.candidate.open("rb") as stream:
        raw = stream.read(1_032_001)
    (args.output / "input.raw").write_bytes(raw)
    save(args.output / "input_capture.json", {"captured_bytes": len(raw),
         "captured_sha256": digest(raw), "size_limit_exceeded": len(raw) > 1_032_000})
    try:
        if args.response:
            fragment, extraction = extract_response(raw)
        else:
            fragment, extraction = raw, {"response_sha256": None, "start_byte": 0, "end_byte": len(raw)}
        (args.output / "prescription.raw.json").write_bytes(fragment)
        save(args.output / "extraction.json", {**extraction, "raw_artifact_sha256": digest(fragment)})
        # Both raw and canonical inputs are checked by the unchanged upstream checker.
        strict(fragment)
        parsed = a.load_candidate(args.output / "prescription.raw.json", rules)
        a.e.check_variables(parsed, task, baseline)
        body = canonical(parsed)
        (args.output / "canonical.pending.json").write_bytes(body)
        candidate = a.load_candidate(args.output / "canonical.pending.json", rules)
        a.e.check_variables(candidate, task, baseline)
        if args.parent:
            import copy
            parent = a.load_candidate(args.parent, rules)
            plan = strict(args.plan.read_bytes())
            adjusted = copy.deepcopy(candidate)
            def replace_at(obj, pointer, value):
                parts = [p.replace("~1", "/").replace("~0", "~") for p in pointer.strip("/").split("/")]
                current = obj
                for part in parts[:-1]:
                    current = current[int(part)] if isinstance(current, list) else current[part]
                if isinstance(current, list):
                    current[int(parts[-1])] = value
                else:
                    current[parts[-1]] = value
            for variable in task["variables"]:
                if variable["variable_id"] in plan["variables_to_adjust"]:
                    for pointer in variable.get("paths", [variable.get("path")]):
                        replace_at(adjusted, pointer, a.e.pointer(parent, pointer))
            if canonical(adjusted) != canonical(parent):
                raise ValueError("VARIABLE_NOT_ALLOWED_BY_PLAN")
    except (ValueError, TypeError, KeyError, IndexError, OverflowError, RecursionError) as exc:
        save(args.output / "terminal.json", {"status": "submission_invalid", "error": str(exc),
             "provider_requests": 0, "profile_executions": 0})
        return 2

    env = environment_identity()
    identity = {"task_contract_hash": args.task_hash,
                "canonical_artifact_sha256": digest(body),
                "canonicalization_version": CANONICALIZATION,
                "physics_implementation_hash": digest(canonical(rules["implementation_sha256"])),
                "assessment_adapter_hash": adapter_hash(), "mode": args.mode,
                "sampling_manifest_hash": digest(canonical(protocol["online_sampling" if args.mode == "online" else "audit_sampling"])),
                "acceptance_rules_hash": digest((args.bundle / "assets/acceptance_rules.json").read_bytes()),
                "environment_manifest_hash": digest(canonical(env))}
    save(args.output / "assessment_identity.json", identity)
    save(args.output / "environment.json", env)
    if getattr(args, "static_only", False):
        save(args.output / "static_validation.json", {"identity": identity, "prescription": candidate})
        save(args.output / "terminal.json", {"status": "static_valid", "profile_executions": 0})
        return 0
    start = time.monotonic()
    try:
        result = physics_result(a, candidate, task, baseline, protocol, args.mode, args.output,
                                args.session_run, args.assessment_id)
    except a.InvalidSubmission as exc:
        # Static-valid inputs may still be rejected during full optical setup.
        save(args.output / "terminal.json", {"status": "submission_invalid", "error": str(exc),
             "provider_requests": 0, "profile_executions": len(list((args.output / "profiles").glob("*.started.json")))})
        return 2
    # A full optical DESIGN_INVALID must not leave a reusable artifact behind.
    # Storage/identity errors remain infrastructure, outside candidate-error conversion.
    artifact_dir, artifact = store_artifact(args.output / "artifacts", fragment, args.task_hash)
    load_artifact(artifact_dir, args.task_hash)
    save(args.output / "upstream_result.json", result)
    profile_values = list(result["profiles"].values())
    statuses = {p["status"] for p in profile_values}
    physics_status = "OPTICAL_FAIL" if "OPTICAL_FAIL" in statuses else "NUMERICAL_UNCERTAIN" if "NUMERICAL_UNCERTAIN" in statuses else "OK"
    online_ok = args.mode == "online" and physics_status == "OK"
    p = profile_values[0]
    facts = {"schema_id": "optics-offline-facts/v1", "mode": args.mode,
             "purpose": "online_calibration" if args.mode == "online" else "local_verification_audit" if args.session_run else "diagnostic_audit",
             "verification_pipeline": bool(args.mode == "audit" and args.session_run), "evaluation_identity": identity,
             "evaluation_identity_sha256": digest(canonical(identity)),
             "artifact_ref": artifact_dir.relative_to(args.output).as_posix(),
             "submission_status": "valid", "execution_status": "complete", "physics_status": physics_status,
             "online_feasible": p["judgment"]["all_hard_constraints_passed"] if online_ok else None,
             "quality_q": p["aggregate_metrics"]["quality_q"] if online_ok else None,
             "constraints": p["judgment"]["constraint_vector"] if online_ok else {},
             "constraint_ids": [c["constraint_id"] for c in task["hard_constraints"]],
             "profile_results": result["profiles"], "audit_verdict": result["state"] if args.mode == "audit" else None,
             "upstream_result_sha256": digest(canonical(result)), "independent_verifier": "NOT_RUN"}
    key = rank_key(facts)
    facts.update({"ranking_key": key, "ranking_contract_hash": RANKING_HASH,
                  "vsum": -key[1] if key else None, "vmax": -key[2] if key else None})
    save(args.output / "facts.json", facts)
    save(args.output / "terminal.json", {"status": "complete", "provider_requests": 0,
         "profile_executions": len(profile_values), "elapsed_seconds": time.monotonic() - start,
         "evidence_sha256": {p.relative_to(args.output).as_posix(): digest(p.read_bytes())
                             for p in sorted(args.output.rglob("*")) if p.is_file()},
         "facts_sha256": digest(canonical(facts)), "source_package_sha256": manifest["source_package_sha256"]})
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--task-hash", required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--response", action="store_true")
    parser.add_argument("--mode", choices=("online", "audit"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--owner-token", required=True)
    parser.add_argument("--session-run", type=Path)
    parser.add_argument("--assessment-id")
    parser.add_argument("--parent", type=Path)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--static-only", action="store_true")
    args = parser.parse_args()
    # Ownership errors must not create/overwrite diagnostics in another caller's directory.
    request = strict((args.output / "execution_request.json").read_bytes())
    expected = {"owner_token": args.owner_token, "task_contract_hash": args.task_hash,
                "bundle": str(args.bundle.resolve()), "candidate": str(args.candidate.absolute()),
                "mode": args.mode, "response": args.response}
    if request != expected:
        return 4
    if args.session_run:
        from artifact_session.supervisor import process_birth
        save(args.output / "process_owner.json", {"pid": os.getpid(), "birth": process_birth(os.getpid())})
    try:
        return run(args)
    except Exception as exc:
        # Evidence/storage failures remain infrastructure failures, never objective=0.
        save(args.output / "infrastructure_error.json", {"status": "failed", "error_type": type(exc).__name__,
             "error": str(exc), "provider_requests": 0})
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
