"""P1 offline CLI; intentionally does not expose generation or Session commands."""

import argparse
import json
from pathlib import Path
import subprocess

from .artifacts import require_python
from .sources import import_task
from .offline import OfflineFailure, compare_saved, evaluate


def main():
    require_python()
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    imp = sub.add_parser("import-t1", aliases=["import-task"])
    imp.add_argument("--task-id", default="optics-t1-singlet")
    imp.add_argument("--archive", type=Path, required=True)
    imp.add_argument("--source-sha256", required=True)
    imp.add_argument("--output", type=Path, required=True)
    ev = sub.add_parser("evaluate")
    ev.add_argument("--bundle", type=Path, required=True)
    ev.add_argument("--task-hash", required=True)
    ev.add_argument("--candidate", type=Path, required=True)
    ev.add_argument("--response", action="store_true")
    ev.add_argument("--mode", choices=("online", "diagnostic_audit"), default="online")
    ev.add_argument("--timeout", type=float, default=600)
    ev.add_argument("--output", type=Path, required=True)
    comp = sub.add_parser("compare")
    comp.add_argument("--previous", type=Path)
    comp.add_argument("--candidate", type=Path, required=True)
    comp.add_argument("--task-hash", required=True)
    comp.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command in ("import-t1", "import-task"):
            result = import_task(args.archive, args.output, args.source_sha256, args.task_id)
        elif args.command == "evaluate":
            facts = evaluate(args.bundle, args.task_hash, args.candidate, args.output,
                             mode="audit" if args.mode == "diagnostic_audit" else "online",
                             response=args.response, timeout=args.timeout)
            result = {"output": str(args.output), "evaluation_identity_sha256": facts["evaluation_identity_sha256"],
                      "ranking_key": facts["ranking_key"], "audit_verdict": facts["audit_verdict"]}
        else:
            result = compare_saved(args.previous, args.candidate, args.task_hash, args.output)
        print(json.dumps({"ok": True, "result": result}, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": type(exc).__name__, "detail": str(exc)}, ensure_ascii=False))
        return exc.exit_code if isinstance(exc, OfflineFailure) else 5 if isinstance(exc, subprocess.TimeoutExpired) else 4


if __name__ == "__main__":
    raise SystemExit(main())
