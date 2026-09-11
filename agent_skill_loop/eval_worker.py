"""JSON stdin/stdout worker. Imports agent_skill_loop only.

When the request carries a ``parent_pid``, a watchdog thread exits this
process as soon as that parent dies. This is the cancellation owner for the
nested official-EoH path on Windows: if the official outer eval process is
killed at its timeout, the inner candidate worker must not be orphaned.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time


def _watch_parent(parent_pid: int) -> None:
    if parent_pid <= 0 or parent_pid == os.getpid():
        return
    if os.name == "nt":
        import ctypes

        SYNCHRONIZE = 0x00100000
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(SYNCHRONIZE, False, int(parent_pid))
        if not handle:
            os._exit(1)
        try:
            kernel32.WaitForSingleObject(handle, 0xFFFFFFFF)
        finally:
            os._exit(1)
    else:
        while True:
            time.sleep(0.5)
            try:
                os.kill(parent_pid, 0)
            except OSError:
                os._exit(1)


def main() -> int:
    try:
        raw = sys.stdin.buffer.read()
        request = json.loads(raw.decode("utf-8"))
        if not isinstance(request, dict):
            raise ValueError
        parent_pid = request.get("parent_pid")
        if isinstance(parent_pid, int):
            threading.Thread(
                target=_watch_parent, args=(parent_pid,), daemon=True, name="parent-watch"
            ).start()
        from agent_skill_loop.evaluator import evaluate_candidate_request

        result = evaluate_candidate_request(request)
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