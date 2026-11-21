"""One-round probe: can this machine still reach the provider through the bridge?

Kept deliberately tiny so a failure costs at most two provider requests.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

import agent_skill_loop.session_actions as actions  # noqa: E402
import agent_skill_loop.session_runtime as db  # noqa: E402

KEY = Path(r"C:\Users\24294\Projects\aao-e2e\.secrets\deepseek.key")


def main() -> int:
    root = REPO / "experiments/cvrp_midterm/runs/probe"
    if root.exists():
        raise SystemExit(f"exists: {root}")
    os.environ["DEEPSEEK_API_KEY"] = KEY.read_text(encoding="utf-8").strip()

    db.initialize_session(
        output=root,
        operation_id="probe",
        problem="cvrp_construct",
        eoh_model="deepseek-flash",
        eoh_max_requests=2,
        eoh_round_max_requests=2,
        max_solver_calls=6,
        engine_wall_seconds=300.0,
        round_wall_seconds=300.0,
        size=6,
        count=1,
        max_rounds=1,
        memory_enabled=False,
        eoh_thinking="disabled",
        request_timeout=120.0,
    )

    plan = {
        "round_id": 1,
        "direction": "Probe only.",
        "operations": [{"type": "preserve", "target": "search", "mechanism": "Probe."}],
        "preserve": "Everything.",
        "hypothesis": "Probe.",
    }
    path = Path(str(root) + "/plan.json")
    path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    state = db.read_state(run=root)
    actions.submit_plan(run=root, operation_id="p", expected_state_version=state["state_version"], file=path)
    state = db.read_state(run=root)
    actions.execute(run=root, operation_id="e", expected_state_version=state["state_version"])
    deadline = time.time() + 300
    while time.time() < deadline:
        task = db.read_state(run=root).get("task") or {}
        if task.get("state") == "EXITED":
            break
        time.sleep(2)
    state = db.read_state(run=root)
    actions.collect(run=root, operation_id="c", expected_state_version=state["state_version"])
    facts = actions.read_evaluation(run=root)["result"]
    print(json.dumps({k: facts.get(k) for k in (
        "baseline_objective", "best_generated_objective", "terminal_reason",
        "generation_requests", "http_requests", "valid_generation_yield",
    )}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
