"""Track 3 CVRP evaluation, development-only LLM evolution, and mux manifests."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import statistics
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from importlib.metadata import version
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import numpy as np

from agent_skill_loop.client import ProviderFailure, http_post_with_deadline, load_local_env
from agent_skill_loop.cvrp_workbench.baselines_2026 import (
    dual_timing_fields,
    evaluate_portfolio_solver,
    fit_selectors,
    load_portfolio,
    select_complementary,
    solve_pyvrp,
    summarize_solve_timing,
    timing_value as _number,
    validate_training_suite,
)
from agent_skill_loop.cvrp_workbench.solvers import evaluate_algorithm_on_instance
from agent_skill_loop.interface_design.blind_eval import paired_bootstrap_comparison
from agent_skill_loop.interface_design.blind_eval_m3 import holm_bonferroni_adjust
from agent_skill_loop.interface_design.contracts import FrozenInterfaceSolver, sha256_text
from agent_skill_loop.interface_design.planner import build_interface_design, parse_hook_candidate
from agent_skill_loop.interface_design.runtime import evaluate_frozen_interface_solver
from agent_skill_loop.interface_design.session_baseline import load_dev_or_public_suite
from agent_skill_loop.interface_design.templates import get_template_spec
from agent_skill_loop.interface_design.validator import InterfaceValidator
from agent_skill_loop.request_budget import PersistentRequestBudget
from research_agent.contracts import atomic_write_text
from tools.multi_task_mux import _atomic_write_json, _session_lock

DEV = "cvrp_dev_hetero_24"
SELECTION = "cvrp_select_multiscale_64"
EXTERNAL_COUNTS = {
    "cvrp_ext_eohs_256": 256,
    "cvrp_ext_cvrplib_abp_74": 74,
    "cvrp_ext_cvrplib_x_100": 100,
}
SEEDS = (20261124, 20261125, 20261126)
BUDGETS = (500, 2000)
REQUEST_CAP = 100
PARATERA_ENDPOINT = "https://llmapi.paratera.com/v1/chat/completions"
MODEL = "DeepSeek-V4.1-Flash"
OUTPUT_DIR = REPO / "experiments" / "baselines_2026"
FLEET_POLICIES = {"exact-k": "strict_max_vehicles", "free_fleet": "free_fleet_min_k_lb"}
METHODS = {"reevo": "ReEvo", "eohs": "EoH-S"}
TEMPLATES = ("cvrp_ruin_recreate", "cvrp_parallel_merge_static")
SELECTOR_NAMES = ("SATzilla", "AutoFolio", "Hydra", "SBS")
TIMING_PROTOCOL = "solve-only-deadline/nearest-rank-right-censor-bounds/v1"


def _load_suite(suite_id: str, split: str, role: str, count: int) -> dict[str, Any]:
    suite = load_dev_or_public_suite(suite_id, split=split, role=role)
    if len(suite["instances"]) != count:
        raise ValueError(f"unexpected_instance_count:{suite_id}:{len(suite['instances'])}")
    return suite


def _load_dev() -> dict[str, Any]:
    return _load_suite(DEV, "dev_train", "diagnostic_interactive", 24)


def _load_external() -> list[dict[str, Any]]:
    return [
        _load_suite(name, "heldout", "external_evaluation", count)
        for name, count in EXTERNAL_COUNTS.items()
    ]


def _target_instances(suite: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Use manifest k or the workbench NN route count for an unlabelled fleet."""
    targeted = []
    for instance in suite["instances"]:
        target = instance.get("k_vehicles")
        source = "manifest_k_vehicles"
        if target is None:
            target = instance.get("max_vehicles")
            source = "manifest_max_vehicles"
        if target is None:
            nn = evaluate_algorithm_on_instance(
                "nn", instance, distance_convention=suite.get("distance_convention", "euc_2d_float"),
                vehicle_limit_policy="unconstrained", enforce_wall_deadline=False, record_trace=False,
            )
            if not nn["valid"]:
                raise ValueError(f"missing_exact_k_reference:{instance['instance_id']}")
            target = nn["route_count"]
            source = "nearest_neighbor_route_count"
        if isinstance(target, bool) or int(target) != target or target < 1:
            raise ValueError(f"invalid_exact_k_reference:{instance['instance_id']}")
        targeted.append({**instance, "k_vehicles": int(target), "exact_k_target_source": source})
    return targeted


def _score(instance: Mapping[str, Any], result: Mapping[str, Any], policy: str, budget_ms: float) -> dict[str, Any]:
    reference = _number(instance.get("reference_objective"))
    if not reference:
        raise ValueError(f"invalid_reference_objective:{instance['instance_id']}")
    error = result.get("error_code")
    if error in {"worker_protocol", "worker_crash", "worker_start_failed"}:
        raise RuntimeError(f"solver_worker_failed:{instance['instance_id']}:{error}")
    objective = _number(result.get("tour_length", result.get("objective")))
    valid = result.get("valid") is True and objective is not None
    exact = result.get("exact_vehicle_count")
    feasible = valid and (policy != "strict_max_vehicles" or exact is True)
    timing = dual_timing_fields(result, budget_ms=budget_ms, feasible=feasible)
    uncensored_overrun = (
        (not timing["solve_censored"])
        and (timing["deadline_overrun_ms"] is not None)
        and (timing["deadline_overrun_ms"] > 0.0)
    )
    default_completed = result.get("status") == "ok" and not result.get("budget_exhausted", False)
    completed = feasible and result.get("completed", default_completed) is True and not uncensored_overrun
    return {
        "instance_id": instance["instance_id"],
        "size": instance.get("size", len(instance["demands"])),
        "reference_objective": reference,
        "reference_kind": instance.get("reference_kind"),
        "objective": objective if valid else None,
        "tour_length": objective if valid else None,
        "tour_length_euc_2d_float": _number(result.get("tour_length_euc_2d_float")),
        "valid": valid,
        "feasible": feasible,
        "completed": completed,
        "uncensored_deadline_overrun": uncensored_overrun,
        "completed_feasible_before_deadline": completed and (timing["feasible_before_deadline"] is not False),
        "completed_returned_before_deadline": completed and (timing["returned_before_deadline"] is not False),
        "scored_objective": objective if completed else 2 * reference,
        "target_vehicles": instance.get("k_vehicles", instance.get("max_vehicles")),
        "exact_k_target_source": instance.get("exact_k_target_source"),
        "route_count": result.get("route_count"),
        "exact_vehicle_count": exact,
        "within_vehicle_limit": result.get("within_vehicle_limit"),
        "status": result.get("status"),
        "outcome_class": result.get("outcome_class"),
        "error_code": error,
        "stop_reason": result.get("stop_reason"),
        "budget_exhausted": result.get("budget_exhausted") is True,
        "time_limit_reached": result.get("time_limit_reached"),
        "timeout_kind": result.get("timeout_kind"),
        **timing,
        "incumbent_ms": _number(result.get("incumbent_ms")),
        "source_solver": result.get("source_solver"),
        "selector_ms": _number(result.get("selector_ms")),
        "set_member_count": result.get("set_member_count"),
    }


def _best_result(instance: Mapping[str, Any], results: Mapping[str, Mapping[str, Any]],
                 policy: str, budget_ms: float) -> dict[str, Any]:
    scored = {name: _score(instance, result, policy, budget_ms) for name, result in results.items()}
    name = min(scored, key=lambda key: (
        not scored[key]["completed"], not scored[key]["feasible"],
        scored[key]["scored_objective"] if scored[key]["completed"] else
        (scored[key]["objective"] if scored[key]["feasible"] else math.inf), key,
    ))
    return {**results[name], "source_solver": name}


def _summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    count = len(rows)
    completed = [row for row in rows if row["completed"]]
    feasible_count = sum(row["feasible"] for row in rows)
    total = sum(row["scored_objective"] for row in rows)
    references = sum(row["reference_objective"] for row in rows)
    checked = [row for row in rows if row["exact_vehicle_count"] is not None]
    matches = sum(row["valid"] and row["exact_vehicle_count"] is True for row in checked)
    feasible_before_completed = sum(
        bool(row.get("completed")) and (row.get("feasible_before_deadline") is not False)
        for row in rows
    )
    returned_before_completed = sum(
        bool(row.get("completed")) and (row.get("returned_before_deadline") is not False)
        for row in rows
    )
    uncensored_overrun_cnt = sum(
        bool(row.get("uncensored_deadline_overrun"))
        or (
            (not row.get("solve_censored"))
            and (row.get("deadline_overrun_ms") is not None)
            and (float(row["deadline_overrun_ms"]) > 0.0)
        )
        for row in rows
    )
    censored_callback_overrun_cnt = sum(
        bool(row.get("completed"))
        and bool(row.get("solve_censored"))
        and (row.get("deadline_overrun_ms") is not None)
        and (float(row["deadline_overrun_ms"]) > 0.0)
        for row in rows
    )
    return {
        "n_instances": count,
        "completed_count": len(completed),
        "completion_rate": len(completed) / count if count else None,
        "feasible_before_deadline_completed_count": feasible_before_completed,
        "returned_before_deadline_completed_count": returned_before_completed,
        "uncensored_overrun_penalized_count": uncensored_overrun_cnt,
        "censored_callback_overrun_count": censored_callback_overrun_cnt,
        "feasible_count": feasible_count,
        "feasible_rate": feasible_count / count if count else None,
        "penalized_count": count - len(completed),
        "total_scored_objective": total if count else None,
        "mean_scored_objective": total / count if count else None,
        "mean_tour_length": statistics.mean(row["objective"] for row in completed) if completed else None,
        "relative_gap_pct": 100 * (total / references - 1) if references else None,
        "exact_k_checked": len(checked),
        "exact_k_count": matches,
        "exact_k_compliance_rate": matches / len(checked) if checked else None,
        "budget_exhausted_count": sum(row["budget_exhausted"] for row in rows),
        **summarize_solve_timing(rows),
    }


def _paired(rows: Mapping[str, Sequence[Mapping[str, Any]]], *, common_completed: bool,
            samples: int, seed: int) -> dict[str, Any]:
    baselines = [name for name in ("SBS", "VBS") if name in rows] or [next(iter(rows))]
    comparisons = {}
    for name, candidate in rows.items():
        for baseline in baselines:
            if name == baseline or (name == "SBS" and baseline == "VBS"):
                continue
            pairs = [(left, right) for left, right in zip(candidate, rows[baseline], strict=True)
                     if not common_completed or (left["completed"] and right["completed"])]
            stats = paired_bootstrap_comparison(
                [left["scored_objective"] for left, _ in pairs],
                [right["scored_objective"] for _, right in pairs],
                n_boot=samples, seed=seed,
            ) if pairs else {"n_instances": 0, "wilcoxon_signed_rank": None}
            comparisons[f"{name}_vs_{baseline}"] = {"candidate_id": name, "baseline_id": baseline, **stats}
    # Empty contrasts use p=1 inside the predeclared family but carry no result.
    adjusted = holm_bonferroni_adjust([
        row["wilcoxon_signed_rank"]["p_two_sided"] if row["wilcoxon_signed_rank"] else 1.0
        for row in comparisons.values()
    ])
    for row, p_value in zip(comparisons.values(), adjusted, strict=True):
        row["p_holm_wilcoxon"] = p_value if row["wilcoxon_signed_rank"] else None
    return comparisons


def _evaluate_lane(suite: Mapping[str, Any], instances: Sequence[Mapping[str, Any]],
                   solvers: Mapping[str, Callable[..., Mapping[str, Any]]], *, policy: str,
                   seed: int, budget_ms: float, bootstrap_samples: int) -> dict[str, Any]:
    rows = {name: [] for name in solvers}
    for instance in instances:
        for name, solve in solvers.items():
            result = solve(instance, budget_ms=budget_ms, seed=seed,
                           distance_convention=suite.get("distance_convention", "euc_2d_float"),
                           vehicle_limit_policy=policy)
            rows[name].append({"algorithm_id": name, **_score(instance, result, policy, budget_ms)})
    all_indices = list(range(len(instances)))
    common = [i for i in all_indices if all(values[i]["completed"] for values in rows.values())]
    return {
        "vehicle_limit_policy": policy,
        "n_instances": len(instances),
        "common_completed_count": len(common),
        "common_completed_instance_ids": [instances[i]["instance_id"] for i in common],
        "overall": {name: _summary(values) for name, values in rows.items()},
        "common_completed": {name: _summary([values[i] for i in common]) for name, values in rows.items()},
        "comparisons": {
            "overall": _paired(rows, common_completed=False, samples=bootstrap_samples, seed=seed),
            "common_completed": _paired(rows, common_completed=True, samples=bootstrap_samples, seed=seed),
        },
        "rows": [row for values in rows.values() for row in values],
    }


def evaluate_external(suites: Sequence[Mapping[str, Any]],
                      solvers: Mapping[str, Callable[..., Mapping[str, Any]]], *,
                      seed: int, budget_ms: float, bootstrap_samples: int = 10000) -> dict[str, Any]:
    """Evaluate fixed solvers per seed, suite, and fleet lane with matched denominators."""
    if not suites or not solvers or bootstrap_samples < 1:
        raise ValueError("evaluation_requires_suites_solvers_and_bootstrap_samples")
    report: dict[str, Any] = {
        "schema_version": "cvrp-external-baselines-2026/v1",
        "seed": seed,
        "budget_ms": budget_ms,
        "timing_protocol": TIMING_PROTOCOL,
        "overall_noncompletion_penalty": "2 * reference_objective",
        "paired_statistics": {"bootstrap_samples": bootstrap_samples, "bootstrap_seed": seed,
                              "test": "two_sided_wilcoxon_signed_rank",
                              "common_completed": "pairwise_intersection",
                              "holm_family": "within_seed_suite_fleet_and_denominator"},
        "suites": {},
    }
    for suite in suites:
        suite_id = suite["suite_id"]
        if suite_id not in EXTERNAL_COUNTS or suite.get("split") != "heldout" or suite_id in report["suites"]:
            raise ValueError(f"unauthorized_or_duplicate_external_suite:{suite_id}")
        instances = _target_instances(suite)
        if not instances or len({row["instance_id"] for row in instances}) != len(instances):
            raise ValueError(f"empty_or_duplicate_external_instances:{suite_id}")
        report["suites"][suite_id] = {
            "distance_convention": suite.get("distance_convention", "euc_2d_float"),
            "data_manifest_hash": suite.get("data_manifest_hash"),
            "reference_manifest_hash": suite.get("reference_manifest_hash"),
            **{
                lane: _evaluate_lane(suite, instances, solvers, policy=policy, seed=seed,
                                     budget_ms=budget_ms, bootstrap_samples=bootstrap_samples)
                for lane, policy in FLEET_POLICIES.items()
            },
        }
    report["external_instance_count"] = sum(len(suite["instances"]) for suite in suites)
    return report


def _fit_portfolio(dev: Mapping[str, Any], selection: Mapping[str, Any], portfolio: Mapping[str, Any],
                   *, budget_ms: float, hydra_k: int, seed: int) -> dict[str, Any]:
    fitted = {}
    for policy in FLEET_POLICIES.values():
        costs = {}
        for suite in (dev, selection):
            for instance in _target_instances(suite):
                iid = instance["instance_id"]
                costs[iid] = {}
                for name, solver in portfolio.items():
                    result = evaluate_portfolio_solver(
                        solver, instance, budget_ms=budget_ms, vehicle_limit_policy=policy,
                        distance_convention=suite["distance_convention"],
                    )
                    row = _score(instance, result, policy, budget_ms)
                    costs[iid][name] = row["scored_objective"] / row["reference_objective"]
        fitted[policy] = fit_selectors((dev, selection), costs, solver_names=tuple(portfolio),
                                       hydra_k=hydra_k, seed=seed)
    return fitted


def _portfolio_callbacks(portfolio: Mapping[str, Any], fitted: Mapping[str, Any]) -> dict[str, Callable]:
    # Each row is solved once per portfolio member. Picks are fixed before VBS sees any results.
    current_instance: Mapping[str, Any] | None = None
    current: tuple | None = None
    results: dict[str, Mapping[str, Any]] = {}
    picks: dict[str, str] = {}
    selector_ms = 0.0

    def evaluate(name: str, instance: Mapping[str, Any], *, budget_ms: float, seed: int,
                 distance_convention: str, vehicle_limit_policy: str) -> dict[str, Any]:
        nonlocal current_instance, current, picks, selector_ms
        key = (distance_convention, vehicle_limit_policy, budget_ms, seed)
        if current_instance is not instance or current != key:
            current_instance = instance
            current = key
            results.clear()
            start = time.perf_counter()
            picks = fitted[vehicle_limit_policy].predict(instance)
            selector_ms = 1000 * (time.perf_counter() - start)

        def run(member: str) -> Mapping[str, Any]:
            if member not in results:
                results[member] = evaluate_portfolio_solver(
                    portfolio[member], instance, budget_ms=budget_ms, distance_convention=distance_convention,
                    vehicle_limit_policy=vehicle_limit_policy,
                )
            return results[member]

        if name == "VBS":
            return _best_result(instance, {member: run(member) for member in portfolio},
                                vehicle_limit_policy, budget_ms)
        member = picks[name]
        result = run(member)
        selection_ms = selector_ms if name != "SBS" else 0.0
        preprocess_ms = _number(result.get("preprocess_ms"))
        return {**result, "source_solver": member, "selector_ms": selection_ms,
                "preprocess_ms": preprocess_ms + selection_ms if preprocess_ms is not None else None}

    def callback(name: str) -> Callable:
        return lambda instance, **kwargs: evaluate(name, instance, **kwargs)

    return {name: callback(name) for name in (*SELECTOR_NAMES, "VBS")}


class MockDriver:
    """Deterministic reflection and valid hook proposals through the live response contract."""

    identity = {"mode": "mock", "model": "deterministic_mock/v1"}

    def complete(self, *, phase: str, prompt: str, template_id: str, seed: int, request: int) -> str:
        if phase != "propose":
            return json.dumps({"reflection": "Compare demand and distance contributions on the dev scores."})
        design = build_interface_design(template_id)
        weight = random.Random((seed << 16) + request).uniform(0.01, 0.35)
        code = design.baseline_hook_code.rstrip()
        if template_id == "cvrp_ruin_recreate":
            code += f" + {weight:.8f} * demands[1:] / capacity\n"
        else:
            code = code.replace("    return ", "    scale = np.maximum(np.mean(distance_matrix[0, 1:]), 1e-12)\n    return (")
            code += f") / scale + {weight:.8f} * (demands[i_idx] + demands[j_idx]) / capacity\n"
        return json.dumps({"hook_code": code})


class ParateraDriver:
    """One deadline-bound HTTP attempt per reserved request."""

    def __init__(self, model: str, timeout_s: float) -> None:
        load_local_env()
        self.endpoint = os.environ.get("PARATERA_ENDPOINT") or PARATERA_ENDPOINT
        self.key = os.environ.get("PARATERA_API_KEY")
        if not self.key:
            raise ValueError("PARATERA_API_KEY_missing")
        self.model = model
        self.timeout_s = timeout_s
        self.identity = {"mode": "live", "model": model, "endpoint": self.endpoint, "timeout_s": timeout_s}

    def complete(self, *, phase: str, prompt: str, template_id: str, seed: int, request: int) -> str:
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": "You design CVRP heuristic hooks. Return one JSON object."},
                         {"role": "user", "content": prompt}],
            "temperature": 0.5,
            "max_tokens": 16384 if phase == "propose" else 4096,
        }
        headers = {"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"}
        status, body = http_post_with_deadline(self.endpoint, headers, json.dumps(payload).encode(), self.timeout_s)
        if status != 200:
            raise ProviderFailure("provider_http_status", status=status)
        obj = json.loads(body)
        content = obj["choices"][0]["message"]["content"]
        if not isinstance(content, str) or not content.strip():
            raise ValueError("empty_provider_content")
        return content


def _candidate(design: Any, code: str, *, method: str, seed: int, budget_ms: float,
               origin: Path, validator: InterfaceValidator) -> tuple[FrozenInterfaceSolver | None, list[str]]:
    try:
        implementations = parse_hook_candidate(design.template_id, design.template_version, code)
    except (SyntaxError, ValueError) as exc:
        return None, [str(exc)]
    primary = implementations[design.hook_name]
    report = validator.validate(design, hook_code_override=primary,
                                hook_implementations=implementations if design.hook_specs else None)
    if not report.passed:
        return None, [failure.error_code for failure in report.failures]
    spec = get_template_spec(design.template_id, design.template_version)
    code_hash = sha256_text(primary)
    return FrozenInterfaceSolver(
        solver_id=f"{method}_s{seed}_{code_hash[:12]}",
        display_name=f"{METHODS[method]} {design.template_id} {code_hash[:8]}",
        problem_family=design.problem_family, paradigm=design.paradigm,
        template_id=design.template_id, template_version=design.template_version,
        template_source_sha256=spec.template_source_sha256,
        postprocess_mode=design.postprocess_mode, template_options=dict(design.template_options),
        hook_name=design.hook_name, hook_code=primary, hook_code_sha256=code_hash,
        design_sha256=design.design_sha256, origin_run=str(origin),
        kb_release_id="track3_external_baselines_2026", default_budget_ms=budget_ms,
        protocol_id=spec.effective_protocol_id, hook_specs=spec.hook_specs,
        hook_implementations=implementations if spec.hook_specs else {},
    ), []


def _frozen_result(solver: FrozenInterfaceSolver, instance: Mapping[str, Any], *, budget_ms: float,
                   distance_convention: str, vehicle_limit_policy: str) -> dict[str, Any]:
    return evaluate_frozen_interface_solver(
        solver, instance, distance_convention=distance_convention, vehicle_limit_policy=vehicle_limit_policy,
        solve_deadline_ms=budget_ms, enforce_wall_deadline=True,
    )


def frozen_set_solver(winners: Sequence[FrozenInterfaceSolver], *, portfolio_size: int) -> Callable:
    """Use the best verified return under a fixed total solve budget for the set."""
    if not winners or len(winners) > portfolio_size or len({solver.solver_id for solver in winners}) != len(winners):
        raise ValueError("invalid_frozen_set")

    def solve(instance: Mapping[str, Any], *, budget_ms: float, seed: int,
              distance_convention: str, vehicle_limit_policy: str) -> dict[str, Any]:
        member_budget = budget_ms / portfolio_size
        results = {
            solver.solver_id: _frozen_result(solver, instance, budget_ms=member_budget,
                                            distance_convention=distance_convention,
                                            vehicle_limit_policy=vehicle_limit_policy)
            for solver in winners
        }
        chosen = _best_result(instance, results, vehicle_limit_policy, member_budget)
        elapsed = 0.0
        incumbent = False
        member_censored = False
        for result in results.values():
            member = _score(instance, result, vehicle_limit_policy, member_budget)
            if member["feasible_before_deadline"] and elapsed + member_budget <= budget_ms:
                incumbent = True
            elapsed += member["solve_ms"] if member["solve_ms"] is not None else math.inf
            member_censored |= member["solve_censored"]
        for field in ("solve_ms", "preprocess_ms", "verify_ms"):
            values = [_number(row.get(field)) for row in results.values()]
            chosen[field] = sum(values) if all(value is not None for value in values) else None
        chosen["feasible_before_deadline"] = incumbent
        chosen["solve_censored"] = member_censored
        chosen.pop("deadline_overrun_ms", None)
        chosen["set_member_count"] = len(winners)
        return chosen

    return solve


def _dev_candidate(solver: FrozenInterfaceSolver, suite: Mapping[str, Any], budget_ms: float,
                   *, request: int) -> dict[str, Any]:
    policy = FLEET_POLICIES["free_fleet"]
    outcomes = []
    for instance in suite["instances"]:
        result = _frozen_result(solver, instance, budget_ms=budget_ms, vehicle_limit_policy=policy,
                                distance_convention=suite.get("distance_convention", "euc_2d_float"))
        outcomes.append(_score(instance, result, policy, budget_ms))
    costs = [row["scored_objective"] / row["reference_objective"] for row in outcomes]
    return {"solver": solver.to_dict(), "costs": costs, "mean_cost": statistics.mean(costs),
            "feasible_count": sum(row["feasible"] for row in outcomes),
            "completed_count": sum(row["completed"] for row in outcomes), "request": request}


def _elite_key(candidate: Mapping[str, Any]) -> tuple:
    return (candidate["mean_cost"], -candidate["completed_count"], -candidate["feasible_count"],
            candidate["solver"]["solver_id"])


def _complementary(candidates: Sequence[Mapping[str, Any]], size: int) -> list[Mapping[str, Any]]:
    costs = np.asarray([candidate["costs"] for candidate in candidates], dtype=float).T
    return [candidates[i] for i in select_complementary(costs, min(size, len(candidates)))]


def _prompt(method: str, state: Mapping[str, Any], template_id: str, design: Any,
            request: int, phase: str, seed: int, size: int) -> tuple[str, str, list[str]]:
    candidates = sorted(state["population"], key=_elite_key)
    eligible = [row for row in candidates if row["solver"]["template_id"] == template_id]
    operation = "mutate"
    if method == "eohs":
        parents = _complementary(candidates, size)
        current = np.min([row["costs"] for row in parents], axis=0).tolist()
        goal = ("Improve greedy set coverage on the dev cases. Lowest current normalized cost per dev case: "
                f"{current}. Case indices are aligned across parents. Prioritize cases with high residual cost.")
        operation = "complementary_set_proposal"
    else:
        cycle = (request - 1) // 3
        rng = random.Random((seed << 16) + cycle)
        parents = eligible[:1]
        if len(eligible) > 1:
            parents.append(rng.choice(eligible[1:6]))
        if cycle % 4 >= 2 and len(parents) == 2:
            operation = "crossover"
        goal = (f"Use {operation} with the first parent as the elite. For mutation, change that parent's rule. "
                "For crossover, combine useful aspects of both same-template parents.")
    context = [{"id": row["solver"]["solver_id"], "template": row["solver"]["template_id"],
                "hook_code": row["solver"]["hook_code"], "dev_normalized_costs": row["costs"]} for row in parents]
    directives = {
        "reflect_short": 'Compare parent performance and code. Return {"reflection": "one actionable observation"}.',
        "reflect_long": 'Distill recurring lessons using short-term and previous long-term reflection. '
                        'Return {"reflection": "updated concise long-term memory"}.',
        "propose": 'Return {"hook_code": "complete Python hook source"}. Preserve signature and input immutability.',
    }
    prompt = (f"{METHODS[method]} request {request}. {goal}\n{design.hook_task_description}\n"
              f"Starting hook:\n{design.baseline_hook_code}\n"
              f"Development results and parents: {json.dumps(context)}\n"
              f"Short-term reflection: {state['short_reflection']}\n"
              f"Long-term reflection: {state['long_reflection']}\n{directives[phase]}")
    return prompt, operation, [row["id"] for row in context]


def _reply_field(content: str, key: str, max_length: int) -> str:
    content = content.strip()
    if content.startswith("```") and content.endswith("```"):
        _, _, content = content.partition("\n")
        content = content.removesuffix("```").strip()
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        start, end = content.find("{"), content.rfind("}")
        if start < 0 or end <= start:
            raise
        parsed = json.loads(content[start : end + 1])
    if not isinstance(parsed, Mapping):
        raise ValueError("invalid_reply_object")
    value = parsed[key]
    if not isinstance(value, str) or not value.strip() or len(value) > max_length:
        raise ValueError(f"invalid_reply_field:{key}")
    return value


def _apply_pending(state: dict[str, Any], *, designs: Mapping[str, Any], dev_suite: Mapping[str, Any],
                   budget_ms: float, method: str, seed: int, checkpoint_path: Path,
                   validator: InterfaceValidator) -> None:
    pending = state["pending"]
    event = dict(pending["event"])
    if "response" in pending:
        phase = event["phase"]
        try:
            value = _reply_field(pending["response"], "hook_code" if phase == "propose" else "reflection",
                                 16000 if phase == "propose" else 4000)
        except (KeyError, TypeError, ValueError) as exc:
            event.update(status="invalid_reply", error_code=type(exc).__name__)
        else:
            if phase != "propose":
                reflection = "short_reflection" if phase == "reflect_short" else "long_reflection"
                state[reflection] = value
                event.update(status="reflected", reflection=value)
            else:
                design = designs[event["template_id"]]
                candidate, failures = _candidate(design, value, method=method, seed=seed, budget_ms=budget_ms,
                                                 origin=checkpoint_path, validator=validator)
                if candidate is None:
                    event.update(status="validation_rejected", validation_errors=failures)
                elif candidate.solver_id in {member["solver"]["solver_id"] for member in state["population"]}:
                    event.update(status="duplicate", candidate_id=candidate.solver_id)
                else:
                    row = _dev_candidate(candidate, dev_suite, budget_ms, request=event["request"])
                    if row["feasible_count"]:
                        state["population"].append(row)
                        event.update(status="accepted", candidate_id=candidate.solver_id, mean_cost=row["mean_cost"])
                    else:
                        event.update(status="no_feasible_dev_result", candidate_id=candidate.solver_id)
    state["history"].append(event)
    state["processed_requests"] = event["request"]
    state["pending"] = None
    _atomic_write_json(checkpoint_path, state)


def evolve(method: str, dev_suite: Mapping[str, Any], *, seed: int, request_cap: int,
           budget_ms: float, checkpoint_path: Path, driver: Any, portfolio_size: int = 3) -> dict[str, Any]:
    """Run or resume one bounded evolution arm using only authenticated dev instances."""
    if method == "eoh-s":
        method = "eohs"
    if method not in METHODS or not 1 <= request_cap <= REQUEST_CAP or not math.isfinite(budget_ms) or budget_ms <= 0:
        raise ValueError("invalid_evolution_method_or_budget")
    if portfolio_size < 1 or dev_suite.get("split") != "dev_train" or dev_suite.get("suite_id") != DEV:
        raise ValueError("evolution_requires_dev_hetero_24_and_positive_portfolio_size")
    training = validate_training_suite(dev_suite)
    dev_cases = hashlib.sha256(json.dumps(dev_suite["instances"], sort_keys=True).encode()).hexdigest()
    member_budget = budget_ms / portfolio_size if method == "eohs" else budget_ms
    checkpoint_path = Path(checkpoint_path).resolve()
    ledger_path = checkpoint_path.with_suffix(".sqlite3")
    config = {"method": method, "seed": seed, "request_cap": request_cap, "budget_ms": budget_ms,
              "member_budget_ms": member_budget, "portfolio_size": portfolio_size, "driver": driver.identity,
              "training_suite": training, "ordered_dev_cases_sha256": dev_cases,
              "template_hashes": {key: get_template_spec(key, "v1").template_source_sha256 for key in TEMPLATES}}
    designs = {key: build_interface_design(key, design_id=f"track3_{key}") for key in TEMPLATES}
    validator = InterfaceValidator(instance_time_budget_ms=member_budget)
    checkpoint_schema = "cvrp-baselines-2026-checkpoint/v1"
    with _session_lock(checkpoint_path.parent, lock_name=f".{checkpoint_path.name}.lock"):
        if checkpoint_path.exists():
            state = json.loads(checkpoint_path.read_bytes())
            if state.get("schema_version") != checkpoint_schema or state.get("config") != config:
                raise ValueError("evolution_checkpoint_configuration_mismatch")
            if not ledger_path.is_file() and (state["processed_requests"] or state["pending"]):
                raise ValueError("evolution_request_ledger_missing")
        else:
            if ledger_path.exists():
                raise ValueError("evolution_checkpoint_missing_for_existing_ledger")
            population = []
            for design in designs.values():
                solver, failures = _candidate(design, design.baseline_hook_code, method=method, seed=seed,
                                              budget_ms=member_budget, origin=checkpoint_path, validator=validator)
                if solver is None:
                    raise RuntimeError(f"stock_hook_validation_failed:{design.template_id}:{failures}")
                population.append(_dev_candidate(solver, dev_suite, member_budget, request=0))
            state = {"schema_version": checkpoint_schema, "config": config, "population": population, "history": [],
                     "processed_requests": 0, "pending": None, "short_reflection": "", "long_reflection": ""}
            _atomic_write_json(checkpoint_path, state)

        ledger = PersistentRequestBudget(ledger_path, request_cap, run_id=f"{method}:{seed}")
        if ledger.used < state["processed_requests"] or (state["pending"] and ledger.used < state["pending"]["event"]["request"]):
            raise ValueError("evolution_request_ledger_behind_checkpoint")
        def apply_pending() -> None:
            _apply_pending(state, designs=designs, dev_suite=dev_suite, budget_ms=member_budget,
                           method=method, seed=seed, checkpoint_path=checkpoint_path, validator=validator)

        if state["pending"]:
            apply_pending()
        for skipped in range(state["processed_requests"] + 1, ledger.used + 1):
            state["history"].append({"request": skipped, "status": "interrupted_unknown"})
            state["processed_requests"] = skipped
        _atomic_write_json(checkpoint_path, state)

        while ledger.used < request_cap:
            request = ledger.used + 1
            if method == "reevo":
                phase = ("reflect_short", "reflect_long", "propose")[(request - 1) % 3]
                template_id = TEMPLATES[((request - 1) // 3) % len(TEMPLATES)]
            else:
                phase = "propose"
                template_id = TEMPLATES[(request - 1) % len(TEMPLATES)]
            prompt, operation, parents = _prompt(method, state, template_id, designs[template_id], request,
                                                 phase, seed, portfolio_size)
            slot = ledger.reserve(purpose=phase, problem="cvrp", model=driver.identity["model"])
            if slot is None:
                raise RuntimeError(f"evolution_request_reservation_failed:{ledger.denial_reason}")
            ledger.mark_sent(slot)
            event = {"request": request, "phase": phase, "template_id": template_id, "parent_ids": parents,
                     "operation": operation, "request_id": slot.request_id, "prompt_sha256": sha256_text(prompt)}
            pending: dict[str, Any] = {"event": event}
            sent_at = time.monotonic()
            try:
                response = driver.complete(phase=phase, prompt=prompt, template_id=template_id, seed=seed, request=request)
            except (ProviderFailure, TypeError, ValueError, KeyError, IndexError) as exc:
                event.update(status="provider_error", error_code=getattr(exc, "error_code", type(exc).__name__))
                if isinstance(exc, ProviderFailure) and exc.status is not None:
                    event["http_status"] = exc.status
                terminal = "provider_error"
            else:
                pending["response"] = response
                event["response_sha256"] = sha256_text(response)
                terminal = "success"
            state["pending"] = pending
            _atomic_write_json(checkpoint_path, state)
            ledger.finish(slot, terminal, response_sha256=event.get("response_sha256"),
                          error_code=event.get("error_code"), status=event.get("http_status"),
                          elapsed_seconds=time.monotonic() - sent_at)
            apply_pending()
            if event.get("http_status") in {401, 403}:
                raise RuntimeError(f"paratera_authentication_failed:{event['http_status']}")

        ranked = sorted(state["population"], key=_elite_key)
        winners = _complementary(ranked, portfolio_size) if method == "eohs" else ranked[:1]
        coverage = np.min([row["costs"] for row in winners], axis=0)
        accepted_count = sum(row["request"] > 0 for row in ranked)
        return {
            "schema_version": "cvrp-baselines-2026-evolution/v1", "method": method, **config,
            "status": "completed" if accepted_count else "no_evolved_candidate",
            "accepted_candidate_count": accepted_count,
            "requests_used": ledger.used, "winners": [row["solver"] for row in winners],
            "winner_dev_mean_normalized_cost": float(coverage.mean()),
            "winner_dev_coverage": coverage.tolist(),
            "population": [{**{key: value for key, value in row.items() if key != "solver"},
                            "solver_id": row["solver"]["solver_id"]} for row in ranked],
            "history": state["history"],
        }


def _display(value: float | None, digits: int = 3) -> str:
    return "—" if value is None else f"{value:.{digits}f}"


def write_report(report: Mapping[str, Any], stem: Path) -> None:
    _atomic_write_json(stem.with_suffix(".json"), report)
    lines = [
        "# Track 3 external CVRP baselines", "",
        f"Seed {report['seed']}, {report['budget_ms']} ms solve budget, "
        f"{report['external_instance_count']} external instances.", "",
        "Overall assigns twice the reference objective to noncompletions. "
        "Common-completed summaries use the all-algorithm intersection. "
        "Paired comparisons use the intersection for the two algorithms in each comparison.", "",
        "The deadline applies to the solve stage. A ≥ prefix marks a latency quantile reported as a lower bound.", "",
        "Positive paired gain favors the candidate. VBS is the retrospectively best verified portfolio pick.",
    ]
    for suite_id, suite in report["suites"].items():
        lines += ["", f"## {suite_id}", "", f"Distance convention `{suite['distance_convention']}`."]
        for lane in FLEET_POLICIES:
            section = suite[lane]
            for denominator in ("overall", "common_completed"):
                lines += [
                    "", f"### {lane} / {denominator}", "",
                    "| Algorithm | Instances | Completed | Feasible | Feasible by deadline | Returned by deadline | Penalized | Gap (%) | P50 solve (ms) | P95 solve (ms) |",
                    "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
                ]
                for name, row in section[denominator].items():
                    p50, p95 = [
                        ("≥" if row.get(f"{key}_is_lower_bound") else "") + _display(row[key])
                        for key in ("solve_ms_p50", "solve_ms_p95")
                    ]
                    lines.append(f"| {name} | {row['n_instances']} | {row['completed_count']} | "
                                 f"{row['feasible_count']} | {row['feasible_before_deadline_count']} | "
                                 f"{row['returned_before_deadline_count']} | {row['penalized_count']} | "
                                 f"{_display(row['relative_gap_pct'])} | {p50} | {p95} |")
                comparisons = section["comparisons"][denominator]
                if comparisons:
                    lines += ["", "| Comparison | Pairs | Gain (%) | Bootstrap 95% CI | Wilcoxon p (Holm) |",
                              "|---|---:|---:|---:|---:|"]
                for row in comparisons.values():
                    interval = row.get("rel_gain_ci95_pct")
                    ci = f"[{_display(interval[0])}, {_display(interval[1])}]" if interval else "—"
                    lines.append(f"| {row['candidate_id']} vs {row['baseline_id']} | {row['n_instances']} | "
                                 f"{_display(row.get('rel_gain_vs_baseline_pct'))} | {ci} | "
                                 f"{_display(row.get('p_holm_wilcoxon'), 6)} |")
    atomic_write_text(stem.with_suffix(".md"), "\n".join(lines) + "\n")


def _run_dir(output_dir: Path, method: str, seed: int, mode: str) -> Path:
    return output_dir / "runs" / mode / f"{method}_s{seed}"


def _winner_callback(evolution: Mapping[str, Any]) -> Callable:
    if evolution["status"] != "completed":
        raise ValueError(f"no_evolved_candidate:{evolution['method']}:{evolution['seed']}")
    winners = [FrozenInterfaceSolver.from_dict(row) for row in evolution["winners"]]
    slots = evolution["portfolio_size"] if evolution["method"] == "eohs" else 1
    return frozen_set_solver(winners, portfolio_size=slots)


def _load_finished_evolutions(output_dir: Path, seed: int, mode: str) -> dict[str, dict[str, Any]]:
    reports = {}
    for method in METHODS:
        run_dir = _run_dir(output_dir, method, seed, mode)
        report = json.loads((run_dir / "evolution.json").read_bytes())
        if (report.get("schema_version") != "cvrp-baselines-2026-evolution/v1"
                or report.get("method") != method or report.get("seed") != seed
                or report["driver"].get("mode") != mode or report.get("requests_used") != report.get("request_cap")
                or report.get("status") != "completed" or not report.get("accepted_candidate_count")
                or report["training_suite"].get("suite_id") != DEV
                or report["training_suite"].get("split") != "dev_train"):
            raise ValueError(f"invalid_evolution_report:{run_dir}")
        reports[method] = report
    return reports


def _run_benchmark(args: argparse.Namespace) -> None:
    dependencies = {name: version(name) for name in ("pyvrp", "scikit-learn", "scipy", "numpy")}
    evolutions = _load_finished_evolutions(args.output_dir, args.seed, args.with_evolution) if args.with_evolution else {}
    dev = _load_dev()
    selection = _load_suite(SELECTION, "selection", "selection_tuning", 64)
    portfolio = load_portfolio()
    if args.hydra_k > len(portfolio):
        raise ValueError(f"hydra_k_exceeds_portfolio_size:{len(portfolio)}")
    fitted = _fit_portfolio(dev, selection, portfolio, budget_ms=args.budget_ms, hydra_k=args.hydra_k, seed=args.seed)
    solvers = {"PyVRP": solve_pyvrp, **_portfolio_callbacks(portfolio, fitted),
               **{METHODS[method]: _winner_callback(run) for method, run in evolutions.items()}}
    report = evaluate_external(_load_external(), solvers, seed=args.seed, budget_ms=args.budget_ms)
    report["dependencies"] = dependencies
    report["portfolio"] = {
        name: {"source_sha256": solver.hook_code_sha256, "template_sha256": solver.template_source_sha256}
        if isinstance(solver, FrozenInterfaceSolver) else {"source_sha256": solver.code_sha256}
        for name, solver in portfolio.items()
    }
    report["selectors"] = {lane: fitted[policy].metadata for lane, policy in FLEET_POLICIES.items()}
    report["evolution"] = {
        METHODS[method]: {key: run[key] for key in ("driver", "requests_used", "budget_ms", "member_budget_ms",
                                                  "portfolio_size", "training_suite", "winners",
                                                  "accepted_candidate_count", "winner_dev_coverage")}
        for method, run in evolutions.items()
    }
    label = f"all_{args.with_evolution}" if evolutions else "static"
    stem = args.output_dir / f"external_baselines_{label}_s{args.seed}_b{args.budget_ms}"
    write_report(report, stem)
    print(stem.with_suffix(".json"))


def recompute_dual_timing(report: dict[str, Any]) -> dict[str, Any]:
    """Refresh timing fields and summaries in a Track 3 report using stored rows."""
    if report.get("schema_version") != "cvrp-external-baselines-2026/v1":
        raise ValueError("invalid_track3_schema")
    budget_ms = _number(report["budget_ms"])
    if budget_ms is None or budget_ms <= 0:
        raise ValueError("invalid_track3_budget")
    for suite in report["suites"].values():
        for lane in FLEET_POLICIES:
            section = suite[lane]
            overall: dict[str, list] = {name: [] for name in section["overall"]}
            common_ids = set(section["common_completed_instance_ids"])
            for row in section["rows"]:
                if "feasible_before_deadline" not in row and row["algorithm_id"] == "PyVRP":
                    # The original runner used the wall-limited callback result.
                    row["feasible_before_deadline"] = row["feasible"] is True
                # Old selector rows recorded prediction overhead separately.
                if "total_e2e_ms" not in row and row.get("preprocess_ms") is not None:
                    row["preprocess_ms"] += _number(row.get("selector_ms")) or 0.0
                row.update(dual_timing_fields(row, budget_ms=budget_ms, feasible=row["feasible"] is True))
                overall[row["algorithm_id"]].append(row)
            for name, rows in overall.items():
                section["overall"][name].update(summarize_solve_timing(rows))
                section["common_completed"][name].update(summarize_solve_timing(
                    [row for row in rows if row["instance_id"] in common_ids],
                ))
    report["timing_protocol"] = TIMING_PROTOCOL
    report["timing_recompute"] = {
        "llm_requests": 0,
        "legacy_pyvrp_incumbent_evidence": "verified wall-limited callback return",
        "other_legacy_incumbent_evidence": "verified return with observed solve time within budget",
    }
    return report


def _run_timing_audit(args: argparse.Namespace) -> None:
    if args.input_report:
        default_name = f"{args.input_report.stem}_dual_timing"
    else:
        default_name = f"pyvrp_dual_timing_s{args.seed}_b{args.budget_ms}"
    stem = args.output or args.output_dir / default_name
    if any(stem.with_suffix(ext).exists() for ext in (".json", ".md")):
        raise ValueError(f"timing_audit_output_exists:{stem}")
    if args.input_report:
        report = recompute_dual_timing(json.loads(args.input_report.read_bytes()))
    else:
        names = (args.suite,) if args.suite else EXTERNAL_COUNTS
        suites = [_load_suite(name, "heldout", "external_evaluation", EXTERNAL_COUNTS[name]) for name in names]
        report = evaluate_external(suites, {"PyVRP": solve_pyvrp}, seed=args.seed, budget_ms=args.budget_ms)
        report["dependencies"] = {"pyvrp": version("pyvrp")}
    write_report(report, stem)
    print(stem.with_suffix(".json"))


def _run_evolution(args: argparse.Namespace) -> None:
    driver = MockDriver() if args.mode == "mock" else ParateraDriver(args.model, args.request_timeout_s)
    run_dir = _run_dir(args.output_dir, args.command, args.seed, args.mode)
    evolution = evolve(args.command, _load_dev(), seed=args.seed, request_cap=args.request_cap,
                       budget_ms=args.budget_ms, checkpoint_path=run_dir / "checkpoint.json",
                       driver=driver, portfolio_size=args.portfolio_size)
    path = run_dir / "evolution.json"
    _atomic_write_json(path, evolution)
    print(path)
    if evolution["status"] != "completed":
        raise RuntimeError(f"no_evolved_candidate:{args.command}:{args.seed}")
    if args.evaluate_external:
        def nn(instance: Mapping[str, Any], *, budget_ms: float, seed: int, **kwargs: Any) -> dict[str, Any]:
            return evaluate_algorithm_on_instance("nn", instance, time_budget_ms=budget_ms, record_trace=False, **kwargs)

        report = evaluate_external(_load_external(), {"NN": nn, METHODS[args.command]: _winner_callback(evolution)},
                                   seed=args.seed, budget_ms=args.budget_ms)
        report["evolution"] = evolution
        write_report(report, run_dir / "external")
        print(run_dir / "external.json")


def build_mux_manifest(*, output_dir: Path, mode: str = "live", model: str = MODEL, budget_ms: int = 500,
                       request_cap: int = REQUEST_CAP, portfolio_size: int = 3,
                       request_timeout_s: float = 120.0, stage: str = "evolution") -> dict[str, Any]:
    """Emit independent panes for evolution or for evaluation of finished arms."""
    command = [sys.executable, str(Path(__file__).resolve()), "--output-dir", str(Path(output_dir).resolve())]
    if stage == "benchmark":
        return {"panes": [
            {"id": f"track3_benchmark_s{seed}_b{budget}", "cwd": str(REPO), "command": [
                *command, "benchmark", "--with-evolution", mode,
                "--seed", str(seed), "--budget-ms", str(budget),
            ]}
            for budget in BUDGETS for seed in SEEDS
        ]}
    if stage != "evolution":
        raise ValueError(f"unknown_mux_stage:{stage}")
    return {"panes": [
        {"id": f"track3_{method}_s{seed}", "cwd": str(REPO), "command": [
            *command, method, "--seed", str(seed), "--budget-ms", str(budget_ms), "--request-cap", str(request_cap),
            "--mode", mode, "--model", model, "--portfolio-size", str(portfolio_size),
            "--request-timeout-s", str(request_timeout_s),
        ]}
        for method in METHODS for seed in SEEDS
    ]}


def _driver_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--mode", choices=("mock", "live"), default="mock")
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--request-cap", type=int, default=REQUEST_CAP)
    parser.add_argument("--request-timeout-s", type=float, default=120.0)
    parser.add_argument("--portfolio-size", type=int, default=3)
    parser.add_argument("--budget-ms", type=int, choices=BUDGETS, default=BUDGETS[0])


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    commands = parser.add_subparsers(dest="command", required=True)
    benchmark = commands.add_parser("benchmark", help="Evaluate PyVRP, selectors and optionally frozen evolution arms")
    benchmark.add_argument("--seed", type=int, choices=SEEDS, default=SEEDS[0])
    benchmark.add_argument("--budget-ms", type=int, choices=BUDGETS, default=BUDGETS[0])
    benchmark.add_argument("--hydra-k", type=int, default=3)
    benchmark.add_argument("--with-evolution", choices=("mock", "live"), help="Load both finished evolution arms for this seed")
    audit = commands.add_parser("recompute-dual-timing", help="Re-summarize Track 3 or rerun only PyVRP, offline")
    source = audit.add_mutually_exclusive_group(required=True)
    source.add_argument("--input-report", type=Path)
    source.add_argument("--rerun-pyvrp", action="store_true")
    audit.add_argument("--suite", choices=EXTERNAL_COUNTS, help="Restrict a PyVRP rerun to one external suite")
    audit.add_argument("--seed", type=int, choices=SEEDS, default=SEEDS[0])
    audit.add_argument("--budget-ms", type=int, choices=BUDGETS, default=BUDGETS[0])
    audit.add_argument("--output", type=Path, help="Output stem for the JSON and Markdown reports")
    for method, label in METHODS.items():
        evolution = commands.add_parser(method, aliases=["eoh-s"] if method == "eohs" else [],
                                        help=f"Run or resume one development-only {label} arm")
        _driver_options(evolution)
        evolution.add_argument("--seed", type=int, choices=SEEDS, default=SEEDS[0])
        evolution.add_argument("--evaluate-external", action="store_true", help="Also write a standalone external report")
    mux = commands.add_parser("emit-mux", help="Write six panes for tools/multi_task_mux.py")
    _driver_options(mux)
    mux.add_argument("--stage", choices=("evolution", "benchmark"), default="evolution",
                     help="The benchmark stage consumes finished arms and runs both evaluation budgets")
    mux.add_argument("--manifest", type=Path)
    args = parser.parse_args(argv)
    args.output_dir = args.output_dir.resolve()
    if args.command == "recompute-dual-timing":
        if args.input_report and args.suite:
            parser.error("--suite requires --rerun-pyvrp")
        _run_timing_audit(args)
    elif args.command == "benchmark":
        if args.hydra_k < 1:
            parser.error("--hydra-k must be positive")
        _run_benchmark(args)
    else:
        if not 1 <= args.request_cap <= REQUEST_CAP or args.portfolio_size < 1:
            parser.error("--request-cap must be in 1..100 and --portfolio-size must be positive")
        if not math.isfinite(args.request_timeout_s) or args.request_timeout_s <= 0:
            parser.error("--request-timeout-s must be positive and finite")
        if args.command == "emit-mux":
            manifest = args.manifest or (args.output_dir / f"mux_track3_{args.stage}_{args.mode}.json")
            _atomic_write_json(manifest, build_mux_manifest(
                output_dir=args.output_dir, mode=args.mode, model=args.model, budget_ms=args.budget_ms,
                request_cap=args.request_cap, portfolio_size=args.portfolio_size,
                request_timeout_s=args.request_timeout_s, stage=args.stage,
            ))
            print(manifest)
        else:
            if args.command == "eoh-s":
                args.command = "eohs"
            _run_evolution(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
