"""Minimal real T1 differential, plus reload/identity checks. Zero model calls.

No author solution, historical trajectory, provider, or Session is used.
"""

import argparse
import copy
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from optics_backend.artifacts import canonical, digest, require_python, save, strict
from optics_backend.offline import OfflineFailure, child_environment, compare_saved, evaluate, reload_facts
from optics_backend.sources import import_task, load_task
from optics_backend.worker import environment_identity


def main():
    require_python()
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=600)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    bundle = args.output / "t1_bundle"
    manifest = import_task(args.archive, bundle, args.source_sha256)
    task_hash = manifest["task_contract_hash"]
    baseline = bundle / "assets/initial_prescription.json"
    rows = []
    adapter_profiles, oracle_profiles = 0, 0
    for mode in ("online", "audit"):
        output = args.output / ("adapter_" + mode)
        start = time.monotonic()
        facts = evaluate(bundle, task_hash, baseline, output, mode=mode, timeout=args.timeout)
        wrapper_seconds = time.monotonic() - start
        oracle_path = args.output / ("original_" + mode + ".json")
        start = time.monotonic()
        result = subprocess.run([sys.executable, "-I", "-B", str(bundle / "evaluate.py"), str(baseline),
                                 "--mode", mode, "--output", str(oracle_path)],
                                env=child_environment(), capture_output=True, timeout=args.timeout)
        if result.returncode:
            raise RuntimeError("ORIGINAL_ENTRYPOINT_FAILED:" + result.stderr.decode(errors="replace"))
        oracle_seconds = time.monotonic() - start
        oracle = strict(oracle_path.read_bytes(), 20_000_000)
        wrapper = strict((output / "upstream_result.json").read_bytes(), 20_000_000)
        if oracle != wrapper:
            raise AssertionError("UPSTREAM_DIFFERENTIAL_MISMATCH:" + mode)
        if reload_facts(output, task_hash) != facts:
            raise AssertionError("RELOAD_MISMATCH")
        rows.append({"mode": mode, "exact_structural_numeric_match": True, "state": oracle["state"],
                     "oracle_seconds": oracle_seconds, "adapter_seconds": wrapper_seconds,
                     "profile_count_each": len(oracle["profiles"]), "ranking_key": facts["ranking_key"]})
        adapter_profiles += strict((output / "terminal.json").read_bytes())["profile_executions"]
        oracle_profiles += len(oracle["profiles"])
        print(mode, oracle["state"], "equal", flush=True)

    # A documented deterministic input perturbation, not a model/search candidate.
    changed = copy.deepcopy(strict(baseline.read_bytes()))
    changed["configurations"][0]["sensor_z_mm"] += .01
    changed_path = args.output / "perturbed_input.json"
    save(changed_path, changed)
    evaluate(bundle, task_hash, changed_path, args.output / "perturbed_online", timeout=args.timeout)
    adapter_profiles += strict((args.output / "perturbed_online/terminal.json").read_bytes())["profile_executions"]
    receipt = compare_saved(args.output / "adapter_online", args.output / "perturbed_online",
                            task_hash, args.output / "comparison.json")
    # Rebuild comparison in a fresh process from disk, with no physical or model call.
    cli = Path(__file__).resolve().parents[1] / "src/optics_backend/__main__.py"
    launcher = "import sys;sys.path.insert(0,sys.argv.pop(1));from optics_backend.__main__ import main;raise SystemExit(main())"
    result = subprocess.run([sys.executable, "-I", "-B", "-c", launcher, str(cli.parents[1]), "compare",
                             "--previous", str(args.output / "adapter_online"), "--candidate", str(args.output / "perturbed_online"),
                             "--task-hash", task_hash, "--output", str(args.output / "comparison_reloaded.json")],
                            env=child_environment(), capture_output=True, timeout=30)
    if result.returncode or strict((args.output / "comparison_reloaded.json").read_bytes()) != strict((args.output / "comparison.json").read_bytes()):
        raise AssertionError("FRESH_PROCESS_COMPARISON_MISMATCH:" + result.stderr.decode(errors="replace"))

    # Tamper detection, on disposable copies only (no extra optical executions).
    import shutil
    copied = args.output / "tamper_probe"
    shutil.copytree(bundle, copied)
    p = copied / "assets/evaluation_protocol.json"
    with p.open("ab") as stream:
        stream.write(b" ")
    try:
        load_task(copied, task_hash)
    except ValueError as exc:
        if "TASK_FILE_HASH_MISMATCH" not in str(exc):
            raise
    else:
        raise AssertionError("TAMPER_ACCEPTED")
    invalid = copy.deepcopy(changed)
    invalid["stop"]["diameter_mm"] = 999
    invalid_path = args.output / "invalid_input.json"
    save(invalid_path, invalid)
    try:
        evaluate(bundle, task_hash, invalid_path, args.output / "invalid_online", timeout=args.timeout)
    except OfflineFailure as exc:
        terminal = strict((args.output / "invalid_online/terminal.json").read_bytes())
        if exc.exit_code != 2 or terminal["status"] != "submission_invalid" or terminal["profile_executions"] != 0:
            raise AssertionError("INVALID_CANDIDATE_MISCLASSIFIED") from exc
        if (args.output / "invalid_online/artifacts").exists():
            raise AssertionError("INVALID_CANDIDATE_EXPORTED")
    else:
        raise AssertionError("INVALID_CANDIDATE_ACCEPTED")
    # A directory must reach the input checker as such, never as parsed content.
    try:
        evaluate(bundle, task_hash, bundle, args.output / "nonregular_input", timeout=args.timeout)
    except OfflineFailure as exc:
        if exc.exit_code != 2:
            raise AssertionError("NONREGULAR_INPUT_MISCLASSIFIED") from exc
    else:
        raise AssertionError("NONREGULAR_INPUT_ACCEPTED")
    report = {"scope": "P1 T1 offline adapter only", "task_contract_hash": task_hash,
              "source_package_sha256": args.source_sha256, "environment": environment_identity(),
              "protocol_mode": "adapted_external_controller", "controller_identity": {"host": "offline_fixture", "controller_model": None},
              "exact_original_environment_reproduction": False,
              "environment_deviation": "Windows Python 3.12.11 versus declared Linux Python 3.12.14",
              "differential": rows, "fresh_process_comparison_equal": True,
              "tamper_rejected": True, "invalid_rejected_without_physics_or_export": True,
              "nonregular_input_rejected": True,
              "comparison": receipt, "provider_requests": 0,
              "profile_executions": {"adapter": adapter_profiles, "original_oracle": oracle_profiles,
                                     "total": adapter_profiles + oracle_profiles},
              "audit_purpose": "diagnostic_audit", "independent_verifier": "NOT_RUN",
              "session_v2": "NOT_IMPLEMENTED", "best_verified_artifact": None}
    save(args.output / "p1_receipt.json", report)
    hashes = {p.relative_to(args.output).as_posix(): digest(p.read_bytes()) for p in sorted(args.output.rglob("*"))
              if p.is_file() and "tamper_probe" not in p.parts}
    save(args.output / "SHA256_manifest.json", hashes)
    print("P1 receipt:", args.output / "p1_receipt.json", flush=True)


if __name__ == "__main__":
    main()
