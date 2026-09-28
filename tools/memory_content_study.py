"""Prepare and start the frozen island605 memory-content study safely."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent_skill_loop import client
from agent_skill_loop import session_actions as actions
from agent_skill_loop import session_runtime as runtime
from agent_skill_loop.benchmark.pilot import build_island605_memory_content_manifests
from agent_skill_loop.session_fork import import_collected_first_round


BATCH = ROOT / "outputs/island605-bp-memory-content-v2"
PLAN = ROOT / "docs/research-loop-v2-memory-content-recovery-frozen.md"
BASE = ROOT / "outputs/island605-bp-abc-diagnostic-20260926-v4/manifests/seed_1836735484_A.json"
INITIAL_PLAN = ROOT / "outputs/island605-bp-abc-diagnostic-20260926-v4/initial_plan.json"
PRIOR_STATUS = Path("C:/Users/24294/.codex/worktrees/research-loop-v2/auto-algo-opt/outputs/island605-bp-memory-content-v1/batch_status.json")
SEEDS = (2658045112, 2210285944, 3138250455)
ARMS = ("N", "R", "F", "M")
CONTROLLER_FILES = (
    "tools/memory_content_brief.py",
    "tools/memory_content_decision_prompt.py",
    "tools/memory_content_controller_call.py",
    "tools/memory_content_host.py",
    "tools/memory_content_study.py",
)


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _save(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest_set(seed: int) -> dict:
    base = _json(BASE)
    base["runtime_hash"] = runtime._runtime_source_hash()
    base["skill_hash"] = runtime._required_skill_content_hash("init")
    base["search_seed"] = seed
    base["extra"]["common_first_round_contract"] = "one_physical_round_then_three_provenance_preserving_branches/v1"
    base["extra"]["controller_brief_policy"] = "bounded_verified_facts_v1"
    base["extra"]["controller_decision_protocol"] = "json_only_separate_reflection_and_plan_v1"
    return build_island605_memory_content_manifests(base)


def prepare() -> dict:
    if (BATCH / "pre_registration.json").exists() or (BATCH / "runs").exists():
        raise ValueError("study_batch_already_exists")
    if not PLAN.is_file() or not BASE.is_file() or not INITIAL_PLAN.is_file() or not PRIOR_STATUS.is_file():
        raise ValueError("study_source_missing")
    prior = _json(PRIOR_STATUS)
    if prior.get("physical_solver_calls_used") != 25 or prior.get("status") != "stopped_infrastructure_failure":
        raise ValueError("prior_failed_attempt_accounting_changed")
    manifests = {str(seed): _manifest_set(seed) for seed in SEEDS}
    BATCH.mkdir(parents=True, exist_ok=True)
    (BATCH / "initial_plan.json").write_bytes(INITIAL_PLAN.read_bytes())
    hashes: dict[str, dict[str, str]] = {}
    for seed in SEEDS:
        hashes[str(seed)] = {}
        for arm in ARMS:
            manifest = manifests[str(seed)]["groups"][arm]["manifest"]
            _save(BATCH / "manifests" / f"seed_{seed}_{arm}.json", manifest)
            hashes[str(seed)][arm] = manifest["experiment_manifest_sha256"]
    prereg = {
        "schema_version": "island605-bp-memory-content-preregistration/v2",
        "plan_ref": PLAN.relative_to(ROOT).as_posix(),
        "plan_sha256": _sha(PLAN),
        "initial_plan_sha256": _sha(BATCH / "initial_plan.json"),
        "seeds": SEEDS,
        "arms": ("R", "F", "M"),
        "order_by_seed": (("R", "F", "M"), ("F", "M", "R"), ("M", "R", "F")),
        "shared_first_round_solver_calls": 25,
        "post_fork_solver_calls_per_arm": 75,
        "max_physical_solver_calls": 750,
        "prior_failed_attempt_solver_calls": 25,
        "max_cumulative_physical_solver_calls": 775,
        "prior_failed_attempt_status_ref": PRIOR_STATUS.as_posix(),
        "prior_failed_attempt_status_sha256": _sha(PRIOR_STATUS),
        "controller_brief_policy": "bounded_verified_facts_v1",
        "controller_brief_max_chars": 16000,
        "controller_decision_protocol": "json_only_separate_reflection_and_plan_v1",
        "controller_model": "gpt-5.5",
        "eoh_model": "qwen/deepseek-v4.1-flash",
        "heldout_policy": "locked_no_access_diagnostic",
        "runtime_hash": runtime._runtime_source_hash(),
        "skill_hash": runtime._required_skill_content_hash("init"),
        "manifest_hashes": hashes,
        "registration_state": "pending_controller_freeze",
    }
    _save(BATCH / "pre_registration.json", prereg)
    return prereg


def freeze_controller() -> dict:
    if (BATCH / "runs").exists():
        raise ValueError("controller_freeze_after_session_start_forbidden")
    prereg = _json(BATCH / "pre_registration.json")
    if prereg.get("registration_state") not in {None, "pending_controller_freeze"}:
        raise ValueError("controller_already_frozen")
    prereg["controller_implementation_hashes"] = {
        ref: _sha(ROOT / ref) for ref in CONTROLLER_FILES
    }
    prereg["registration_state"] = "frozen"
    _save(BATCH / "pre_registration.json", prereg)
    return prereg


def _prereg() -> dict:
    prereg = _json(BATCH / "pre_registration.json")
    if prereg.get("registration_state") != "frozen" or prereg.get("controller_implementation_hashes") != {
        ref: _sha(ROOT / ref) for ref in CONTROLLER_FILES
    }:
        raise ValueError("controller_implementation_identity_changed")
    if (_sha(PLAN) != prereg["plan_sha256"] or runtime._runtime_source_hash() != prereg["runtime_hash"]
            or runtime._required_skill_content_hash("init") != prereg["skill_hash"]
            or _sha(PRIOR_STATUS) != prereg["prior_failed_attempt_status_sha256"]):
        raise ValueError("study_frozen_identity_changed")
    return prereg


def _manifest(seed: int, arm: str) -> dict:
    prereg = _prereg()
    if seed not in prereg["seeds"] or arm not in ARMS:
        raise ValueError("study_seed_or_arm_not_registered")
    path = BATCH / "manifests" / f"seed_{seed}_{arm}.json"
    manifest = _json(path)
    if manifest["experiment_manifest_sha256"] != prereg["manifest_hashes"][str(seed)][arm]:
        raise ValueError("study_manifest_identity_changed")
    return manifest


def _init(seed: int, arm: str, run_name: str | None = None) -> Path:
    run = BATCH / "runs" / f"seed_{seed}" / (run_name or arm)
    if run.exists():
        raise ValueError("study_run_already_exists")
    manifest = _manifest(seed, arm)
    memory = arm == "M"
    runtime.initialize_session(
        output=run, operation_id=f"memory-content-v1-init-{seed}-{run.name}",
        problem="bp_online_island605", benchmark_id="island605_bp",
        benchmark_profile_name="historically_exposed_train_v1",
        experiment_manifest=manifest, inheritance_mode="population_seeds",
        feedback_mode="runtime_facts", eoh_model="qwen/deepseek-v4.1-flash",
        eoh_endpoint="https://model-router.edu-aliyun.com/v1/chat/completions",
        eoh_api_key_env="MODEL_ROUTER_API_KEY", eoh_thinking="disabled",
        repair_mode="off", memory_enabled=memory,
        memory_store=str(run / "memory") if memory else None,
        max_rounds=4, round_budget=25, max_solver_calls=100,
        eoh_max_requests=240, eoh_round_max_requests=60,
        engine_wall_seconds=7200, round_wall_seconds=1800,
        seed=seed, solver_timeout=20, request_timeout=180,
        search_policy_defaults={"pop_size": 4, "n_pop": 2, "max_sample_nums": 100},
        search_policy_limits={"pop_size": [4, 4], "n_pop": [2, 2], "max_sample_nums": [100, 100]},
    )
    return run


def init_source(seed: int, source_name: str = "N") -> dict:
    run = _init(seed, "N", source_name)
    state = runtime.read_state(run=run)
    actions.submit_plan(
        run=run, file=BATCH / "initial_plan.json",
        operation_id=f"memory-content-v1-initial-plan-{seed}-{source_name}",
        expected_state_version=state["state_version"],
    )
    return {"run": str(run), "state": runtime.read_state(run=run)["state"]}


def execute_source(seed: int, source_name: str = "N") -> dict:
    _prereg()
    from tools.memory_content_host import _physical_calls
    if _physical_calls() + 25 > 775:
        raise ValueError("cumulative_physical_budget_exhausted")
    source = BATCH / "runs" / f"seed_{seed}" / source_name
    state = runtime.read_state(run=source)
    if state["state"] != "READY_TO_EXECUTE":
        raise ValueError("source_not_ready_to_execute")
    client.load_local_env()
    actions.execute(
        run=source, operation_id=f"memory-content-v1-execute-shared-{seed}-{source_name}",
        expected_state_version=state["state_version"],
    )
    return {"run": str(source), "state": runtime.read_state(run=source)["state"]}


def collect_source(seed: int, source_name: str = "N") -> dict:
    _prereg()
    source = BATCH / "runs" / f"seed_{seed}" / source_name
    state = runtime.read_state(run=source)
    if (state["state"] != "EXECUTING" or (state.get("task") or {}).get("state") != "EXITED"
            or (state.get("task") or {}).get("terminal_reason") != "ROUND_BUDGET_EXHAUSTED"):
        raise ValueError("shared_first_round_terminal_not_reusable")
    result = actions.collect(
        run=source, operation_id=f"memory-content-v2-collect-shared-{seed}-{source_name}",
        expected_state_version=state["state_version"],
    )
    after = runtime.read_state(run=source)
    if after["state"] != "WAITING_FOR_EVALUATION" or after["budgets"]["solver_calls_used"] != 25:
        raise ValueError("shared_first_round_collection_invalid")
    return {"run": str(source), "result": result["result"], "state": after["state"]}


def init_branches(seed: int, source_name: str = "N") -> dict:
    _prereg()
    source = BATCH / "runs" / f"seed_{seed}" / source_name
    state = runtime.read_state(run=source)
    if state["state"] != "WAITING_FOR_EVALUATION" or state["budgets"]["solver_calls_used"] != 25:
        raise ValueError("shared_first_round_not_collected_exactly")
    if (state.get("task") or {}).get("terminal_reason") != "ROUND_BUDGET_EXHAUSTED":
        raise ValueError("shared_first_round_terminal_not_reusable")
    results = {}
    for arm in ("R", "F", "M"):
        target = BATCH / "runs" / f"seed_{seed}" / arm
        if target.exists():
            target_state = runtime.read_state(run=target)
            if target_state["state"] != "WAITING_FOR_PLAN" or target_state["state_version"] != 1:
                raise ValueError("study_branch_not_fresh_for_import")
        else:
            target = _init(seed, arm)
        results[arm] = import_collected_first_round(
            source=source, target=target,
            operation_id=f"memory-content-v1-import-{seed}-{arm}",
        )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "freeze-controller", "init-source", "execute-source", "collect-source", "init-branches"))
    parser.add_argument("--seed", type=int)
    parser.add_argument("--source-name", default="N")
    args = parser.parse_args()
    if args.action == "prepare":
        result = prepare()
    elif args.action == "freeze-controller":
        result = freeze_controller()
    else:
        if args.seed not in SEEDS:
            parser.error("--seed must be one of the three preregistered seeds")
        if not re.fullmatch(r"N(?:_retry[1-9][0-9]*)?", args.source_name):
            parser.error("--source-name must be N or N_retryN")
        result = {"init-source": init_source, "execute-source": execute_source,
                  "collect-source": collect_source, "init-branches": init_branches}[args.action](args.seed, args.source_name)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
