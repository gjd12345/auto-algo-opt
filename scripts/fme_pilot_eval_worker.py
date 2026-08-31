"""JSON-lines worker for :mod:`eoh_rag.fme.pilot_evaluation`.

The parent process supplies one JSON object on stdin.  Exactly one compact JSON
object is emitted on stdout; errors intentionally contain no candidate source
or raw exception text.
"""
from __future__ import annotations

import json
import sys


def main() -> int:
    try:
        raw = sys.stdin.buffer.read()
        request = json.loads(raw.decode("utf-8"))
        if not isinstance(request, dict):
            raise ValueError
        from eoh_rag.fme.pilot_evaluation import _evaluate_candidate_request

        result = _evaluate_candidate_request(request)
    except Exception:
        result = {
            "valid": False,
            "objective": None,
            "instance_objectives": [],
            "suite_hash": None,
            "error_code": "worker_protocol",
            "elapsed_seconds": 0.0,
        }
    sys.stdout.write(json.dumps(result, ensure_ascii=False, separators=(",", ":"), allow_nan=False))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
