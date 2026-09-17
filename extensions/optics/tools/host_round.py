"""Persist an explicit host decision from CLI arguments; no auto-planning model."""

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from optics_backend.artifacts import save
from artifact_session import runtime
from artifact_session.store import config, connect
from verify_session import plan_for


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--round", type=int, required=True)
    p.add_argument("--observation", required=True)
    p.add_argument("--hypothesis", required=True)
    p.add_argument("--decision", choices=("continue", "complete"), required=True)
    p.add_argument("--next-budget", type=int, default=1)
    p.add_argument("--variables", nargs="+")
    args = p.parse_args()
    facts = runtime.read_evaluation(args.run, args.round)
    evaluation = {"schema_id": "optical-prescription-evaluation/v1", "round_id": args.round,
        "online_facts_ref": facts["ref"], "plan_alignment": "unknown" if all("error" in c for c in facts["facts"]["candidates"]) else "partial",
        "observations": [args.observation], "hypotheses": [args.hypothesis], "next_search_advice": args.hypothesis, "memory_action": "none"}
    runtime.submit_evaluation(args.run, evaluation, f"host-evaluate-{args.round}", runtime.state(args.run)["state_version"])
    runtime.finish_round(args.run, args.decision, f"host-finish-{args.round}", runtime.state(args.run)["state_version"])
    if runtime.state(args.run)["run_state"] == "SEARCHING":
        with connect(args.run) as db:
            conf = config(db)
        plan = plan_for(conf, args.round + 1, facts["ref"])
        plan["hypothesis"] = args.hypothesis
        plan["candidate_budget"] = args.next_budget
        if args.variables:
            plan["variables_to_adjust"] = args.variables
        save(args.run / f"host_plan_{args.round+1}.json", plan)
    print(runtime.state(args.run))


if __name__ == "__main__":
    main()
