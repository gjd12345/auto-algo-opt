"""Run the Wave 2 C2 timing audit and B1 stopping comparison."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from collections.abc import Mapping, Sequence
from contextlib import closing
from dataclasses import replace
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from agent_skill_loop.client import ProviderFailure, load_local_env
from agent_skill_loop.cvrp_workbench.solvers import evaluate_algorithm_on_instance
from agent_skill_loop.file_lock import exclusive_file_lock
from agent_skill_loop.interface_design.blind_eval_m5 import (
    M5_BLIND_COMMITMENT_PATH,
    M5_BLIND_SUITE_ID,
    _m5_custody_dir,
)
from agent_skill_loop.interface_design.blind_eval_m32 import read_verified_milestone_blind_payload
from agent_skill_loop.interface_design.contracts import FrozenInterfaceSolver, sha256_text
from agent_skill_loop.interface_design.planner import build_interface_design
from agent_skill_loop.interface_design.runtime import evaluate_frozen_interface_solver
from agent_skill_loop.interface_design.session_baseline import load_dev_or_public_suite
from agent_skill_loop.interface_design.templates import get_template_spec
from agent_skill_loop.milestone_checkpoint import settle_attempt_provenance
from agent_skill_loop.request_budget import PersistentRequestBudget
from research_agent.contracts import AgentConfig, atomic_write_json, atomic_write_text, sha256_file
from research_agent.loop import (
    _build_initial_baseline_solver,
    _read_stopping_provenance,
    evaluate_global_stopping_decision,
    run_research_agent,
)
from research_agent.tools.session_tools import SessionRunnerTool
from tools.multi_task_mux import _session_lock
from tools.run_external_baselines_2026 import (
    BUDGETS,
    EXTERNAL_COUNTS,
    MODEL,
    PARATERA_ENDPOINT,
    REQUEST_CAP,
    SEEDS,
    _load_external,
    _paired,
    _score,
    _summary,
    _target_instances,
)

DEFAULT_OUTPUT = REPO / "experiments" / "milestone6_wave2_c2_b1"
TEMPLATE_ID = "cvrp_parallel_merge_static"
TEMPLATE_VERSION = "v2"
BASELINE = "cw_relocate_2opt"
LIVE_BUDGET_MS = 500
BOOTSTRAP_SAMPLES = 10_000
ARMS = {
    "no_early_stop": ("off", False),
    "naive_patience_24": ("naive_patience", False),
    "stagnation_restart_only": ("off", True),
    "risk_bounded_adaptive_stop": ("risk_bounded_beta_geom", False),
}
M5_SNAPSHOTS = {
    "m5_ds_legacy_s20261128": "legacy_baseline_500ms_20261128.json",
    "m5_ds_whitelist_s20261127": "whitelist_latency_500ms_20261127.json",
    "m5_qwen_ctrl_s20261125": "model2_ctrl_full_500ms_20261125.json",
}
PRIVATE_KEYS = frozenset({
    "depot", "coordinates", "customer_coordinates", "demands", "distance_matrix",
    "sealed_seed_token", "seed_token", "items", "item_sizes", "routes",
})


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _digest(payload: Any) -> str:
    return sha256_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False))


def _check_public(payload: Any) -> None:
    if isinstance(payload, Mapping):
        if PRIVATE_KEYS.intersection(payload):
            raise ValueError("private_instance_fields_in_wave2_output")
        for value in payload.values():
            _check_public(value)
    elif isinstance(payload, (tuple, list)):
        for value in payload:
            _check_public(value)


def _write_public(path: Path, payload: Mapping[str, Any]) -> None:
    _check_public(payload)
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def _output_path(out_dir: Path) -> Path:
    resolved = out_dir.resolve()
    if resolved.is_relative_to(REPO) and not (
        resolved.is_relative_to(DEFAULT_OUTPUT) or resolved.is_relative_to(REPO / "build")
    ):
        raise ValueError("wave2_output_must_use_wave2_or_build_directory")
    if any(part.casefold().startswith(".agent_skill_custody") or part.casefold() == ".secrets" for part in resolved.parts):
        raise ValueError("wave2_output_cannot_use_custody_directory")
    return resolved


def _static_v2_solvers() -> dict[str, FrozenInterfaceSolver]:
    old = get_template_spec(TEMPLATE_ID, "v1")
    new = get_template_spec(TEMPLATE_ID, TEMPLATE_VERSION)
    design = build_interface_design(TEMPLATE_ID, TEMPLATE_VERSION, postprocess_mode="relocate_2opt")
    design = replace(design, template_options={**design.template_options, "positive_savings_only": True})
    code = design.baseline_hook_code
    cw = FrozenInterfaceSolver(
        solver_id="cw_static", display_name="Classical Clarke–Wright static v2", problem_family="cvrp",
        paradigm=design.paradigm, template_id=TEMPLATE_ID, template_version=TEMPLATE_VERSION,
        template_source_sha256=new.template_source_sha256, postprocess_mode=design.postprocess_mode,
        template_options=dict(design.template_options), hook_name=design.hook_name,
        hook_code=code, hook_code_sha256=sha256_text(code), design_sha256=design.design_sha256,
        origin_run="m6_wave2_c2", kb_release_id="m6_wave2_c2", protocol_id=new.effective_protocol_id,
    )
    result = {cw.solver_id: cw}
    snapshots = REPO / "experiments" / "milestone5_paratera" / "roster_snapshots"
    for label, filename in M5_SNAPSHOTS.items():
        raw = _read_json(snapshots / filename)
        source = FrozenInterfaceSolver.from_dict(raw.get("frozen_solver", raw))
        if (
            (source.template_id, source.template_version, source.template_source_sha256)
            != (TEMPLATE_ID, "v1", old.template_source_sha256)
            or source.hook_name != new.hook_name or source.hook_specs != new.hook_specs
            or source.hook_code_sha256 != sha256_text(source.hook_code)
        ):
            raise ValueError(f"invalid_wave2_source_solver:{label}")
        wrapped_design = build_interface_design(TEMPLATE_ID, TEMPLATE_VERSION, postprocess_mode=source.postprocess_mode)
        wrapped_design = replace(wrapped_design, template_options=dict(source.template_options))
        result[label] = replace(
            source, solver_id=label, display_name=f"{source.display_name} (static v2)",
            template_version=TEMPLATE_VERSION, template_source_sha256=new.template_source_sha256,
            design_sha256=wrapped_design.design_sha256, description="Wave 2 static v2 wrapper for a frozen M5 hook.",
        )
    return result


def _external_suites() -> dict[str, dict[str, Any]]:
    return {suite["suite_id"]: {**suite, "instances": _target_instances(suite)} for suite in _load_external()}


def _evaluate_cached(
    label: str,
    solver: FrozenInterfaceSolver | str,
    suite: Mapping[str, Any],
    budget_ms: int,
    cache_dir: Path,
) -> list[dict[str, Any]]:
    suite_id = suite["suite_id"]
    policy = suite.get("evaluation_vehicle_limit_policy", "free_fleet_min_k_lb")
    distance = suite["distance_convention"]
    instances = suite["instances"]
    instance_ids = [instance["instance_id"] for instance in instances]
    if not instance_ids or len(set(instance_ids)) != len(instance_ids):
        raise ValueError(f"empty_or_duplicate_wave2_suite:{suite_id}")
    source_paths = (
        Path(__file__),
        REPO / "agent_skill_loop/interface_design/runtime.py",
        REPO / "agent_skill_loop/cvrp_workbench/solvers.py",
        REPO / "tools/run_external_baselines_2026.py",
    )
    identity = {
        "schema_version": "m6-wave2-solve-cache/v1", "solver_id": label, "suite_id": suite_id,
        "budget_ms": budget_ms, "workers": 1, "distance_convention": distance, "vehicle_limit_policy": policy,
        "solver_sha256": _digest(solver.to_dict() if isinstance(solver, FrozenInterfaceSolver) else solver),
        "instances_sha256": _digest(instances),
        "evaluation_sha256": _digest([sha256_file(path) for path in source_paths]),
    }
    cache_path = cache_dir / f"{label}__{suite_id}__{budget_ms}.json"
    if cache_path.is_file():
        cached = _read_json(cache_path)
        _check_public(cached)
        rows = cached.get("rows", [])
        if cached.get("identity") == identity and [row["instance_id"] for row in rows] == instance_ids:
            return rows

    kwargs = {"distance_convention": distance, "vehicle_limit_policy": policy, "enforce_wall_deadline": True}
    rows = []
    for instance in instances:
        if isinstance(solver, FrozenInterfaceSolver):
            result = evaluate_frozen_interface_solver(solver, instance, solve_deadline_ms=budget_ms, **kwargs)
        else:
            result = evaluate_algorithm_on_instance(solver, instance, time_budget_ms=budget_ms, record_trace=False, **kwargs)
        row = _score(instance, result, policy, budget_ms)
        strict = bool(row["completed"] and row["returned_before_deadline"] is True)
        rows.append({
            **row,
            "completed": strict,
            "strict_completed_before_deadline": strict,
            "scored_objective": row["objective"] if strict else 2 * row["reference_objective"],
            "voluntary_anytime_return": result.get("voluntary_anytime_return") is True,
            "local_search_truncated": result.get("local_search_truncated") is True,
        })
    _write_public(cache_path, {"identity": identity, "rows": rows})
    return rows


def _exact_k(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Project the same returned routes onto the exact fleet target."""
    projected = []
    for row in rows:
        matches = row["exact_vehicle_count"] is True
        completed = row["completed"] and matches
        projected.append({
            **row,
            "feasible": row["feasible"] and matches,
            "completed": completed,
            "strict_completed_before_deadline": completed,
            "returned_before_deadline": row["returned_before_deadline"] and matches,
            "feasible_before_deadline": row["feasible_before_deadline"] and matches,
            "scored_objective": row["objective"] if completed else 2 * row["reference_objective"],
        })
    return projected


def _compare(
    rows_by_solver: Mapping[str, Sequence[Mapping[str, Any]]], *, seed: int,
) -> dict[str, Any]:
    groups = {"free_fleet": rows_by_solver, "exact_k": {label: _exact_k(rows) for label, rows in rows_by_solver.items()}}
    return {
        lane: {
            "solvers": {label: _summary(rows) for label, rows in group.items()},
            "paired": {
                metric: _paired(group, common_completed=common, samples=BOOTSTRAP_SAMPLES, seed=seed)
                for metric, common in (("overall", False), ("common_completed", True))
            },
        }
        for lane, group in groups.items()
    }


def run_c2_offline(out_dir: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    out_dir = _output_path(out_dir) / "c2_offline"
    suites = _external_suites()
    solvers = {BASELINE: BASELINE, **_static_v2_solvers()}
    expected = sum(EXTERNAL_COUNTS.values())
    by_budget: dict[str, Any] = {}
    for budget in BUDGETS:
        by_suite = {suite_id: {} for suite_id in suites}
        pooled = {label: [] for label in solvers}
        for label, solver in solvers.items():
            print(f"C2 {budget} ms: {label}", flush=True)
            for suite_id, suite in suites.items():
                rows = _evaluate_cached(label, solver, suite, budget, out_dir / "cache")
                by_suite[suite_id][label] = _summary(rows)
                pooled[label].extend(rows)
        acceptance = {
            label: {
                "returned_before_deadline": sum(row["returned_before_deadline"] is True for row in rows),
                "expected": expected,
                "strict_completed_before_deadline": sum(row["strict_completed_before_deadline"] for row in rows),
            }
            for label, rows in pooled.items() if label != BASELINE
        }
        passed = all(row["strict_completed_before_deadline"] == expected for row in acceptance.values())
        by_budget[str(budget)] = {
            "strict_return_acceptance_passed": passed, "strict_returns": acceptance,
            "by_suite_free_fleet": by_suite, **_compare(pooled, seed=SEEDS[0]),
        }
    report = {
        "schema_version": "m6-c2-offline-430/v1", "workers": 1, "suite_counts": EXTERNAL_COUNTS,
        "n_instances": expected,
        "strict_return_acceptance_passed": all(item["strict_return_acceptance_passed"] for item in by_budget.values()),
        "baseline": BASELINE, "exact_k_method": "project_returned_free_fleet_routes_onto_exact_target",
        "bootstrap_samples": BOOTSTRAP_SAMPLES, "budgets_ms": by_budget,
    }
    _write_public(out_dir / "c2_offline_430_report.json", report)
    return report


def _run_id(arm: str, seed: int) -> str:
    return f"m6_b1_{arm}_s{seed}"


def _arm_config(
    out_dir: Path, arm: str, seed: int, *, mode: str, endpoint: str, api_key_env: str,
) -> AgentConfig:
    global_mode, restart = ARMS[arm]
    live = mode == "live"
    run_id = _run_id(arm, seed)
    return AgentConfig(
        run_id=run_id,
        output_dir=str(out_dir / (run_id if live else arm)),
        arm_id=arm,
        search_seed=seed,
        initial_template_id=TEMPLATE_ID,
        template_version=TEMPLATE_VERSION,
        allowed_templates=(TEMPLATE_ID,),
        allowed_postprocess_modes=("relocate_2opt",),
        initial_postprocess_mode="relocate_2opt",
        use_benchmark_dev_suite=live,
        dev_instance_count=24 if live else 2,
        dev_instance_size=20,
        instance_time_budget_ms=LIVE_BUDGET_MS,
        total_request_cap=REQUEST_CAP,
        max_rounds=24,
        outer_requests_per_round_cap=4 if live else 1,
        outer_reflect_cap=2 if live else 1,
        eoh_pop_size=2,
        eoh_n_pop=1,
        eoh_max_sample_nums=8,
        strict_checkpoint_barriers=True,
        checkpoint_budgets=(REQUEST_CAP,),
        planner_model=MODEL,
        eoh_model=MODEL,
        endpoint=endpoint,
        api_key_env=api_key_env,
        mode=mode,
        request_timeout_s=90.0 if live else 5.0,
        wall_seconds=14400.0 if live else 600.0,
        tools_enabled=live,
        kb_enabled=live,
        archive_feedback_enabled=live,
        enable_c2_joint_screen=live,
        global_early_stop_mode=global_mode,
        early_stop_no_jump_requests=6 if restart else None,
        basin_restart_on_stagnation=restart,
    )


class _ScriptedSession(SessionRunnerTool):
    """Replay one small jump, then tied evaluations through the durable request ledger."""

    _instances = [{
        "instance_id": "wave2_mock_line", "depot": [0, 0], "customer_coordinates": [[5, 0], [10, 0]],
        "demands": [1, 1], "capacity": 2, "size": 2, "reference_objective": 20.0,
    }]
    _metrics = {
        "all_feasible": True, "completion_rate": 1.0, "valid_count": 1, "instance_count": 1,
        "penalized_mean_tour_length": 19.9, "valid_only_mean_tour_length": 19.9,
    }

    def __init__(self, *, run_dir: Path, config: AgentConfig, budget: PersistentRequestBudget) -> None:
        super().__init__(run_dir=run_dir, config=config, budget=budget)
        self._solver = replace(_build_initial_baseline_solver(config), solver_id="wave2_mock_plateau").to_dict()

    def ensure_initialized(self) -> dict[str, Any]:
        path = self.session_dir / "dev_suite.json"
        if not path.is_file():
            atomic_write_json(path, {"instances": self._instances})
        return {}

    def run_round(self, *, round_id: int, fresh_template: bool, **_: Any) -> dict[str, Any]:
        before = self.budget.used
        global_patience = (
            self.config.global_early_stop_mode == "naive_patience" and not self.config.basin_restart_on_stagnation
        )
        limit = self.config.early_stop_no_jump_requests
        # A fresh basin compares the first scripted candidate with the local baseline.
        local_improvements = int(round_id == 1 or fresh_template)
        attempts = min(self.config.eoh_max_sample_nums, limit + local_improvements) if limit else self.config.eoh_max_sample_nums
        inner_stop = False
        for _ in range(attempts):
            slot = self.budget.reserve(purpose="eoh_generation", problem="cvrp", model=self.config.eoh_model)
            if slot is None:
                break
            if slot.attempt_token is None:
                raise RuntimeError("wave2_mock_candidate_provenance_missing")
            self.budget.mark_sent(slot)
            self.budget.finish(slot, "complete", status=200)
            settle_attempt_provenance(
                self.budget.ledger_path, attempt_token=slot.attempt_token, generation_status="valid_candidate",
                eval_id=f"wave2_mock_{slot.index}", code_sha256=self._solver["hook_code_sha256"],
                solver_manifest=self._solver, validation_passed=True, dev_eval=self._metrics,
                dev_suite_hash=_digest(self._instances), solve_budget_ms=self.config.instance_time_budget_ms,
            )
            if global_patience:
                used = self.budget.used
                decision = evaluate_global_stopping_decision(
                    self.config, t=used, candidate_provenance=_read_stopping_provenance(self.budget, used),
                )
                if decision["stop"]:
                    inner_stop = True
                    break
        after = self.budget.used
        exhausted = self.budget.remaining == 0
        inner_stop = not exhausted and (inner_stop or (limit is not None and after - before - local_improvements >= limit))
        return {
            "requests_before": before, "requests_after": after, "frozen_solver": self._solver,
            "dev_eval": self._metrics, "session_status": "STOPPED" if exhausted else "RUNNING",
            "stop_reason": "stagnation_early_stop" if inner_stop else "eoh_completed",
            "fresh_template_applied": fresh_template,
            **({"stagnation_trigger_ordinal": after} if inner_stop else {}),
        }

    def memory_consumption(self, round_id: int) -> dict[str, Any]:
        return {"round_id": round_id, "injected_refs": [], "gateway_refs": []}


def run_b1_mock(out_dir: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    mock_dir = _output_path(out_dir) / "b1_mock"
    arms = {}
    decisions = []
    for arm, (global_mode, restart) in ARMS.items():
        config = _arm_config(mock_dir, arm, SEEDS[0], mode="mock", endpoint="mock://local", api_key_env="PARATERA_API_KEY")
        run_dir = Path(config.output_dir)
        summary = run_research_agent(
            config, resume=(run_dir / "agent_checkpoint.json").is_file(), session_factory=_ScriptedSession,
        )
        phase = summary["final_phase"]
        realized = summary["realized_request_spend"]
        champion = summary["best_solver_manifest_ref"]
        decision_path = run_dir / "stopping_decisions.jsonl"
        arm_rows = [json.loads(line) for line in decision_path.read_text(encoding="utf-8").splitlines()] if decision_path.is_file() else []
        decisions.extend({**row, "arm": arm} for row in arm_rows)
        started_stopping = global_mode != "off"
        passed = bool(champion and (run_dir / champion).is_file()) and (
            (phase == "early_stopped_global" and realized < REQUEST_CAP and bool(arm_rows))
            if started_stopping else (phase != "early_stopped_global" and realized == REQUEST_CAP)
        ) and (not restart or summary["restart_count"] > 0)
        arms[arm] = {
            "phase": phase, "stop_reason": summary["stop_reason"], "realized_request_spend": realized,
            "best_solver_manifest_ref": champion, "restart_count": summary["restart_count"],
            "stopping_decision_count": len(arm_rows), "passed": passed,
        }
    _check_public(decisions)
    atomic_write_text(mock_dir / "stopping_decisions.jsonl", "".join(json.dumps(row, allow_nan=False) + "\n" for row in decisions))
    report = {
        "schema_version": "m6-b1-mock/v1", "seed": SEEDS[0], "total_request_cap": REQUEST_CAP,
        "arms": arms, "passed": all(row["passed"] for row in arms.values()),
        "simulation": "scripted_inner_session_with_production_controller_and_request_ledger",
    }
    _write_public(mock_dir / "b1_mock_report.json", report)
    return report


def build_mux_manifest(
    out_dir: Path = DEFAULT_OUTPUT, *, endpoint: str = PARATERA_ENDPOINT, api_key_env: str = "PARATERA_API_KEY",
) -> dict[str, Any]:
    out_dir = _output_path(out_dir)
    panes = []
    for arm in ARMS:
        for seed in SEEDS:
            panes.append({
                "id": _run_id(arm, seed),
                "cwd": str(REPO),
                "command": [
                    sys.executable, str(Path(__file__).resolve()), "--stage", "b1_cell",
                    "--output-dir", str(out_dir), "--arm", arm, "--seed", str(seed),
                    "--endpoint", endpoint, "--api-key-env", api_key_env, "--resume",
                ],
            })
    return {"model": MODEL, "request_cap": REQUEST_CAP, "template_version": TEMPLATE_VERSION, "panes": panes}


def _seed_common_start(live_dir: Path, seed: int, *, endpoint: str, api_key_env: str) -> dict[str, Any]:
    path = live_dir / f"common_start_s{seed}.json"
    if path.is_file():
        return _read_json(path)
    deadline = time.monotonic() + 60.0
    while True:
        try:
            with exclusive_file_lock(live_dir / f".common_start_s{seed}.lock", busy=f"common_start_busy:{seed}"):
                if path.is_file():
                    return _read_json(path)
                cfg = _arm_config(live_dir, "no_early_stop", seed, mode="live", endpoint=endpoint, api_key_env=api_key_env)
                baseline_solver = _build_initial_baseline_solver(cfg)
                suite = load_dev_or_public_suite(cfg.dev_suite_id, split=cfg.dev_split, role="diagnostic_interactive")
                dist_conv = str(suite.get("distance_convention") or "not_applicable")
                veh_pol = str(suite.get("vehicle_limit_policy") or "not_applicable")
                outer_s = max(5.0, float(cfg.instance_time_budget_ms) / 1000.0 + 3.0)
                raw_records = [
                    evaluate_frozen_interface_solver(
                        baseline_solver,
                        inst,
                        distance_convention=dist_conv,
                        vehicle_limit_policy=veh_pol,
                        solve_deadline_ms=cfg.instance_time_budget_ms,
                        outer_timeout_s=outer_s,
                        protocol_id=suite.get("protocol_id"),
                    )
                    for inst in suite["instances"]
                ]
                records = [{k: v for k, v in rec.items() if k != "routes"} for rec in raw_records]
                valid_objs: list[float] = []
                penalized_objs: list[float] = []
                for inst, rec in zip(suite["instances"], records, strict=True):
                    obj = rec.get("objective")
                    if obj is None:
                        obj = rec.get("tour_length")
                    if rec.get("valid") is True and rec.get("completed", True) is True and obj is not None and not isinstance(obj, bool):
                        val = float(obj)
                        valid_objs.append(val)
                        penalized_objs.append(val)
                    else:
                        ref_obj = inst.get("reference_objective")
                        penalized_objs.append(2.0 * float(ref_obj) if isinstance(ref_obj, (int, float)) and float(ref_obj) > 0 else 100.0)
                solve_times = [float(r["solve_ms"]) for r in records if r.get("solve_ms") is not None]
                n_total = len(records)
                valid_count = len(valid_objs)
                valid_mean = round(sum(valid_objs) / valid_count, 8) if valid_count else None
                pen_mean = round(sum(penalized_objs) / max(1, n_total), 8)
                dev_suite_hash = sha256_text(
                    json.dumps(suite["instances"], ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
                )
                payload = {
                    "schema_version": "m6-b1-common-start/v1",
                    "seed": seed,
                    "dev_suite_hash": dev_suite_hash,
                    "frozen_solver": baseline_solver.to_dict(),
                    "baseline_dev_eval": {
                        "suite_id": cfg.dev_suite_id,
                        "protocol_id": suite.get("protocol_id"),
                        "valid_count": valid_count,
                        "instance_count": n_total,
                        "completion_rate": round(valid_count / max(1, n_total), 6),
                        "all_feasible": bool(n_total > 0 and valid_count == n_total),
                        "failure_penalty_policy": "2x_reference_objective",
                        "valid_only_mean_objective": valid_mean,
                        "penalized_mean_objective": pen_mean,
                        "mean_objective": pen_mean,
                        "valid_only_mean_tour_length": valid_mean,
                        "penalized_mean_tour_length": pen_mean,
                        "mean_tour_length": pen_mean,
                        "solve_ms_mean": round(sum(solve_times) / len(solve_times), 4) if solve_times else None,
                        "records": records,
                    },
                }
                _check_public(payload)
                atomic_write_json(path, payload)
                return payload
        except ValueError as exc:
            if str(exc) != f"common_start_busy:{seed}" or time.monotonic() >= deadline:
                raise
            if path.is_file():
                return _read_json(path)
            time.sleep(0.25)


def _read_champion(live_dir: Path, arm: str, seed: int) -> tuple[FrozenInterfaceSolver, dict[str, Any]]:
    run_id = _run_id(arm, seed)
    run_dir = (live_dir / run_id).resolve()
    persisted = AgentConfig.from_dict(_read_json(run_dir / "agent_config.json"))
    expected = _arm_config(live_dir, arm, seed, mode="live", endpoint=persisted.endpoint, api_key_env=persisted.api_key_env)
    if persisted != expected or persisted.endpoint.startswith("mock://"):
        raise ValueError(f"invalid_wave2_live_config:{run_id}")
    summary = _read_json(run_dir / "research_summary.json")
    phase = summary["final_phase"]
    realized = summary["realized_request_spend"]
    if summary["run_id"] != run_id or phase not in {"completed", "budget_stopped", "early_stopped_global"}:
        raise ValueError(f"wave2_live_run_not_terminal:{run_id}")
    db_uri = (run_dir / "agent_budget.sqlite3").resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(db_uri, uri=True)) as db:
        requests = db.execute("SELECT idx, state FROM budget_requests WHERE run_id=? ORDER BY idx", (run_id,)).fetchall()
        if not 0 < realized <= REQUEST_CAP or len(requests) != realized or any(
            ordinal != expected_ordinal or state in {"reserved", "sent"}
            for expected_ordinal, (ordinal, state) in enumerate(requests, 1)
        ):
            raise ValueError(f"wave2_champion_ledger_mismatch:{run_id}")
        if realized == REQUEST_CAP:
            checkpoint = run_dir / "checkpoints" / f"frozen_checkpoint_{REQUEST_CAP}.json"
            record = db.execute(
                "SELECT state, payload_sha256, settled_through_ordinal FROM milestone_checkpoints WHERE run_id=? AND ckpt_budget=?",
                (run_id, REQUEST_CAP),
            ).fetchone()
            digest = sha256_file(checkpoint)
            if record != ("sealed", digest, REQUEST_CAP):
                raise ValueError(f"wave2_champion_checkpoint_unsealed:{run_id}")
            payload = _read_json(checkpoint)["frozen_solver"]
        else:
            if phase not in {"early_stopped_global", "completed"}:
                raise ValueError(f"wave2_run_ended_below_cap_without_valid_completion:{run_id}")
            ref = Path(summary["best_solver_manifest_ref"])
            path = (run_dir / ref).resolve()
            if ref.is_absolute() or not path.is_relative_to(run_dir):
                raise ValueError(f"wave2_champion_reference_outside_run:{run_id}")
            payload = _read_json(path)
            digest = sha256_file(path)
            row = db.execute(
                "SELECT solver_manifest_json FROM candidate_provenance WHERE run_id=? AND global_ordinal<=? AND eligible=1 "
                "ORDER BY dev_all_feasible DESC, dev_completion_rate DESC, dev_penalized_mean ASC, global_ordinal ASC LIMIT 1",
                (run_id, realized),
            ).fetchone()
            if row is None or json.loads(row[0]) != payload:
                raise ValueError(f"wave2_below_cap_champion_provenance_mismatch:{run_id}")
    solver = FrozenInterfaceSolver.from_dict(payload)
    template = get_template_spec(TEMPLATE_ID, TEMPLATE_VERSION)
    if (
        (solver.template_id, solver.template_version, solver.template_source_sha256)
        != (TEMPLATE_ID, TEMPLATE_VERSION, template.template_source_sha256)
        or solver.hook_name != template.hook_name or solver.hook_code_sha256 != sha256_text(solver.hook_code)
        or solver.postprocess_mode != "relocate_2opt"
    ):
        raise ValueError(f"wave2_champion_template_mismatch:{run_id}")
    return solver, {"requests_used": realized, "phase": phase, "champion_source_sha256": digest}


def pareto_frontier(points: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Lower spend and penalized blind gap are preferable, with more strict completions."""
    def coordinates(point: Mapping[str, Any]) -> tuple[float, float, float]:
        return (point["requests_used"], point["blind_120_quality"], -point["strict_completed_before_deadline"])

    vectors = [coordinates(point) for point in points]
    frontier = []
    for point, vector in zip(points, vectors, strict=True):
        dominated = any(
            other != vector and all(left <= right for left, right in zip(other, vector, strict=True))
            for other in vectors
        )
        if not dominated:
            frontier.append(dict(point))
    return sorted(frontier, key=coordinates)


def run_eval(out_dir: Path = DEFAULT_OUTPUT, *, custody_dir: Path | None = None) -> dict[str, Any]:
    out_dir = _output_path(out_dir)
    live_dir = out_dir / "b1_live"
    eval_dir = out_dir / "eval"
    solvers = {}
    metadata = {}
    for seed in SEEDS:
        for arm in ARMS:
            cell = _run_id(arm, seed)
            solvers[cell], metadata[cell] = _read_champion(live_dir, arm, seed)

    commitment_sha = sha256_file(M5_BLIND_COMMITMENT_PATH)
    roster = {"cells": metadata, "blind_commitment_sha256": commitment_sha, "budget_ms": LIVE_BUDGET_MS}
    lock_path = eval_dir / "b1_live_roster_lock.json"
    with _session_lock(eval_dir):
        if not lock_path.is_file():
            _write_public(lock_path, roster)
        elif _read_json(lock_path) != roster:
            raise ValueError("wave2_eval_roster_already_locked_to_different_champions")

    custody = _m5_custody_dir(custody_dir, REPO)
    sealed, _, verification = read_verified_milestone_blind_payload(
        sealed_path=custody / f"{M5_BLIND_SUITE_ID}_sealed.json", commitment_path=M5_BLIND_COMMITMENT_PATH,
        expected_commitment_sha256=commitment_sha, expected_suite_id=M5_BLIND_SUITE_ID,
    )
    if verification["instance_count"] != 120:
        raise ValueError("invalid_wave2_blind_suite_count")
    blind = {
        "suite_id": M5_BLIND_SUITE_ID, "instances": sealed["instances"],
        "distance_convention": sealed["distance_convention"],
        "evaluation_vehicle_limit_policy": sealed["vehicle_limit_policy"],
    }
    external = _external_suites()
    by_seed = {}
    points = []
    for seed in SEEDS:
        blind_rows = {}
        external_rows = {}
        for arm in ARMS:
            cell = _run_id(arm, seed)
            solver = solvers[cell]
            print(f"B1 evaluation: {cell}", flush=True)
            try:
                blind_rows[arm] = _evaluate_cached(cell, solver, blind, LIVE_BUDGET_MS, eval_dir / "cache")
            except Exception:
                raise RuntimeError(f"wave2_blind_evaluation_failed:{cell}") from None
            external_rows[arm] = [
                row for suite in external.values()
                for row in _evaluate_cached(cell, solver, suite, LIVE_BUDGET_MS, eval_dir / "cache")
            ]
            points.append({
                "arm": arm, "seed": seed, **metadata[cell],
                "blind_120_quality": _summary(blind_rows[arm])["relative_gap_pct"],
                "strict_completed_before_deadline": sum(row["strict_completed_before_deadline"] for row in blind_rows[arm]),
                "external_430_strict_completed_before_deadline": sum(
                    row["strict_completed_before_deadline"] for row in external_rows[arm]
                ),
            })
        by_seed[str(seed)] = {
            "blind_120": _compare(blind_rows, seed=seed), "external_430": _compare(external_rows, seed=seed),
        }
    report = {
        "schema_version": "m6-b1-eval/v1", "workers": 1, "budget_ms": LIVE_BUDGET_MS,
        "blind_suite_verification": verification, "external_suite_counts": EXTERNAL_COUNTS,
        "paired_baseline": "no_early_stop", "bootstrap_samples": BOOTSTRAP_SAMPLES,
        "blind_120_quality_metric": "penalized_relative_gap_pct", "points": points,
        "pareto_frontier": pareto_frontier(points), "by_seed": by_seed,
    }
    _write_public(eval_dir / "b1_eval_report.json", report)
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True, choices=("c2_offline", "b1_mock", "b1_mux", "b1_cell", "eval"))
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--arm", choices=tuple(ARMS))
    parser.add_argument("--seed", type=int, choices=SEEDS)
    parser.add_argument("--endpoint", default=PARATERA_ENDPOINT)
    parser.add_argument("--api-key-env", default="PARATERA_API_KEY")
    parser.add_argument("--custody-dir", type=Path)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)
    out_dir = _output_path(args.output_dir)
    if args.stage == "c2_offline":
        report = run_c2_offline(out_dir)
        print(out_dir / "c2_offline" / "c2_offline_430_report.json")
        return 0 if report["strict_return_acceptance_passed"] else 1
    if args.stage == "b1_mock":
        report = run_b1_mock(out_dir)
        print(out_dir / "b1_mock" / "b1_mock_report.json")
        return 0 if report["passed"] else 1
    if args.stage == "b1_mux":
        for seed in SEEDS:
            _seed_common_start(out_dir / "b1_live", seed, endpoint=args.endpoint, api_key_env=args.api_key_env)
        manifest = build_mux_manifest(out_dir, endpoint=args.endpoint, api_key_env=args.api_key_env)
        path = out_dir / "b1_live" / "mux_m6_b1.json"
        _write_public(path, manifest)
        print(path)
        return 0
    if args.stage == "eval":
        run_eval(out_dir, custody_dir=args.custody_dir)
        print(out_dir / "eval" / "b1_eval_report.json")
        return 0
    if args.arm is None or args.seed is None:
        parser.error("--stage b1_cell requires --arm and --seed")
    load_local_env()
    if args.endpoint.startswith("mock://") or os.environ.get("AGENT_SKILL_M2_MOCK") == "1":
        parser.error("b1_cell requires a live endpoint with mock mode disabled")
    live_dir = out_dir / "b1_live"
    config = _arm_config(
        live_dir, args.arm, args.seed, mode="live", endpoint=args.endpoint, api_key_env=args.api_key_env,
    )
    run_dir = Path(config.output_dir)
    with exclusive_file_lock(run_dir / ".cell.lock", busy=f"b1_cell_busy:{config.run_id}"):
        common_start = _seed_common_start(live_dir, args.seed, endpoint=args.endpoint, api_key_env=args.api_key_env)
        try:
            summary = run_research_agent(
                config,
                resume=bool(args.resume),
                common_start=common_start,
            )
        except ProviderFailure as exc:
            atomic_write_json(run_dir / "run_interrupt_status.json", {"status": "resumable", "reason": exc.error_code})
            return 75
        print(json.dumps({key: summary[key] for key in ("run_id", "final_phase", "realized_request_spend")}))
        if summary.get("final_phase") not in {"completed", "budget_stopped", "early_stopped_global"}:
            return 2
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
