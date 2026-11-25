"""CVRP solver and algorithm-selection adapters for the 2026 external study."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from itertools import combinations, product
import math
import time
from typing import Any, Mapping, Sequence

import numpy as np

from agent_skill_loop.benchmark.catalog import load_profile_suite
from agent_skill_loop.benchmark.contracts import ALLOWED_VEHICLE_LIMIT_POLICIES
from agent_skill_loop.interface_design.contracts import FrozenInterfaceSolver, classify_outcome
from agent_skill_loop.interface_design.runtime import evaluate_frozen_interface_solver

from .protocol import prepare_instance_arrays, verify_cvrp_solution
from .solvers import SolverSpec, evaluate_algorithm_on_instance, get_solver_spec
from .suites import BENCHMARK_ID


SCALE = 10_000
DEFAULT_SEED = 20261124
FREE_FLEET_POLICY = "free_fleet_min_k_lb"
TRAINING_SPLITS = {
    "cvrp_dev_hetero_24": "dev_train",
    "cvrp_select_multiscale_64": "selection",
}
PORTFOLIO_ALGORITHMS = (
    "nn",
    "savings_pointwise",
    "s2_r5_spiral",
    "s2_r7_iso",
    "cw_parallel_merge",
    "cw_2opt",
    "cw_relocate_2opt",
)

PortfolioSolver = SolverSpec | FrozenInterfaceSolver


def timing_value(value: Any) -> float | None:
    if isinstance(value, (int, float, np.integer, np.floating)) and not isinstance(value, bool):
        if math.isfinite(value) and value >= 0:
            return float(value)
    return None


def dual_timing_fields(result: Mapping[str, Any], *, budget_ms: float, feasible: bool) -> dict[str, Any]:
    """Apply the solve-only deadline to a result verified under the target fleet."""
    preprocess_ms = timing_value(result.get("preprocess_ms"))
    solve_ms = timing_value(result.get("solve_ms"))
    verify_ms = timing_value(result.get("verify_ms"))
    stages = (preprocess_ms, solve_ms, verify_ms)
    overrun_ms = timing_value(result.get("deadline_overrun_ms"))
    if solve_ms is not None:
        overrun_ms = max(overrun_ms or 0.0, solve_ms - budget_ms, 0.0)
    within_deadline = solve_ms is not None and solve_ms <= budget_ms and overrun_ms == 0
    exhausted = (
        result.get("budget_exhausted") is True or result.get("time_limit_reached") is True
        or result.get("status") == "timeout" or bool(result.get("timeout_kind"))
        or result.get("solve_censored") is True
    )
    incumbent = result.get("feasible_before_deadline")
    returned = bool(feasible and within_deadline and not exhausted)
    return {
        "budget_ms": budget_ms,
        "preprocess_ms": preprocess_ms,
        "solve_ms": solve_ms,
        "verify_ms": verify_ms,
        "total_e2e_ms": sum(stages) if all(stage is not None for stage in stages) else None,
        "deadline_overrun_ms": overrun_ms,
        "solve_censored": exhausted,
        "feasible_before_deadline": returned or incumbent is True or (
            feasible and incumbent is None and within_deadline
        ),
        "returned_before_deadline": returned,
    }


def summarize_solve_timing(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Report nearest-rank latency bounds, retaining every timed-out observation.

    Right-censored solves contribute their observed duration (or the budget when
    duration is missing). A lower-bound flag marks quantiles that could increase
    if the censored solves had been allowed to finish.
    """
    lower, upper = [], []
    censored = 0
    for row in rows:
        elapsed = timing_value(row.get("solve_ms"))
        is_censored = bool(
            row.get("solve_censored") or row.get("budget_exhausted")
            or row.get("time_limit_reached") or row.get("status") == "timeout"
            or row.get("timeout_kind")
        )
        censored += is_censored
        if is_censored and elapsed is None:
            elapsed = timing_value(row.get("budget_ms"))
        if elapsed is not None:
            lower.append(elapsed)
            upper.append(math.inf if is_censored else elapsed)
    lower.sort()
    upper.sort()
    summary = {
        "solve_ms_observation_count": len(lower),
        "solve_ms_missing_count": len(rows) - len(lower),
        "solve_ms_censored_count": censored,
    }
    for label, fraction in (("solve_ms_p50", 0.50), ("solve_ms_p95", 0.95)):
        index = math.ceil(fraction * len(lower)) - 1
        summary[label] = lower[index] if lower else None
        summary[f"{label}_is_lower_bound"] = bool(lower and lower[index] < upper[index])
    for field in ("feasible_before_deadline", "returned_before_deadline"):
        count = sum(row.get(field) is True for row in rows)
        summary[f"{field}_count"] = count
        summary[f"{field}_rate"] = count / len(rows) if rows else None
    return summary


def solve_pyvrp(
    instance: Mapping[str, Any],
    *,
    budget_ms: float,
    seed: int = DEFAULT_SEED,
    distance_convention: str = "euc_2d_float",
    vehicle_limit_policy: str = FREE_FLEET_POLICY,
    enforce_wall_deadline: bool = True,
) -> dict[str, Any]:
    """Run PyVRP 0.14.1 and remeasure the result under the workbench protocol.

    Float Euclidean edges enter the integer solver at a fixed-point scale.
    CVRPLib integer-rounded edges enter unchanged. Both cases are independently
    verified in float Euclidean distance, with CVRPLib also scored in its native
    convention. Native search checks time cooperatively at iteration boundaries.
    """
    from pyvrp import (
        Client, Depot, IteratedLocalSearchCallbacks, IteratedLocalSearchParams,
        Location, ProblemData, SolveParams, VehicleType, solve,
    )
    from pyvrp.stop import MaxRuntime

    if not math.isfinite(budget_ms) or budget_ms <= 0:
        raise ValueError("pyvrp_budget_must_be_positive")
    if vehicle_limit_policy not in ALLOWED_VEHICLE_LIMIT_POLICIES:
        raise ValueError(f"unsupported_vehicle_limit_policy:{vehicle_limit_policy}")

    preprocess_started = time.perf_counter()
    matrix, demands, capacity = prepare_instance_arrays(instance, distance_convention)
    num_clients = len(demands) - 1
    target = instance.get("k_vehicles")
    if target is None:
        target = instance.get("max_vehicles")
    if target is not None and (
        isinstance(target, bool) or int(target) != target or int(target) < 1
    ):
        raise ValueError("pyvrp_vehicle_target_must_be_a_positive_integer")
    has_fleet_limit = target is not None and vehicle_limit_policy != FREE_FLEET_POLICY
    num_vehicles = int(target) if has_fleet_limit else num_clients
    verification_policy = "strict_max_vehicles" if has_fleet_limit else vehicle_limit_policy

    # Every registered suite uses integral demands. Preserve decimal test inputs
    # to the same precision as the verifier's capacity tolerance.
    loads = [Decimal(str(value)).normalize() for value in (*demands[1:], capacity)]
    load_digits = min(9, max(0, max(-value.as_tuple().exponent for value in loads)))
    load_scale = 10**load_digits
    *int_demands, int_capacity = [round(value * load_scale) for value in loads]
    distance_scale = SCALE if distance_convention == "euc_2d_float" else 1
    distances = np.floor(matrix * distance_scale + 0.5).astype(np.int64)
    locations = [
        Location(float(x), float(y))
        for x, y in (instance["depot"], *instance["customer_coordinates"])
    ]
    data = ProblemData(
        locations,
        [Client(idx, delivery=[delivery]) for idx, delivery in enumerate(int_demands, 1)],
        [Depot(0)],
        [VehicleType(num_available=num_vehicles, capacity=[int_capacity])],
        [distances],
        [np.zeros_like(distances)],
    )

    started = time.perf_counter()
    max_runtime = MaxRuntime(budget_ms / 1000.0)
    deadline = started + budget_ms / 1000.0
    stopped_at_limit = False
    incumbents = []
    exact_k = vehicle_limit_policy == "strict_max_vehicles" and target is not None

    class IncumbentRecorder(IteratedLocalSearchCallbacks):
        def on_start(self, ils):
            self.on_best(ils.initial_solution)

        def on_best(self, best):
            observed = time.perf_counter()
            if (observed <= deadline and best.is_feasible()
                    and (not exact_k or len(best.routes()) == target)):
                incumbents.append((best, (observed - started) * 1000.0))

    def stop(best_cost: int) -> bool:
        nonlocal stopped_at_limit
        stopped_at_limit = max_runtime(best_cost) or (
            enforce_wall_deadline and time.perf_counter() >= deadline
        )
        return stopped_at_limit

    params = SolveParams(ils=IteratedLocalSearchParams(callbacks=IncumbentRecorder()))
    result = solve(data, stop, seed=seed, collect_stats=False, display=False, params=params)
    solve_ms = (time.perf_counter() - started) * 1000.0
    # PyVRP 0.14.x iterates ScheduledActivity objects. A client activity index
    # is zero-based among clients, whereas the workbench reserves node 0.
    def extract_routes(solution):
        return [
            [0, *(int(activity.idx) + 1 for activity in route if activity.is_client()), 0]
            for route in solution.routes()
        ] if solution is not None else []

    def fleet_feasible(verification):
        return verification["valid"] is True and (not exact_k or verification["exact_vehicle_count"] is True)

    def verify(solution):
        routes = extract_routes(solution)
        verified_float = verify_cvrp_solution(
            instance, routes, distance_convention="euc_2d_float", vehicle_limit_policy=verification_policy,
        )
        verified = verified_float
        if distance_convention != "euc_2d_float" and verified_float["valid"]:
            verified = verify_cvrp_solution(
                instance, routes, distance_convention=distance_convention,
                vehicle_limit_policy=verification_policy,
            )
        return routes, verified_float, verified

    verify_started = time.perf_counter()
    best_in_time, incumbent_ms, incumbent_verification = None, None, None
    for candidate, observed_ms in reversed(incumbents):
        verification = verify(candidate)
        if fleet_feasible(verification[2]):
            best_in_time, incumbent_ms, incumbent_verification = candidate, observed_ms, verification
            break
    best = result.best
    if enforce_wall_deadline and (best_in_time is not None or solve_ms > budget_ms):
        best = best_in_time
    routes, verified_float, verified = (
        incumbent_verification if best is best_in_time and incumbent_verification is not None else verify(best)
    )
    feasible = fleet_feasible(verified)
    # Reaching the configured time limit is normal for this time-boxed solver.
    # Ignore improvements produced by a native iteration that crosses the deadline.
    time_limit_reached = stopped_at_limit or solve_ms > budget_ms
    exhausted = time_limit_reached and not feasible
    status = "ok" if feasible else "timeout" if exhausted else "infeasible"
    timing = dual_timing_fields({
        "preprocess_ms": (started - preprocess_started) * 1000.0,
        "solve_ms": solve_ms,
        "verify_ms": (time.perf_counter() - verify_started) * 1000.0,
        "budget_exhausted": exhausted,
        "time_limit_reached": time_limit_reached,
    }, budget_ms=budget_ms, feasible=feasible)
    return {
        **verified,
        "algorithm_id": "PyVRP",
        "problem_family": "cvrp",
        "instance_id": instance.get("instance_id"),
        "distance_convention": distance_convention,
        "vehicle_limit_policy": vehicle_limit_policy,
        "objective": verified["tour_length"] if feasible else None,
        "tour_length_euc_2d_float": verified_float["tour_length"],
        "routes": routes,
        "feasible": feasible,
        "completed": feasible,
        "status": status,
        "error_code": ("no_incumbent_by_deadline" if exhausted and best is None
                       else "exact_vehicle_count_mismatch" if verified["valid"] and not feasible
                       else verified["error_code"]),
        "outcome_class": classify_outcome(valid=feasible, status=status, budget_exhausted=exhausted),
        "budget_exhausted": exhausted,
        "time_limit_reached": time_limit_reached,
        "stop_reason": "time_limit" if time_limit_reached else "completed",
        "timeout_kind": "solve_deadline" if exhausted else None,
        **timing,
        "feasible_before_deadline": best_in_time is not None or timing["feasible_before_deadline"],
        "incumbent_ms": incumbent_ms,
        "reference_objective": instance.get("reference_objective"),
        "reference_kind": instance.get("reference_kind"),
        "solver_meta": {
            "distance_scale": distance_scale,
            "load_scale": load_scale,
            "num_vehicles": num_vehicles,
            "seed": seed,
            "iterations": result.num_iterations,
        },
    }


def load_portfolio() -> dict[str, PortfolioSolver]:
    """Load the verified heuristic catalog and existing frozen champion/L3 arms."""
    from agent_skill_loop.interface_design.blind_eval_m3 import (
        M3_EXTRA_L3_SOLVER_ID,
        load_phase3c_frozen_roster,
    )
    from tools.run_b4_intron_ablation import (
        build_pruned_m32_champion,
        load_m32_champion_solver,
        load_raw_m32_champion,
    )

    portfolio: dict[str, PortfolioSolver] = {name: get_solver_spec(name) for name in PORTFOLIO_ALGORITHMS}
    champion = load_m32_champion_solver(build_pruned_m32_champion(load_raw_m32_champion()))
    roster = {solver.solver_id: solver for solver in load_phase3c_frozen_roster()}
    for solver in (champion, roster["m3_l3_ctrl_500ms"], roster[M3_EXTRA_L3_SOLVER_ID]):
        portfolio[solver.solver_id] = solver
    return portfolio


def evaluate_portfolio_solver(
    solver: PortfolioSolver,
    instance: Mapping[str, Any],
    *,
    budget_ms: float,
    distance_convention: str,
    vehicle_limit_policy: str,
) -> dict[str, Any]:
    """Evaluate a single fixed member with the repository's runtime and verifier."""
    if isinstance(solver, FrozenInterfaceSolver):
        return evaluate_frozen_interface_solver(
            solver, instance, distance_convention=distance_convention,
            vehicle_limit_policy=vehicle_limit_policy, solve_deadline_ms=budget_ms,
            enforce_wall_deadline=True,
        )
    return evaluate_algorithm_on_instance(
        solver.algorithm_id, instance, distance_convention=distance_convention,
        vehicle_limit_policy=vehicle_limit_policy, time_budget_ms=budget_ms,
        record_trace=False, enforce_wall_deadline=True,
    )


def extract_cvrp_instance_features(instance: Mapping[str, Any]) -> dict[str, float]:
    """Extract pre-solve features invariant to coordinate and demand units."""
    points = np.asarray([instance["depot"], *instance["customer_coordinates"]], dtype=np.float64)
    demands = np.asarray(instance["demands"], dtype=np.float64)
    capacity = float(instance["capacity"])
    if (
        demands.ndim != 1
        or points.shape != (demands.size + 1, 2)
        or not demands.size
        or not np.all(np.isfinite(points))
        or not np.all(np.isfinite(demands))
        or np.any(demands < 0)
        or not math.isfinite(capacity)
        or capacity <= 0
    ):
        raise ValueError("invalid_cvrp_feature_input")

    relative = points[1:] - points[0]
    span = float(np.ptp(points, axis=0).max())
    if span:
        relative /= span
    radial = np.linalg.norm(relative, axis=1)
    direction = np.divide(
        relative, radial[:, None], out=np.zeros_like(relative), where=radial[:, None] > 0,
    )
    pairwise = np.linalg.norm(relative[:, None, :] - relative[None, :, :], axis=2)
    n = len(demands)
    if n > 1:
        pair_mean = float(pairwise.sum()) / (n * (n - 1))
        np.fill_diagonal(pairwise, np.inf)
        nearest = pairwise.min(axis=1)
    else:
        pair_mean = 0.0
        nearest = np.zeros(1)

    loads = demands / capacity
    load_mean, nn_mean = float(loads.mean()), float(nearest.mean())
    spread = relative.std(axis=0)
    return {
        "log_n": math.log(n),
        "demand_mean_over_capacity": load_mean,
        "demand_max_over_capacity": float(loads.max()),
        "demand_cv": float(loads.std() / load_mean) if load_mean else 0.0,
        "demand_iqr_over_capacity": float(np.quantile(loads, 0.75) - np.quantile(loads, 0.25)),
        "total_demand_over_capacity": float(loads.sum()),
        "radial_mean_over_span": float(radial.mean()),
        "radial_std_over_span": float(radial.std()),
        "radial_q90_over_span": float(np.quantile(radial, 0.90)),
        "depot_centroid_distance_over_span": float(np.linalg.norm(relative.mean(axis=0))),
        "depot_angle_dispersion": max(0.0, 1.0 - float(np.linalg.norm(direction.mean(axis=0)))),
        "x_spread_over_span": float(spread[0]),
        "y_spread_over_span": float(spread[1]),
        "nn_over_mean_pair_distance": nn_mean / pair_mean if pair_mean else 0.0,
        "nn_distance_cv": float(nearest.std() / nn_mean) if nn_mean else 0.0,
    }


def validate_training_suite(suite: Mapping[str, Any]) -> dict[str, Any]:
    """Check each training row against its hash-verified authorized manifest."""
    suite_id, split = suite.get("suite_id"), suite.get("split")
    if suite_id not in TRAINING_SPLITS or TRAINING_SPLITS[suite_id] != split:
        raise ValueError(f"unauthorized_training_suite:{suite_id}:{split}")
    canonical = load_profile_suite(BENCHMARK_ID, suite_id, split=split)
    if suite.get("data_manifest_hash", canonical["data_manifest_hash"]) != canonical["data_manifest_hash"]:
        raise ValueError(f"training_manifest_hash_mismatch:{suite_id}")
    trusted = {row["instance_id"]: row for row in canonical["instances"]}
    instances = suite.get("instances")
    if not isinstance(instances, Sequence) or not instances:
        raise ValueError(f"empty_training_suite:{suite_id}")
    seen: set[str] = set()
    for instance in instances:
        instance_id = instance.get("instance_id") if isinstance(instance, Mapping) else None
        if not isinstance(instance_id, str) or instance_id in seen or trusted.get(instance_id) != instance:
            raise ValueError(f"noncanonical_training_instance:{suite_id}:{instance_id}")
        seen.add(instance_id)
    return {
        "suite_id": suite_id,
        "split": split,
        "instance_count": len(instances),
        "data_manifest_hash": canonical["data_manifest_hash"],
    }


def select_complementary(cost_matrix: np.ndarray, k: int) -> tuple[int, ...]:
    """Greedily minimize the mean per-instance best cost of a size-k portfolio."""
    costs = np.asarray(cost_matrix, dtype=np.float64)
    if (
        costs.ndim != 2 or costs.shape[0] == 0 or isinstance(k, bool) or not isinstance(k, int)
        or not 1 <= k <= costs.shape[1] or not np.all(np.isfinite(costs)) or np.any(costs < 0)
    ):
        raise ValueError("invalid_complementary_portfolio_costs_or_size")
    remaining = list(range(costs.shape[1]))
    current_best = np.full(costs.shape[0], np.inf)
    selected = []
    for _ in range(k):
        candidate_costs = np.minimum(current_best[:, None], costs[:, remaining])
        index = int(candidate_costs.mean(axis=0).argmin())
        current_best = candidate_costs[:, index]
        selected.append(remaining.pop(index))
    return tuple(selected)


@dataclass(frozen=True)
class _PairwiseRidge:
    """Regress signed cost differences, weighting informative pairs by regret."""

    solver_count: int
    models: tuple[tuple[int, int, Any], ...]

    @classmethod
    def fit(cls, features: np.ndarray, costs: np.ndarray) -> _PairwiseRidge:
        from sklearn.linear_model import Ridge
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler

        models = []
        for left, right in combinations(range(costs.shape[1]), 2):
            difference = costs[:, left] - costs[:, right]
            weight = np.abs(difference)
            # Keep ties in the training data and weight large regrets more.
            mean_weight = float(weight.mean())
            sample_weight = 1.0 + weight / mean_weight if mean_weight else np.ones_like(weight)
            model = make_pipeline(StandardScaler(), Ridge(alpha=1.0))
            model.fit(features, difference, ridge__sample_weight=sample_weight)
            models.append((left, right, model))
        return cls(costs.shape[1], tuple(models))

    def predict(self, features: np.ndarray) -> np.ndarray:
        scores = np.zeros((len(features), self.solver_count))
        for left, right, model in self.models:
            difference = model.predict(features)
            scores[:, left] += difference
            scores[:, right] -= difference
        return scores.argmin(axis=1)


def _fit_autofolio_models(
    features: np.ndarray, costs: np.ndarray, *, max_depth: int | None, min_leaf: int, seed: int,
) -> tuple[Any, Any]:
    from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor

    labels = costs.argmin(axis=1)
    regret = costs.mean(axis=1) - costs.min(axis=1)
    mean_regret = float(regret.mean())
    weights = 1.0 + regret / mean_regret if mean_regret > 0 else np.ones_like(regret)
    classifier = DecisionTreeClassifier(max_depth=max_depth, min_samples_leaf=min_leaf, random_state=seed)
    regressor = DecisionTreeRegressor(max_depth=max_depth, min_samples_leaf=min_leaf, random_state=seed)
    classifier.fit(features, labels, sample_weight=weights)
    regressor.fit(features, costs, sample_weight=weights)
    return classifier, regressor


def _predict_autofolio(
    models: tuple[Any, Any], features: np.ndarray, shortlist_size: int,
) -> np.ndarray:
    classifier, regressor = models
    costs = np.asarray(regressor.predict(features)).reshape(len(features), -1)
    probabilities = np.zeros_like(costs)
    probabilities[:, classifier.classes_] = classifier.predict_proba(features)
    shortlist = np.argsort(-probabilities, axis=1, kind="stable")[:, :shortlist_size]
    shortlist_cost = np.take_along_axis(costs, shortlist, axis=1)
    return shortlist[np.arange(len(features)), shortlist_cost.argmin(axis=1)]


def _cross_validate_autofolio(
    features: np.ndarray, costs: np.ndarray, *, seed: int,
) -> tuple[tuple[Any, Any], dict[str, Any]]:
    from sklearn.model_selection import KFold

    folds = list(KFold(n_splits=min(5, len(features)), shuffle=True, random_state=seed).split(features))
    candidate_sizes = sorted({1, min(2, costs.shape[1]), costs.shape[1]})
    best_cost = math.inf
    best_parameters = (None, 1, 1)
    for max_depth, min_leaf in product((3, 6, None), (2, 5)):
        fold_cost = dict.fromkeys(candidate_sizes, 0.0)
        for train, validation in folds:
            models = _fit_autofolio_models(
                features[train], costs[train], max_depth=max_depth, min_leaf=min_leaf, seed=seed,
            )
            for size in candidate_sizes:
                prediction = _predict_autofolio(models, features[validation], size)
                fold_cost[size] += float(costs[validation, prediction].sum())
        for size, total in fold_cost.items():
            if total < best_cost:
                best_cost, best_parameters = total, (max_depth, min_leaf, size)

    depth, leaf, size = best_parameters
    model = _fit_autofolio_models(features, costs, max_depth=depth, min_leaf=leaf, seed=seed)
    return model, {
        "max_depth": depth,
        "min_samples_leaf": leaf,
        "shortlist_size": size,
        "folds": len(folds),
        "cross_validated_mean_cost": best_cost / len(features),
    }


@dataclass(frozen=True)
class SelectorSuite:
    """Fitted CVRP selectors and the training-only single best solver."""

    solver_names: tuple[str, ...]
    sbs: str
    hydra_portfolio: tuple[str, ...]
    metadata: dict[str, Any]
    _satzilla: _PairwiseRidge
    _autofolio: tuple[Any, Any]
    _hydra: _PairwiseRidge

    def predict(self, instance: Mapping[str, Any]) -> dict[str, str]:
        features = np.asarray([list(extract_cvrp_instance_features(instance).values())])
        autofolio = _predict_autofolio(
            self._autofolio, features, self.metadata["autofolio"]["shortlist_size"],
        )
        return {
            "SATzilla": self.solver_names[self._satzilla.predict(features)[0]],
            "AutoFolio": self.solver_names[autofolio[0]],
            "Hydra": self.hydra_portfolio[self._hydra.predict(features)[0]],
            "SBS": self.sbs,
        }


def fit_selectors(
    suites: Sequence[Mapping[str, Any]],
    costs: Mapping[str, Mapping[str, float]],
    *,
    solver_names: Sequence[str],
    hydra_k: int = 3,
    seed: int = DEFAULT_SEED,
) -> SelectorSuite:
    """Fit over authorized dev and selection rows with penalized normalized costs."""
    training_metadata = [validate_training_suite(suite) for suite in suites]
    if len(training_metadata) != len(TRAINING_SPLITS) or {
        row["suite_id"] for row in training_metadata
    } != set(TRAINING_SPLITS):
        raise ValueError("selectors_require_dev_train_and_selection")
    by_id = {row["instance_id"]: row for suite in suites for row in suite["instances"]}
    if len(by_id) != sum(row["instance_count"] for row in training_metadata):
        raise ValueError("duplicate_selector_training_instance")
    if set(by_id) != set(costs):
        raise ValueError("selector_costs_must_match_authorized_training_instances")

    names = tuple(solver_names)
    if not names or len(set(names)) != len(names) or not all(isinstance(name, str) and name for name in names):
        raise ValueError("invalid_selector_solver_names")
    if any(set(row) != set(names) for row in costs.values()):
        raise ValueError("selector_costs_must_match_portfolio")
    ids = sorted(by_id)
    matrix = np.asarray([[costs[instance_id][name] for name in names] for instance_id in ids], dtype=np.float64)
    hydra_indices = select_complementary(matrix, hydra_k)
    extracted = [extract_cvrp_instance_features(by_id[instance_id]) for instance_id in ids]
    features = np.asarray([list(row.values()) for row in extracted], dtype=np.float64)
    sbs = names[int(matrix.mean(axis=0).argmin())]
    autofolio, autofolio_metadata = _cross_validate_autofolio(features, matrix, seed=seed)
    hydra_portfolio = tuple(names[index] for index in hydra_indices)
    return SelectorSuite(
        solver_names=names,
        sbs=sbs,
        hydra_portfolio=hydra_portfolio,
        metadata={
            "training_suites": training_metadata,
            "training_instance_ids": ids,
            "normalized_training_costs": {
                instance_id: dict(zip(names, row.tolist(), strict=True))
                for instance_id, row in zip(ids, matrix, strict=True)
            },
            "feature_names": list(extracted[0]),
            "seed": seed,
            "autofolio": autofolio_metadata,
            "hydra_portfolio": list(hydra_portfolio),
            "sbs": sbs,
        },
        _satzilla=_PairwiseRidge.fit(features, matrix),
        _autofolio=autofolio,
        _hydra=_PairwiseRidge.fit(features, matrix[:, hydra_indices]),
    )
