"""Run the frozen Iteration-B G0--G4 pilot without printing credentials.

The runner is intentionally a thin host controller: official EoH remains the
authority for generation, parent selection, operators, and evaluator calls.
Each group gets a new Session and an isolated output/Memory directory.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import time
import argparse
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_skill_loop import session_actions as actions
from agent_skill_loop import session_runtime as db
from agent_skill_loop.benchmark import build_co_pilot_manifests
from agent_skill_loop.evidence.report import reconstruct_session_evidence


MODEL = "qwen/deepseek-v4.1-flash"
API_KEY_ENV = "MODEL_ROUTER_API_KEY"
TOTAL_EVALUATION_BUDGET = 100
ROUND_EVALUATION_BUDGET = 50
TOTAL_REQUEST_BUDGET = 24
ROUND_REQUEST_BUDGET = 12
MAX_ROUNDS = 2
POLL_SECONDS = 2.0
DEFAULT_ENGINE_WALL_SECONDS = 3600.0
DEFAULT_ROUND_WALL_SECONDS = 1800.0


def load_env(path: Path) -> None:
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip().strip('"').strip("'")
        if name in {API_KEY_ENV, "MODEL_ROUTER_ENDPOINT"}:
            os.environ[name] = value


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _endpoint() -> str:
    value = os.environ.get("MODEL_ROUTER_ENDPOINT", "").strip()
    if not value:
        raise RuntimeError("MODEL_ROUTER_ENDPOINT_missing")
    if not os.environ.get(API_KEY_ENV, "").strip():
        raise RuntimeError("MODEL_ROUTER_API_KEY_missing")
    return value


def _plan(group: str, round_id: int, state: dict[str, Any]) -> dict[str, Any]:
    progress = group in {"G2", "G3", "G4"}
    plan = {
        "round_id": round_id,
        "direction": f"CO Iteration B {group}: preserve the frozen OBP contract and test the assigned outer treatment",
        "operations": [{
            "type": "preserve",
            "target": "interface",
            "mechanism": "preserve the official EoH operator, parent selection, evaluator and benchmark gate",
        }],
        "preserve": "OBP suite, MetricSpec, model, endpoint, inheritance, repair setting and evaluator budget",
        # G0 is the record-only arm: it must not consume or expose runtime
        # feedback.  The other arms receive the previous round's verified
        # evaluation reference when the runtime makes one available.
        "feedback_basis": state.get("feedback_basis") if group != "G0" else None,
        "memory_basis": [],
        "reference_skill_ref": None,
        "hypothesis": "The assigned outer treatment may change observed search progress; no causal effect is assumed.",
    }
    if group == "G4":
        plan["search_intent"] = {"phase": "exploration" if round_id == 1 else "exploitation"}
    if progress and round_id > 1:
        plan["reasoning_summary"] = "Use only the previous Runtime-verified SearchProgress facts; do not select EoH parents or operators in the host."
    return plan


def _wait_for_exit(root: Path, deadline_seconds: float = 2100.0) -> dict[str, Any]:
    deadline = time.monotonic() + deadline_seconds
    while time.monotonic() < deadline:
        state = db.read_state(run=root)
        task = state.get("task")
        if task and task.get("state") == "EXITED":
            return state
        # A preflight terminal can clear the live task while the envelope's
        # top-level state is already terminal.  Accept both projections so a
        # controlled evidence failure is reported as such instead of being
        # mislabeled as a runner timeout.
        if state.get("state") in {"FAILED", "STOPPED", "COMPLETED"}:
            return state
        if state.get("run_state") in {"FAILED", "STOPPED", "COMPLETED"} and not task:
            return state
        time.sleep(POLL_SECONDS)
    raise RuntimeError("experiment_wall_timeout")


def _run_group(base: Path, group: str, manifest: dict[str, Any], endpoint: str,
               *, engine_wall_seconds: float, round_wall_seconds: float) -> dict[str, Any]:
    root = base / group
    memory_store = base / "memory" / group
    db.initialize_session(
        output=root,
        operation_id=f"{group.lower()}-init",
        experiment_manifest=manifest,
        eoh_model=MODEL,
        eoh_endpoint=endpoint,
        eoh_api_key_env=API_KEY_ENV,
        benchmark_id="eohs_v1",
        benchmark_profile_name="obp_evolution_mini",
        eoh_max_requests=TOTAL_REQUEST_BUDGET,
        eoh_round_max_requests=ROUND_REQUEST_BUDGET,
        engine_wall_seconds=engine_wall_seconds,
        round_wall_seconds=round_wall_seconds,
        max_solver_calls=TOTAL_EVALUATION_BUDGET,
        round_budget=ROUND_EVALUATION_BUDGET,
        memory_store=str(memory_store) if manifest["memory_enabled"] else None,
    )
    rounds: list[dict[str, Any]] = []
    for round_id in range(1, MAX_ROUNDS + 1):
        state = db.read_state(run=root)
        if manifest["memory_enabled"]:
            actions.memory_search(run=root, query="OBP online priority", limit=2)
            state = db.read_state(run=root)
        plan_path = base / "plans" / group / f"plan_{round_id:04d}.json"
        _write(plan_path, _plan(group, round_id, state))
        planned = actions.submit_plan(run=root, operation_id=f"{group.lower()}-plan-{round_id}",
                                      expected_state_version=state["state_version"], file=plan_path)
        launched = actions.execute(run=root, operation_id=f"{group.lower()}-execute-{round_id}",
                                   expected_state_version=planned["state_version"])
        state = _wait_for_exit(root)
        if not state.get("task") or state["task"].get("state") != "EXITED":
            raise RuntimeError(f"{group}_round_{round_id}_did_not_exit")
        collected = actions.collect(run=root, operation_id=f"{group.lower()}-collect-{round_id}",
                                    expected_state_version=state["state_version"])
        facts = actions.read_evaluation(run=root)["result"]
        evaluation = {
            "plan_alignment": "aligned",
            "observations": [{"claim": "Runtime-verified SearchProgress and evaluation facts are available.",
                               "evidence_refs": [facts["evidence_refs"][0]]}],
            "hypotheses": [],
            "next_search_advice": {},
            "memory_action": ({"kind": "none", "reason": "No new reusable finding was selected for this controlled pilot."}
                               if manifest["memory_enabled"] else {"kind": "disabled"}),
        }
        evaluation_path = base / "plans" / group / f"evaluation_{round_id:04d}.json"
        _write(evaluation_path, evaluation)
        evaluated = actions.submit_evaluation(run=root, operation_id=f"{group.lower()}-evaluation-{round_id}",
                                               expected_state_version=collected["state_version"], file=evaluation_path)
        decision = "continue" if round_id < MAX_ROUNDS else "complete"
        finished = actions.finish_round(run=root, operation_id=f"{group.lower()}-finish-{round_id}",
                                        expected_state_version=evaluated["state_version"], decision=decision)
        rounds.append({
            "round_id": round_id,
            "evaluation_ref": facts.get("evidence_refs", [None])[0],
            "terminal_reason": facts.get("terminal_reason"),
            "search_progress": facts.get("search_progress"),
            "request_costs": facts.get("request_costs"),
            "dual_budget": facts.get("dual_budget"),
            "phase_budget": facts.get("phase_budget"),
            "finish": finished.get("result", {}),
        })
    report = reconstruct_session_evidence(root)
    _write(root / "co_iteration_b_report.json", report)
    summary = {
        "group": group,
        "manifest": manifest,
        "run_root": str(root),
        "memory_store": str(memory_store) if manifest["memory_enabled"] else None,
        "rounds": rounds,
        "report": {"total_requests": report["total_requests"], "total_solver_attempts": report["total_solver_attempts"]},
    }
    _write(root / "co_iteration_b_summary.json", summary)
    return summary


def main(selected_groups: tuple[str, ...] | None = None, *, output_name: str = "co_iteration_b_20260918",
         engine_wall_seconds: float = DEFAULT_ENGINE_WALL_SECONDS,
         round_wall_seconds: float = DEFAULT_ROUND_WALL_SECONDS) -> int:
    workspace = Path(__file__).resolve().parents[1]
    load_env(workspace / ".env")
    endpoint = _endpoint()
    output = workspace / "experiments" / output_name
    output.mkdir(parents=True, exist_ok=True)
    base_root = output / "manifest_source"
    if not (base_root / "config_frozen.json").is_file():
        db.initialize_session(
            output=base_root,
            operation_id="co-base-init",
            eoh_model=MODEL,
            eoh_endpoint=endpoint,
            eoh_api_key_env=API_KEY_ENV,
            benchmark_id="eohs_v1",
            benchmark_profile_name="obp_evolution_mini",
            inheritance_mode="population_seeds",
            max_rounds=MAX_ROUNDS,
            round_budget=ROUND_EVALUATION_BUDGET,
            max_solver_calls=TOTAL_EVALUATION_BUDGET,
            eoh_max_requests=TOTAL_REQUEST_BUDGET,
            eoh_round_max_requests=ROUND_REQUEST_BUDGET,
            engine_wall_seconds=engine_wall_seconds,
            round_wall_seconds=round_wall_seconds,
            search_policy_defaults={"pop_size": 4, "n_pop": 2, "max_sample_nums": TOTAL_EVALUATION_BUDGET},
            search_policy_limits={"pop_size": [4, 4], "n_pop": [2, 2], "max_sample_nums": [TOTAL_EVALUATION_BUDGET, TOTAL_EVALUATION_BUDGET]},
        )
    base_manifest = json.loads((base_root / "config_frozen.json").read_text(encoding="utf-8"))["experiment_manifest"]["document"]
    manifest_path = output / "co_pilot_manifest.json"
    pilot = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else build_co_pilot_manifests(base_manifest)
    _write(manifest_path, pilot)
    summaries = []
    groups = selected_groups or ("G0", "G1", "G2", "G3", "G4")
    for group in groups:
        if group not in pilot["groups"]:
            raise RuntimeError(f"unknown_group:{group}")
        summaries.append(_run_group(output, group, pilot["groups"][group]["manifest"], endpoint,
                                    engine_wall_seconds=engine_wall_seconds,
                                    round_wall_seconds=round_wall_seconds))
        _write(output / "pilot_progress.json", {"completed_groups": [item["group"] for item in summaries], "groups": summaries})
        print(json.dumps({"group": group, "status": "completed", "total_solver_attempts": summaries[-1]["report"]["total_solver_attempts"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--groups", nargs="+", choices=["G0", "G1", "G2", "G3", "G4"])
    parser.add_argument("--output-name", default="co_iteration_b_20260918")
    parser.add_argument("--engine-wall-seconds", type=float, default=DEFAULT_ENGINE_WALL_SECONDS)
    parser.add_argument("--round-wall-seconds", type=float, default=DEFAULT_ROUND_WALL_SECONDS)
    args = parser.parse_args()
    raise SystemExit(main(tuple(args.groups) if args.groups else None, output_name=args.output_name,
                          engine_wall_seconds=args.engine_wall_seconds,
                          round_wall_seconds=args.round_wall_seconds))
