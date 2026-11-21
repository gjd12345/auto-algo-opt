"""Executable diagnostics for CVRP constructive heuristics.

Each candidate is treated as a black-box decision rule and characterised with
measurements instead of prose:

* ``margin``  - how large a relative change of the chosen edge length is needed
  before the rule picks a different node (binary search per decision step).
  A rule whose route flips under 1e-6 perturbation is deciding by numeric
  accident, not by a stable preference.
* ``symmetry`` - is the route invariant under uniform coordinate scaling, under
  scaling demands together with capacity, and how much does it move when the
  depot is displaced?  These separate homogeneous geometric rules from rules
  with absolute capacity terms or radial anchors.
* ``linear_fit`` - when the rule ranks via a numpy reduction the score vector is
  recovered and regressed on interpretable features, giving the effective
  weights and the R^2 of a linear explanation.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping

import numpy as np

# savings = d_curdep + d_dep - d_cur is exactly collinear with (d_cur, d_dep)
# inside a single decision step, so it is a derived quantity rather than a
# regressor; keeping it would make the fitted weights non-identifiable.
FEATURES = ("bias", "d_cur", "d_dep", "demand", "slack", "d_dep_x_demand")


# ---------------------------------------------------------------- loading

def load_candidate(path: Path) -> Callable[..., int]:
    source = Path(path).read_text(encoding="utf-8")
    namespace: dict[str, Any] = {"np": np, "numpy": np, "__name__": "candidate"}
    exec(compile(source, str(path), "exec"), namespace)  # noqa: S102 - research sandbox
    fn = namespace.get("select_next_node")
    if not callable(fn):
        raise ValueError(f"no select_next_node in {path}")
    return fn


# ---------------------------------------------------------------- capture

class _Capture:
    """Recover the array handed to numpy's ranking reductions."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []
        self._enabled = False

    def install(self) -> tuple[Callable, Callable, Callable]:
        original_argmin, original_argmax = np.argmin, np.argmax
        original_argsort = np.argsort

        def argmin(a, *args, **kwargs):
            out = original_argmin(a, *args, **kwargs)
            if self._enabled:
                self.events.append({"array": np.asarray(a, dtype=float).ravel().copy(), "mode": "min", "position": int(out)})
            return out

        def argmax(a, *args, **kwargs):
            out = original_argmax(a, *args, **kwargs)
            if self._enabled:
                self.events.append({"array": np.asarray(a, dtype=float).ravel().copy(), "mode": "max", "position": int(out)})
            return out

        def argsort(a, *args, **kwargs):
            out = original_argsort(a, *args, **kwargs)
            if self._enabled:
                flat = np.asarray(a, dtype=float).ravel()
                order = np.asarray(out).ravel()
                # ``np.argsort`` sorts ascending, so ``order[0]`` is the
                # minimum entry of ``a`` (e.g. ``-savings`` in rule A).
                if order.size:
                    self.events.append({"array": flat, "mode": "min", "position": int(order[0])})
            return out

        np.argmin, np.argmax, np.argsort = argmin, argmax, argsort
        return original_argmin, original_argmax, original_argsort

    def enable(self) -> None:
        self.events = []
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False


# ---------------------------------------------------------------- instances

def build_matrix(instance: Mapping[str, Any], scale: float = 1.0, depot: Any = None) -> np.ndarray:
    depot_point = list(depot) if depot is not None else list(instance["depot"])
    points = [depot_point] + [list(p) for p in instance["customer_coordinates"]]
    coords = np.asarray(points, dtype=float) * float(scale)
    delta = coords[:, None, :] - coords[None, :, :]
    return np.sqrt(np.sum(delta * delta, axis=2))


def shifted(instance: Mapping[str, Any], *, depot: tuple[float, float] | None = None,
            demand_scale: float = 1.0, capacity_scale: float = 1.0,
            jitter: float | None = None, seed: int = 11) -> dict[str, Any]:
    clone = {
        "instance_id": instance.get("instance_id"),
        "depot": list(depot if depot is not None else instance["depot"]),
        "customer_coordinates": [list(p) for p in instance["customer_coordinates"]],
        "demands": [float(d) * demand_scale for d in instance["demands"]],
        "capacity": float(instance["capacity"]) * capacity_scale,
    }
    if jitter:
        rng = np.random.default_rng(seed)
        coords = np.asarray(clone["customer_coordinates"], dtype=float)
        coords = np.clip(coords + rng.normal(0.0, jitter, coords.shape), 0.0, 1.0)
        clone["customer_coordinates"] = coords.tolist()
    return clone


@dataclass
class Step:
    current: int
    remaining: float
    feasible: list[int]
    chosen: int
    scores: np.ndarray | None = None
    mode: str | None = None


@dataclass
class RouteRun:
    route: list[int] = field(default_factory=list)
    steps: list[Step] = field(default_factory=list)
    objective: float = 0.0


# ---------------------------------------------------------------- simulate

def simulate(fn: Callable[..., int], instance: Mapping[str, Any], *,
             matrix: np.ndarray | None = None, capture: _Capture | None = None) -> RouteRun:
    matrix = build_matrix(instance) if matrix is None else matrix
    demands = np.asarray([0.0] + [float(d) for d in instance["demands"]], dtype=float)
    capacity = float(instance["capacity"])
    total = matrix.shape[0]
    unvisited = set(range(1, total))
    route = [0]
    current, remaining = 0, capacity
    steps: list[Step] = []
    guard = total * total
    while unvisited:
        guard -= 1
        if guard < 0:
            raise ValueError("invalid_route")
        feasible = sorted(node for node in unvisited if demands[node] <= remaining + 1e-12)
        if not feasible:
            route.append(0)
            current, remaining = 0, capacity
            continue
        nodes = np.asarray(feasible, dtype=int)
        if capture is not None:
            capture.enable()
        result = int(fn(current, 0, nodes.copy(), remaining, demands.copy(), matrix.copy()))
        if capture is not None:
            capture.disable()
        if result not in feasible:
            raise ValueError("invalid_route")
        step = Step(current=current, remaining=remaining, feasible=feasible, chosen=result)
        if capture is not None and capture.events:
            # Walk back from the last event: rules such as frozen A rank with
            # ``argsort`` first and break ties on a sub-array afterwards, so the
            # final event is not always the one that produced the returned node.
            for ev in reversed(capture.events):
                array = ev["array"]
                position = ev.get("position")
                # Only trust the capture when the reduction it intercepted actually
                # produced the node the rule returned; otherwise it is some helper
                # call inside the rule and the "score" is unrelated to the decision.
                if position is None or not (0 <= position < len(feasible)):
                    continue
                if feasible[position] != result:
                    continue
                if array.shape == (len(feasible),):
                    step.scores, step.mode = array, ev["mode"]
                    break
                if array.shape == (total,):
                    step.scores, step.mode = array[np.asarray(feasible, dtype=int)], ev["mode"]
                    break
        steps.append(step)
        route.append(result)
        unvisited.discard(result)
        remaining -= demands[result]
        current = result
    if route[-1] != 0:
        route.append(0)
    objective = float(sum(matrix[a, b] for a, b in zip(route, route[1:])))
    return RouteRun(route=route, steps=steps, objective=objective)


# ---------------------------------------------------------------- margin

def flip_margin(fn: Callable[..., int], instance: Mapping[str, Any], step: Step,
                matrix: np.ndarray, *, lo: float = 0.0, hi: float = 0.5,
                tol: float = 1e-6) -> float | None:
    """Smallest delta such that scaling d(current, chosen) by (1+delta) flips the choice.

    The scaling is applied only to the edge the rule actually took, so the probe
    asks: how much would this decision change if the chosen edge were slightly
    less attractive?  Returns the delta (0 means a tie already).
    """
    if len(step.feasible) < 2:
        return None
    demands = np.asarray([0.0] + [float(d) for d in instance["demands"]], dtype=float)
    nodes = np.asarray(step.feasible, dtype=int)

    def decide(delta: float) -> int:
        probe = matrix.copy()
        probe[step.current, step.chosen] *= (1.0 + delta)
        probe[step.chosen, step.current] *= (1.0 + delta)
        return int(fn(step.current, 0, nodes.copy(), step.remaining, demands.copy(), probe))

    if decide(0.0) != step.chosen:
        return 0.0
    if decide(hi) == step.chosen:
        return hi
    low, high = lo, hi
    while high - low > tol:
        mid = (low + high) / 2
        if decide(mid) == step.chosen:
            low = mid
        else:
            high = mid
    return high


def margin_profile(fn: Callable[..., int], instance: Mapping[str, Any], run: RouteRun,
                   matrix: np.ndarray, *, limit: int = 120) -> dict[str, Any]:
    values = []
    for step in run.steps[:limit]:
        value = flip_margin(fn, instance, step, matrix)
        if value is not None:
            values.append(value)
    if not values:
        return {"steps": 0}
    values.sort()
    count = len(values)
    return {
        "steps": count,
        "median": round(values[count // 2], 9),
        "p10": round(values[max(0, int(0.1 * count) - 1)], 9),
        "share_below_1e-3": round(sum(1 for v in values if v < 1e-3) / count, 4),
        "share_at_bound": round(sum(1 for v in values if v >= 0.5) / count, 4),
    }


# ---------------------------------------------------------------- invariances

def invariances(fn: Callable[..., int], instance: Mapping[str, Any]) -> dict[str, Any]:
    base = simulate(fn, instance)
    out: dict[str, Any] = {"base_objective": round(base.objective, 6)}
    for scale in (1e-3, 1e3):
        run = simulate(fn, instance, matrix=build_matrix(instance, scale=scale))
        out[f"coord_scale_{scale:g}_route_identical"] = run.route == base.route
    runs = simulate(fn, instance, matrix=build_matrix(instance, scale=2.0))
    out["coord_scale_2_route_identical"] = runs.route == base.route
    # demand and capacity scaled together: ratio-based rules must be invariant.
    twin = shifted(instance, demand_scale=3.0, capacity_scale=3.0)
    run = simulate(fn, twin)
    out["demand_capacity_ratio_scaled_route_identical"] = run.route == base.route
    # depot displaced towards a corner: radial rules must react most.
    depot = instance["depot"]
    moved = (round(min(0.98, depot[0] + 0.45), 8), round(min(0.98, depot[1] + 0.45), 8))
    run = simulate(fn, shifted(instance, depot=moved))
    out["depot_shift_route_identical"] = run.route == base.route
    out["depot_shift_objective_delta_pct"] = round(100.0 * (run.objective - base.objective) / base.objective, 3)
    # small geometric jitter of customers
    run = simulate(fn, shifted(instance, jitter=0.01))
    out["customer_jitter_objective_delta_pct"] = round(100.0 * (run.objective - base.objective) / base.objective, 3)
    return out


# ---------------------------------------------------------------- linear fit

def features(instance: Mapping[str, Any], matrix: np.ndarray, step: Step) -> np.ndarray:
    depot, current, remaining = 0, step.current, step.remaining
    demands = np.asarray([0.0] + [float(d) for d in instance["demands"]], dtype=float)
    capacity = float(instance["capacity"])
    d_curdep = float(matrix[current, depot])
    rows = []
    for node in step.feasible:
        d_cur = float(matrix[current, node])
        d_dep = float(matrix[depot, node])
        demand = float(demands[node])
        slack = (remaining - demand) / capacity
        savings = d_curdep + d_dep - d_cur
        rows.append([1.0, d_cur, d_dep, demand, slack, d_dep * demand])
    return np.asarray(rows, dtype=float)


def linear_fit(instance: Mapping[str, Any], matrix: np.ndarray, steps: list[Step]) -> dict[str, Any]:
    xs, ys = [], []
    xs_dm, ys_dm = [], []
    for step in steps:
        if step.scores is None or len(step.feasible) != step.scores.size:
            continue
        f_mat = features(instance, matrix, step)
        xs.append(f_mat)
        ys.append(step.scores)
        if f_mat.shape[0] >= 2:
            # Step-demeaned (fixed-effect) regression removes step-level offsets
            # such as d(0, current) in savings = d(0, cur) + d(0, j) - d(cur, j),
            # isolating true within-step linearity of candidate ranking.
            xs_dm.append(f_mat[:, 1:] - f_mat[:, 1:].mean(axis=0, keepdims=True))
            ys_dm.append(step.scores - step.scores.mean())
    if not xs:
        return {"captured_steps": 0}
    X, y = np.vstack(xs), np.concatenate(ys)
    keep = np.isfinite(X).all(axis=1) & np.isfinite(y)
    X, y = X[keep], y[keep]
    if X.shape[0] < X.shape[1] + 2:
        return {"captured_steps": int(len(xs))}
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    residual = y - X @ coef
    ss_res = float(np.sum(residual ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2)) or 1.0
    scale = float(np.max(np.abs(y))) or 1.0
    out: dict[str, Any] = {
        "captured_steps": int(len(xs)),
        "rows": int(X.shape[0]),
        "r2": round(1.0 - ss_res / ss_tot, 6),
        "rmse_rel": round(math.sqrt(ss_res / max(len(y), 1)) / scale, 6),
        "coef": {name: round(float(value), 6) for name, value in zip(FEATURES, coef)},
    }
    if xs_dm:
        X_dm, y_dm = np.vstack(xs_dm), np.concatenate(ys_dm)
        keep_dm = np.isfinite(X_dm).all(axis=1) & np.isfinite(y_dm)
        X_dm, y_dm = X_dm[keep_dm], y_dm[keep_dm]
        if X_dm.shape[0] >= X_dm.shape[1] + 2:
            coef_dm, *_ = np.linalg.lstsq(X_dm, y_dm, rcond=None)
            res_dm = y_dm - X_dm @ coef_dm
            tot_dm = float(np.sum(y_dm ** 2)) or 1.0
            out["r2_within_step"] = round(1.0 - float(np.sum(res_dm ** 2)) / tot_dm, 6)
            out["coef_within_step"] = {
                name: round(float(value), 6) for name, value in zip(FEATURES[1:], coef_dm)
            }
    return out


# ---------------------------------------------------------------- driver

def analyze_code(path: Path, instances: list[Mapping[str, Any]], *, margin_limit: int = 120) -> dict[str, Any]:
    fn = load_candidate(path)
    capture = _Capture()
    original = capture.install()
    per_instance: list[dict[str, Any]] = []
    try:
        for instance in instances:
            matrix = build_matrix(instance)
            run = simulate(fn, instance, matrix=matrix, capture=capture)
            per_instance.append({
                "instance_id": instance.get("instance_id"),
                "objective": round(run.objective, 6),
                "steps": len(run.steps),
                "margin": margin_profile(fn, instance, run, matrix, limit=margin_limit),
                "invariance": invariances(fn, instance),
                "linear": linear_fit(instance, matrix, run.steps),
            })
    finally:
        np.argmin, np.argmax, np.argsort = original

    def collect(key: str) -> list[float]:
        return [row["margin"][key] for row in per_instance if row["margin"].get(key) is not None]

    r2 = [row["linear"]["r2"] for row in per_instance if "r2" in row["linear"]]
    r2_ws = [row["linear"]["r2_within_step"] for row in per_instance if "r2_within_step" in row["linear"]]
    coefs = [row["linear"]["coef"] for row in per_instance if "coef" in row["linear"]]
    coefs_ws = [row["linear"]["coef_within_step"] for row in per_instance if "coef_within_step" in row["linear"]]
    return {
        "candidate": Path(path).name,
        "path": Path(path).as_posix(),
        "instances": per_instance,
        "summary": {
            "mean_objective": round(float(np.mean([row["objective"] for row in per_instance])), 6),
            "decisions_probed": int(sum(row["margin"].get("steps", 0) for row in per_instance)),
            "margin_median": round(float(np.median(collect("median"))), 9) if collect("median") else None,
            "margin_p10": round(float(np.median(collect("p10"))), 9) if collect("p10") else None,
            "share_below_1e-3": round(float(np.mean(collect("share_below_1e-3"))), 4) if collect("share_below_1e-3") else None,
            "coord_scale_invariant": all(
                row["invariance"].get("coord_scale_0.001_route_identical") and
                row["invariance"].get("coord_scale_1000_route_identical")
                for row in per_instance),
            "ratio_scaled_invariant": all(row["invariance"].get("demand_capacity_ratio_scaled_route_identical") for row in per_instance),
            "depot_shift_routes_changed": sum(1 for row in per_instance if not row["invariance"].get("depot_shift_route_identical")),
            "linear_r2_median": round(float(np.median(r2)), 6) if r2 else None,
            "linear_r2_within_step_median": round(float(np.median(r2_ws)), 6) if r2_ws else None,
            "linear_coef_median": {
                name: round(float(np.median([coef[name] for coef in coefs])), 6) for name in FEATURES
            } if coefs else None,
            "linear_coef_within_step_median": {
                name: round(float(np.median([coef[name] for coef in coefs_ws])), 6) for name in FEATURES[1:]
            } if coefs_ws else None,
        },
    }


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", action="append", required=True)
    parser.add_argument("--suite", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--margin-limit", type=int, default=120)
    args = parser.parse_args(argv)
    suite = json.loads(Path(args.suite).read_text(encoding="utf-8"))
    instances = suite["instances"] if isinstance(suite, Mapping) else suite
    report = {
        "suite": Path(args.suite).as_posix(),
        "instance_count": len(instances),
        "candidates": [analyze_code(Path(item), instances, margin_limit=args.margin_limit) for item in args.candidate],
    }
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_bytes(json.dumps(report, ensure_ascii=False, indent=2).encode("utf-8") + b"\n")
    print(json.dumps({c["candidate"]: c["summary"] for c in report["candidates"]}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
