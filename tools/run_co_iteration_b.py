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
BENCHMARK_PROFILE = "obp_search_mini"
TOTAL_EVALUATION_BUDGET = 100
ROUND_EVALUATION_BUDGET = 50
# Provider requests include the probe and failed/truncated generations.  Keep
# this budget independent from evaluator attempts so transient provider output
# does not terminate the experiment before EoH can use its 100 evaluations.
TOTAL_REQUEST_BUDGET = 240
ROUND_REQUEST_BUDGET = 120
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


def _plan(
    group: str,
    round_id: int,
    state: dict[str, Any],
    *,
    previous_facts: dict[str, Any] | None,
    memory_basis: list[str],
) -> dict[str, Any]:
    progress = group in {"G2", "G3", "G4"}
    window = ((previous_facts or {}).get("search_progress") or {}).get("window") or {}
    duplicate_rate = window.get("behavior_duplicate_rate")
    valid_yield = window.get("valid_generation_yield")
    if group == "G0":
        direction = "Run the frozen official EoH search with a neutral host Plan."
        operations = [{
            "type": "preserve",
            "target": "search mechanism",
            "mechanism": "let official EoH choose operators and parents without adaptive host guidance",
        }]
    elif round_id == 1:
        direction = (
            "Explore several distinct online bin-selection mechanisms, including stable bin-order, "
            "residual-capacity fit, and item-dependent hybrids."
        )
        operations = [{
            "type": "replace",
            "target": "priority mechanism family",
            "mechanism": "generate behaviorally distinct hypotheses rather than coefficient-only variants",
        }]
    elif progress and isinstance(duplicate_rate, (int, float)) and duplicate_rate >= 0.5:
        direction = (
            "Previous behavior was highly duplicated; switch mechanism family and test stable "
            "first-feasible or item-dependent bin-order rules instead of another best-fit variant."
        )
        operations = [{
            "type": "replace",
            "target": "priority mechanism family",
            "mechanism": "move from repeated residual-capacity scoring to a distinct stable-order hypothesis",
        }]
    else:
        direction = (
            "Use the previous verified objectives and validity results to refine a distinct legal "
            "online bin-selection mechanism."
        )
        operations = [{
            "type": "replace",
            "target": "priority mechanism",
            "mechanism": "test a bounded structural alternative supported by the previous round facts",
        }]
    plan = {
        "round_id": round_id,
        "direction": direction,
        "operations": operations,
        "preserve": "OBP suite, MetricSpec, model, endpoint, inheritance, repair setting and evaluator budget",
        # G0 is the record-only arm: it must not consume or expose runtime
        # feedback.  The other arms receive the previous round's verified
        # evaluation reference when the runtime makes one available.
        "feedback_basis": state.get("feedback_basis") if group != "G0" else None,
        "memory_basis": memory_basis,
        "reference_skill_ref": None,
        "hypothesis": "A structurally distinct legal priority rule may reduce the frozen best-fit baseline gap; this is unproven.",
    }
    if group == "G4":
        plan["search_intent"] = {"phase": "exploration" if round_id == 1 else "exploitation"}
    if progress and round_id > 1:
        plan["reasoning_summary"] = (
            "Use only the previous Runtime-verified SearchProgress facts. "
            f"Observed behavior_duplicate_rate={duplicate_rate!r}, valid_generation_yield={valid_yield!r}. "
            "Official EoH still selects parents and operators."
        )
    return plan


def _read_previous_facts(root: Path, round_id: int) -> dict[str, Any] | None:
    if round_id <= 1:
        return None
    path = root / f"rounds/round_{round_id - 1:04d}/evaluation_facts.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def _memory_basis(root: Path, group: str) -> list[str]:
    if group not in {"G3", "G4"}:
        return []
    result = actions.memory_search(
        run=root,
        query="OBP online priority search progress duplicate behavior",
        limit=2,
    )["result"]
    adopted: list[str] = []
    for item in result.get("memories") or []:
        reference = item.get("reference")
        if not isinstance(reference, str):
            continue
        page = actions.memory_read(run=root, reference=reference, limit=8000)["result"]
        if page.get("complete_memory_consumption"):
            adopted.append(reference)
    return adopted


def _evaluation(group: str, round_id: int, facts: dict[str, Any]) -> dict[str, Any]:
    generated = [
        item for item in facts.get("candidates") or []
        if item.get("origin") in {"generated", "generated_repair"}
    ]
    valid = [item for item in generated if item.get("valid") is True]
    evidence_ref = facts.get("execution_delta", {}).get("ref") or facts["evidence_refs"][0]
    window = (facts.get("search_progress") or {}).get("window") or {}
    if group in {"G3", "G4"} and round_id == 1:
        memory_action: dict[str, Any] = {
            "kind": "insight",
            "name": f"iteration_b_{group.lower()}_round1_progress",
            "description": "Scoped OBP search-progress evidence for the next round of this controlled run.",
            "project": "obp_online",
            "scene": "priority",
            "body": (
                "**Why:** On the frozen OBP search-mini training suite, round 1 observed "
                f"{len(valid)} valid generated candidates out of {len(generated)} and behavior duplicate rate "
                f"{window.get('behavior_duplicate_rate')!r}. This is one-run evidence, not a universal rule.\n\n"
                "**How to apply:** In the next round, use this only as a reason to prefer a structurally distinct "
                "priority mechanism when duplication is high. Keep the same suite, evaluator, budget, and official "
                "EoH parent/operator authority."
            ),
            "evidence_ref": evidence_ref,
        }
    elif group in {"G3", "G4"}:
        memory_action = {"kind": "none", "reason": "No additional reusable finding beyond the round-1 scoped insight."}
    else:
        memory_action = {"kind": "disabled"}
    return {
        "plan_alignment": "unknown",
        "observations": [{
            "claim": f"Runtime recorded {len(valid)} valid generated candidates out of {len(generated)} in round {round_id}.",
            "evidence_refs": [evidence_ref],
        }],
        "hypotheses": [],
        "next_search_advice": {
            "direction": "Use the verified duplicate rate and objective deltas to choose the next bounded mechanism family."
        },
        "memory_action": memory_action,
    }


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
        eoh_thinking="disabled",
        benchmark_id="eohs_v1",
        benchmark_profile_name=BENCHMARK_PROFILE,
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
        previous_facts = _read_previous_facts(root, round_id)
        memory_basis = _memory_basis(root, group) if manifest["memory_enabled"] else []
        state = db.read_state(run=root)
        plan_path = base / "plans" / group / f"plan_{round_id:04d}.json"
        _write(plan_path, _plan(
            group,
            round_id,
            state,
            previous_facts=previous_facts,
            memory_basis=memory_basis,
        ))
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
        evaluation = _evaluation(group, round_id, facts)
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
            eoh_thinking="disabled",
            benchmark_id="eohs_v1",
            benchmark_profile_name=BENCHMARK_PROFILE,
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
