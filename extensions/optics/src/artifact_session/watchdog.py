"""Independent hard-deadline guardian for an owned task process tree."""

import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from artifact_session.store import change, config, connect, dumps, event, record, transaction
from artifact_session.supervisor import process_birth, terminate_owned


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--task-id", required=True)
    args = parser.parse_args()
    while True:
        with connect(args.run) as db:
            row = db.execute("SELECT * FROM tasks WHERE id=?", (args.task_id,)).fetchone()
            if not row or row["state"] not in ("STARTING", "RUNNING"):
                return
            task = dict(row)
            conf = config(db)
        deadline = conf["search_deadline"] if task["purpose"] == "search" else conf["global_deadline"]
        if time.time() < deadline:
            time.sleep(min(.2, deadline - time.time()))
            continue
        if task["pid"]:
            terminate_owned(task)
        else:
            # STARTING worker checks deadlines before registration/effects.
            pass
        with transaction(args.run) as db:
            current = record(db)
            if current["state"] in ("STOPPED", "FAILED", "COMPLETED"):
                return
            from artifact_session.recovery import reconcile_completed, interrupted_round
            reconcile_completed(db, args.run)
            for effect in db.execute("SELECT * FROM effects WHERE state IN ('RESERVED','STARTED')").fetchall():
                info = {**json.loads(effect["detail"]), "process_confirmed_dead": True}
                db.execute("UPDATE effects SET state=?,detail=? WHERE id=?",
                           ("UNKNOWN" if effect["state"] == "STARTED" else "CANCELLED_NOT_STARTED", dumps(info), effect["id"]))
            db.execute("UPDATE tasks SET state='INTERRUPTED' WHERE id=?", (args.task_id,))
            db.execute("UPDATE assessments SET state='INCOMPLETE' WHERE state='RESERVED'")
            if current["state"] in ("STOPPED", "FAILED", "COMPLETED"):
                return
            if task["purpose"] == "search" and current["state"] == "SEARCHING":
                from artifact_session.runtime import seal
                interrupted_round(db, args.run, task["round"])
                db.execute("UPDATE rounds SET state='EVALUATE_SKIPPED' WHERE id=?", (task["round"],))
                seal(db, args.run, "SEARCH_DEADLINE")
            else:
                change(db, state="STOPPED", reason="GLOBAL_DEADLINE")
            event(db, "watchdog_deadline", {"task_id": args.task_id})
        return


if __name__ == "__main__":
    main()
