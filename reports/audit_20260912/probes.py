"""Executable closure checks for A01-A13. Local fixtures only; no paid API.

The original non-asserting probes are preserved in Git history. This entrypoint
now fails if a closure contract regresses instead of printing old bug examples.
"""
from pathlib import Path
import subprocess
import sys


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    targets = [
        "tests/kernel/test_audit_20260912_closure.py",
        "tests/kernel/test_request_budget.py",
        "tests/kernel/test_3plus1_acceptance_repairs.py",
        "tests/kernel/test_3plus1_runner.py",
        "tests/eoh_frozen/test_bounded_repair.py",
        "tests/eoh_frozen/test_workflow_eoh_integration.py",
        "tests/eoh_frozen/test_supervised_chain.py::test_request_limit_stops_engine_preserving_completed_candidate",
    ]
    raise SystemExit(subprocess.call(
        [sys.executable, "-m", "pytest", *targets, "-q", "--tb=short",
         "--junitxml=outputs/audit_20260912_closure.xml"], cwd=root))
