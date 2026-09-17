"""Crash after real durable physics, before assessment DB commit; no API."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from artifact_session import runtime, runner, supervisor
from artifact_session.store import config, connect, dumps, record, transaction
from optics_backend.artifacts import canonical, save, strict
from verify_session import config_for, plan_for, wait, mutate


def child(run, target):
    with transaction(run) as db:
        db.execute("INSERT INTO tasks(id,round,purpose,state,pid,birth) VALUES('crash',1,?,'RUNNING',?,?)",
                   ("audit" if target == "audit" else "search", os.getpid(), supervisor.process_birth(os.getpid())))
    original = runner.evaluate
    def crashing(*args, **kwargs):
        facts = original(*args, **kwargs)
        path = Path(args[2])
        if target == "audit" or (target == "baseline" and path.name == "initial_prescription.json") or (target == "candidate" and path.name == "prescription.json"):
            os._exit(77)
        return facts
    runner.evaluate = crashing
    if target == "audit":
        runner.finalize(run, {"round": 1})
    else:
        runner.search(run, {"round": 1})
    raise AssertionError("CRASH_POINT_NOT_REACHED")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--task-hash")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--child", type=Path)
    parser.add_argument("--target", choices=("baseline", "candidate", "audit"))
    args = parser.parse_args()
    if args.child:
        child(args.child, args.target)
        return
    args.output.mkdir(parents=True, exist_ok=False)
    baseline = strict((args.bundle / "assets/initial_prescription.json").read_bytes())
    baseline["configurations"][0]["sensor_z_mm"] -= .65
    response = canonical({"description": "fixture sensor correction", "prescription": baseline}).decode()
    receipts = {}
    for target in ("baseline", "candidate", "audit"):
        run = (args.output / target).resolve()
        conf = config_for(args.bundle, args.task_hash, [response], False)
        runtime.initialize(run, conf)
        mutate(runtime.submit_plan, run, plan_for(conf, 1), op="plan")
        if target == "audit":
            runner.search(run, {"round": 1})
            with transaction(run) as db:
                runtime.seal(db, run, "fixture")
                db.execute("UPDATE run SET state='FINALIZING'")
        crashed = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--child", str(run), "--target", target], timeout=40)
        assert crashed.returncode == 77, crashed.returncode
        before = runtime.state(run)["counts"]
        version = runtime.state(run)["state_version"]
        receipt = supervisor.recover(run, "recover", version)
        assert receipt["assessments_recovered"]
        assert supervisor.recover(run, "recover", version) == receipt
        assert runtime.state(run)["counts"] == before
        with connect(run) as db:
            root = record(db)
            assert root["baseline"]
            assert db.execute("SELECT COUNT(*) FROM assessments WHERE state='RESERVED'").fetchone()[0] == 0
            if target != "baseline":
                candidate = db.execute("SELECT * FROM candidates").fetchone()
                assert candidate["state"] == "COMPLETE"
                assert json.loads(candidate["detail"])["assessment_ref"] == json.loads(root["incumbent"])
        if target == "audit":
            mutate(runtime.launch, run, "audit", op="finalize")
            wait(run)
            assert runtime.state(run)["counts"] == before, "AUDIT_REPLAYED"
            assert runtime.state(run)["run_state"] == "COMPLETED"
        receipts[target] = {"counts": before, "recovery": receipt, "external_requests": 0}
        if target == "candidate":
            # Corrupt a diagnostic fixture only, never real run evidence.
            with connect(run) as db:
                ref = json.loads(record(db)["incumbent"])
            (run / ref["directory"] / "facts.json").write_bytes(b'{}')
            failed = supervisor.recover(run, "corrupt-recover", runtime.state(run)["state_version"])
            assert failed["recovery_error"] == "RECOVERY_EVIDENCE_FAILED"
            assert runtime.state(run)["run_state"] == "FAILED"
            assert runtime.state(run)["counts"] == before
            receipts[target]["corrupt_evidence_rejected"] = True
    save(args.output / "receipt.json", receipts)
    print("Baseline/candidate/audit durable crash recovery and no-replay passed; external requests=0")


if __name__ == "__main__":
    main()
