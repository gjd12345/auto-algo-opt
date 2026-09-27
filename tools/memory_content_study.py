"""Prepare and start the frozen island605 memory-content study safely."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from agent_skill_loop import client
from agent_skill_loop import session_actions as actions
from agent_skill_loop import session_runtime as runtime
from agent_skill_loop.benchmark.pilot import build_island605_memory_content_manifests
from agent_skill_loop.session_fork import import_collected_first_round


ROOT = Path(__file__).resolve().parents[1]
BATCH = ROOT / "outputs/island605-bp-memory-content-v1"
PLAN = ROOT / "docs/research-loop-v2-memory-content-next-experiment.md"
BASE = ROOT / "outputs/island605-bp-abc-diagnostic-20260926-v4/manifests/seed_1836735484_A.json"
INITIAL_PLAN = ROOT / "outputs/island605-bp-abc-diagnostic-20260926-v4/initial_plan.json"
SEEDS = (2658045112, 2210285944, 3138250455)
ARMS = ("N", "R", "F", "M")


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
    return build_island605_memory_content_manifests(base)


def prepare() -> dict:
    if BATCH.exists():
        raise ValueError("study_batch_already_exists")
    if not PLAN.is_file() or not BASE.is_file() or not INITIAL_PLAN.is_file():
        raise ValueError("study_source_missing")
    manifests = {str(seed): _manifest_set(seed) for seed in SEEDS}
    BATCH.mkdir(parents=True)
    (BATCH / "initial_plan.json").write_bytes(INITIAL_PLAN.read_bytes())
    hashes: dict[str, dict[str, str]] = {}
    for seed in SEEDS:
        hashes[str(seed)] = {}
        for arm in ARMS:
            manifest = manifests[str(seed)]["groups"][arm]["manifest"]
            _save(BATCH / "manifests" / f"seed_{seed}_{arm}.json", manifest)
            hashes[str(seed)][arm] = manifest["experiment_manifest_sha256"]
    prereg = {
        "schema_version": "island605-bp-memory-content-preregistration/v1",
        "plan_ref": PLAN.relative_to(ROOT).as_posix(),
        "plan_sha256": _sha(PLAN),
        "initial_plan_sha256": _sha(BATCH / "initial_plan.json"),
        "seeds": SEEDS,
        "arms": ("R", "F", "M"),
        "order_by_seed": (("R", "F", "M"), ("F", "M", "R"), ("M", "R", "F")),
        "shared_first_round_solver_calls": 25,
        "post_fork_solver_calls_per_arm": 75,
        "max_physical_solver_calls": 750,
        "controller_model": "gpt-5.5",
        "eoh_model": "qwen/deepseek-v4.1-flash",
        "heldout_policy": "locked_no_access_diagnostic",
        "runtime_hash": runtime._runtime_source_hash(),
        "skill_hash": runtime._required_skill_content_hash("init"),
        "manifest_hashes": hashes,
    }
    _save(BATCH / "pre_registration.json", prereg)
    return prereg


def _prereg() -> dict:
    prereg = _json(BATCH / "pre_registration.json")
    if (_sha(PLAN) != prereg["plan_sha256"] or runtime._runtime_source_hash() != prereg["runtime_hash"]
            or runtime._required_skill_content_hash("init") != prereg["skill_hash"]):
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


def _init(seed: int, arm: str) -> Path:
    run = BATCH / "runs" / f"seed_{seed}" / arm
    if run.exists():
        raise ValueError("study_run_already_exists")
    manifest = _manifest(seed, arm)
    memory = arm == "M"
    runtime.initialize_session(
        output=run, operation_id=f"memory-content-v1-init-{seed}-{arm}",
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


def init_source(seed: int) -> dict:
    run = _init(seed, "N")
    state = runtime.read_state(run=run)
    actions.submit_plan(
        run=run, file=BATCH / "initial_plan.json",
        operation_id=f"memory-content-v1-initial-plan-{seed}",
        expected_state_version=state["state_version"],
    )
    return {"run": str(run), "state": runtime.read_state(run=run)["state"]}


def execute_source(seed: int) -> dict:
    _prereg()
    source = BATCH / "runs" / f"seed_{seed}" / "N"
    state = runtime.read_state(run=source)
    if state["state"] != "READY_TO_EXECUTE":
        raise ValueError("source_not_ready_to_execute")
    client.load_local_env()
    actions.execute(
        run=source, operation_id=f"memory-content-v1-execute-shared-{seed}",
        expected_state_version=state["state_version"],
    )
    return {"run": str(source), "state": runtime.read_state(run=source)["state"]}


def init_branches(seed: int) -> dict:
    _prereg()
    source = BATCH / "runs" / f"seed_{seed}" / "N"
    state = runtime.read_state(run=source)
    if state["state"] != "WAITING_FOR_EVALUATION" or state["budgets"]["solver_calls_used"] != 25:
        raise ValueError("shared_first_round_not_collected_exactly")
    results = {}
    for arm in ("R", "F", "M"):
        target = _init(seed, arm)
        results[arm] = import_collected_first_round(
            source=source, target=target,
            operation_id=f"memory-content-v1-import-{seed}-{arm}",
        )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "init-source", "execute-source", "init-branches"))
    parser.add_argument("--seed", type=int)
    args = parser.parse_args()
    if args.action == "prepare":
        result = prepare()
    else:
        if args.seed not in SEEDS:
            parser.error("--seed must be one of the three preregistered seeds")
        result = {"init-source": init_source, "execute-source": execute_source, "init-branches": init_branches}[args.action](args.seed)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
