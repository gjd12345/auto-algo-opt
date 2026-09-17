"""Production audit queue with explicit fixture prescriptions; no discovery claims."""

import argparse
import copy
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from optics_backend.artifacts import canonical, save, strict
from artifact_session import runtime
from artifact_session.report import build
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
    feasible = copy.deepcopy(baseline)
    feasible["configurations"][0]["sensor_z_mm"] -= .65
    other = copy.deepcopy(feasible)
    other["stop"]["diameter_mm"] = 2.55
    responses = [canonical({"description": "explicit regression fixture; not a model discovery", "prescription": value}).decode() for value in (feasible, other)]
    receipts = {}
    for case in ("pass", "audit_timeout", "all_invalid"):
        conf = config_for(args.bundle, args.task_hash, responses if case != "all_invalid" else ["not JSON"], False)
        conf["budgets"]["max_generation_requests"] = 2
        conf["budgets"]["max_candidate_attempts"] = 2
        if case == "audit_timeout":
            conf["budgets"]["profile_timeout"] = .7
        run = args.output / case
        runtime.initialize(run, conf)
        plan = plan_for(conf, 1)
        plan["candidate_budget"] = 2
        runtime.submit_plan(run, plan, "plan", 1)
        runtime.launch(run, "search", "execute", 2)
        status = wait(run)
        assert status["run_state"] == "SEARCH_SEALED", status
        runtime.launch(run, "audit", "finalize", status["state_version"])
        wait(run)
        report, _ = build(run)
        assert report["run_state"] == "COMPLETED" and report["external_requests"] == 0
        if case == "pass":
            assert report["final"]["status"] == "local_audit_pass", report
            assert report["counts"]["AUDIT_PROFILE"] == 8
        elif case == "audit_timeout":
            assert report["final"]["best_verified_artifact"] is None
            with connect(run) as db:
                assert db.execute("SELECT COUNT(*) FROM effects WHERE kind='AUDIT_PROFILE' AND state='UNKNOWN'").fetchone()[0] == 2
                assert db.execute("SELECT COUNT(*) FROM effects WHERE kind='AUDIT_PROFILE' AND state='CANCELLED_NOT_STARTED'").fetchone()[0] == 6
                assert db.execute("SELECT COUNT(*) FROM assessments WHERE mode='audit'").fetchone()[0] == 2
        else:
            assert report["final"]["status"] == "baseline_fallback"
            assert report["counts"]["ONLINE_PROFILE"] == 1 and report["counts"]["AUDIT_PROFILE"] == 0
        receipts[case] = report
    save(args.output / "receipt.json", receipts)
    print("Audit PASS, audit unknown continuation without replay, and all-invalid baseline fallback passed; API=0")


if __name__ == "__main__":
    main()
