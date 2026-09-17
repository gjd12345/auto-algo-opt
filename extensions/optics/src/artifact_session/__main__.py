import argparse
import json
from pathlib import Path

from optics_backend.artifacts import strict
from . import runtime


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("init", "state", "submit-plan", "execute", "collect", "read-evaluation",
        "submit-evaluation", "finish-round", "finalize", "stop", "recover", "report", "memory-search", "memory-read", "memory-write"))
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--file", type=Path)
    parser.add_argument("--operation-id")
    parser.add_argument("--expected-state-version", type=int)
    parser.add_argument("--round", type=int)
    parser.add_argument("--decision", choices=("continue", "complete"))
    parser.add_argument("--memory-id")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--require-audit-pass", action="store_true")
    args = parser.parse_args()
    try:
        value = strict(args.file.read_bytes()) if args.file else None
        action = args.action
        if action == "init":
            result = runtime.initialize(args.run, value)
        elif action == "state":
            result = runtime.state(args.run)
        elif action == "read-evaluation":
            result = runtime.read_evaluation(args.run, args.round)
        elif action in ("memory-search", "memory-read"):
            result = runtime.memory_read(args.run, args.memory_id if action == "memory-read" else None)
        elif action == "report":
            from .report import build
            result, markdown = build(args.run)
            if args.output:
                with args.output.open("w", encoding="utf-8", newline="\n") as stream:
                    stream.write(markdown)
        elif action in ("execute", "finalize"):
            result = runtime.launch(args.run, "search" if action == "execute" else "audit", args.operation_id, args.expected_state_version)
        elif action == "collect":
            result = runtime.collect(args.run, args.operation_id, args.expected_state_version)
        elif action == "finish-round":
            result = runtime.finish_round(args.run, args.decision, args.operation_id, args.expected_state_version)
        elif action in ("stop", "recover"):
            from . import supervisor
            result = getattr(supervisor, action)(args.run, args.operation_id, args.expected_state_version)
        else:
            name = {"submit-plan": "submit_plan", "submit-evaluation": "submit_evaluation", "memory-write": "memory_write"}[action]
            result = getattr(runtime, name)(args.run, value, args.operation_id, args.expected_state_version)
        print(json.dumps({"ok": True, "result": result}, ensure_ascii=False))
        if args.require_audit_pass and action == "report" and (not result.get("final") or result["final"]["status"] != "local_audit_pass"):
            return 6
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": type(exc).__name__, "detail": str(exc)}, ensure_ascii=False))
        message = str(exc)
        if "UNKNOWN" in message or "PROCESS_EXIT_NOT_CONFIRMED" in message:
            return 5
        if any(tag in message for tag in ("BUDGET", "LIMIT", "_STATE", "CLOSED", "SEALED", "STILL_RUNNING")) and "STATE_VERSION" not in message:
            return 3
        if any(tag in message for tag in ("CONFLICT", "FIELDS", "ENUM", "INVALID_", "PLAN_VARIABLE", "PLAN_FEEDBACK", "REFERENCE")):
            return 2
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
