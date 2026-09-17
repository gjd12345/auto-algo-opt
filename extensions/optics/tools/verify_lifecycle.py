"""Real subprocess stop/unknown-profile gates. Fixture responses; zero API."""

import argparse
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from optics_backend.artifacts import canonical, save, strict
from artifact_session import runtime, supervisor
from artifact_session.store import connect
from verify_session import config_for, plan_for, wait


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--task-hash", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    baseline = strict((args.bundle / "assets/initial_prescription.json").read_bytes())
    responses = [canonical({"description": "fixture", "prescription": baseline}).decode()]
    receipts = {}
    for case in ("profile_timeout", "stop"):
        conf = config_for(args.bundle, args.task_hash, responses, False)
        if case == "profile_timeout":
            conf["budgets"]["profile_timeout"] = .001
        else:
            conf["budgets"].update({"max_generation_requests": 20, "max_candidate_attempts": 20,
                "max_online_assessments": 21, "max_profile_executions": 29, "per_round_candidate_limit": 20})
        run = args.output / case
        runtime.initialize(run, conf)
        plan = plan_for(conf, 1)
        if case == "stop":
            plan["candidate_budget"] = 20
        runtime.submit_plan(run, plan, "plan", 1)
        runtime.launch(run, "search", "execute", 2)
        if case == "stop":
            for _ in range(100):
                status = runtime.state(run)
                if any(t["state"] == "RUNNING" for t in status["tasks"]):
                    break
                time.sleep(.05)
            supervisor.stop(run, "stop", runtime.state(run)["state_version"])
            status = runtime.state(run)
            assert status["run_state"] == "STOPPED", status
            with connect(run) as db:
                for task in db.execute("SELECT * FROM tasks WHERE pid IS NOT NULL"):
                    assert supervisor.process_birth(task["pid"]) is None
        else:
            status = wait(run)
            assert status["run_state"] == "SEARCH_SEALED", status
            assert status["counts"]["MODEL_REQUEST"] == 0
            with connect(run) as db:
                assert db.execute("SELECT COUNT(*) FROM effects WHERE state='UNKNOWN'").fetchone()[0] == 1
        receipts[case] = status
    save(args.output / "receipt.json", receipts)
    print("Real profile timeout seals search; real owned process-tree stop confirmed; external requests=0")


if __name__ == "__main__":
    main()
