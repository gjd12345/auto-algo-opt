"""Offline task-specific original-entrypoint differential (T1 or T3)."""

import argparse
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from optics_backend.artifacts import digest, save, strict
from optics_backend.offline import child_environment, evaluate, reload_facts
from optics_backend.sources import load_task


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--task-hash", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    manifest = load_task(args.bundle, args.task_hash)
    candidate = args.bundle / "assets/initial_prescription.json"
    receipt = {"task_id": manifest["task_id"], "task_contract_hash": args.task_hash,
               "provider_requests": 0, "profile_executions": 0, "differential": []}
    for mode in ("online", "audit"):
        facts = evaluate(args.bundle, args.task_hash, candidate, args.output / mode, mode=mode)
        result = args.output / f"original_{mode}.json"
        subprocess.run([sys.executable, "-I", "-B", str(args.bundle.resolve() / "evaluate.py"), str(candidate.resolve()),
                        "--mode", mode, "--output", str(result.resolve())],
                       env=child_environment(), check=True, capture_output=True, timeout=600)
        oracle = strict(result.read_bytes(), 20_000_000)
        actual = strict((args.output / mode / "upstream_result.json").read_bytes(), 20_000_000)
        if oracle != actual or reload_facts(args.output / mode, args.task_hash) != facts:
            raise AssertionError("TASK_DIFFERENTIAL_MISMATCH")
        receipt["profile_executions"] += 2 * len(actual["profiles"])
        receipt["differential"].append({"mode": mode, "state": actual["state"], "full_equality": True})
    save(args.output / "receipt.json", receipt)
    print(receipt)


if __name__ == "__main__":
    main()
