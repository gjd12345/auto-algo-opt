"""Diagonal-Newton decision contract for the six-mirror search.

The evolved entrypoint returns a relative step or an Armijo index. Finite
differences stay here. The production path builds one pinned wavefront;
oracle tests pass a callable and do not import optics_optim.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Callable, Mapping

import numpy as np

from agent_skill_loop.problems.six_mirror_physics import TREE_SHA256, WHEEL_SHA256, PinnedNumpyWavefront

PROBLEM_NAME = "six_mirror_newton"
ENTRYPOINT = "select_diagonal_newton_step"
DIMENSION = 62
SPLIT_OFFSETS = {"dev_train": 0x5EED0032}

# batch_size only chunks the oracle; it does not change the step.
EVALUATOR_CONSTANTS = {
    "eps": 1e-5,
    "zero_scale": 0.0,
    "armijo_c1": 0.1,
    "gradient_tolerance": 1e-8,
    "max_iterations": 2,
    "initial_step": 1.0,
    "backtrack_factor": 0.5,
    "max_backtracks": 12,
    "initial_scale": 1.0,
    "batch_size": 8,
}

TEMPLATE_PROGRAM = '''
def select_diagonal_newton_step(phase, scale, gradient, hessian, current_value, slope, trial_alpha, trial_value):
    """Decide one diagonal relative step, then one Armijo trial.

    phase 0: return q with shape (62,). The evaluator forms p = scale * q.
    Do not multiply q by scale. phase 1: return a 0-d integer index, a
    length-1 integer array, or -1 to accept nothing. Booleans are invalid.
    Evolve only this decision. Probes, ray tracing, prescription decoding,
    and RMS stay outside the genome. torch, scipy, files, and network
    access are forbidden. Inputs are read-only.
    """
    if int(phase) == 0:
        return np.zeros_like(gradient, dtype=np.float64)
    return np.asarray(-1, dtype=np.int64)
'''.strip()

TASK_DESCRIPTION = (
    "Choose a diagonal relative Newton step and then one Armijo trial for a "
    "fixed six-mirror search. phase 0 returns q with shape (62,); the evaluator "
    "forms p = scale * q. phase 1 returns an index into the evaluator's trials "
    "or -1. Only this decision is evolved. Finite-difference probes, ray tracing, "
    "prescription decoding, and RMS stay outside the genome. Minimise the mean RMS."
)

BASELINE_CODE = """def select_diagonal_newton_step(phase, scale, gradient, hessian, current_value, slope, trial_alpha, trial_value):
    if int(phase) == 0:
        q = np.zeros_like(gradient, dtype=np.float64)
        good = hessian > 0.0
        q[good] = -gradient[good] / hessian[good]
        return q
    c1 = 0.1
    for index in range(int(trial_alpha.shape[0])):
        alpha = float(trial_alpha[index])
        value = float(trial_value[index])
        if math.isfinite(value) and value <= float(current_value) + c1 * alpha * float(slope):
            return np.asarray(index, dtype=np.int64)
    return np.asarray(-1, dtype=np.int64)
"""

BASELINE_DESCRIPTION = (
    "relative central-difference diagonal Newton step; coordinates with "
    "curvature not greater than 0 take a zero step, then the first Armijo-feasible trial"
)


def suite_hash(problem: str, split: str, instances: list[Mapping[str, Any]]) -> str:
    payload = {"problem": problem, "split": split, "instances": instances}
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _frozen_instance() -> dict[str, Any]:
    constants = EVALUATOR_CONSTANTS
    return {
        "instance_id": "dev_train-0",
        "prescription_version": "v2",
        "backend": "numpy",
        "constraints": False,
        "initial_scale": float(constants["initial_scale"]),
        "field_indices": [32],
        "sample_d": 9,
        "max_iterations": int(constants["max_iterations"]),
        "eps": float(constants["eps"]),
        "initial_step": float(constants["initial_step"]),
        "armijo_c1": float(constants["armijo_c1"]),
        "backtrack_factor": float(constants["backtrack_factor"]),
        "max_backtracks": int(constants["max_backtracks"]),
        "gradient_tolerance": float(constants["gradient_tolerance"]),
        "zero_scale": float(constants["zero_scale"]),
        "physics_wheel_sha256": WHEEL_SHA256,
        "physics_tree_sha256": TREE_SHA256 if isinstance(TREE_SHA256, str) and TREE_SHA256 else "",
    }


def _same_value(have: Any, want: Any) -> bool:
    if isinstance(want, bool) or isinstance(have, bool):
        return type(have) is bool and type(want) is bool and have == want
    if isinstance(want, float):
        return type(have) is float and have == want
    if isinstance(want, int):
        return type(have) is int and have == want
    if isinstance(want, str):
        return type(have) is str and have == want
    if isinstance(want, list):
        if type(have) is not list or len(have) != len(want):
            return False
        return all(_same_value(item, ref) for item, ref in zip(have, want))
    return type(have) is type(want) and have == want


def _same_instance(got: Mapping[str, Any]) -> bool:
    expected = _frozen_instance()
    if set(got.keys()) != set(expected.keys()):
        return False
    return all(_same_value(got[key], expected[key]) for key in expected)


def build_suite(seed: int, split: str = "dev_train", count: int = 1, size: int = 62) -> dict[str, Any]:
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("invalid_seed")
    if split != "dev_train":
        raise ValueError("invalid_split")
    if isinstance(count, bool) or not isinstance(count, int) or count != 1:
        raise ValueError("invalid_count")
    if isinstance(size, bool) or not isinstance(size, int) or size != 62:
        raise ValueError("invalid_size")
    instances = [_frozen_instance()]
    return {
        "problem": PROBLEM_NAME,
        "split": split,
        "instances": instances,
        "content_hash": suite_hash(PROBLEM_NAME, split, instances),
    }


def validate_suite(suite: Mapping[str, Any]) -> tuple[list[Mapping[str, Any]], str]:
    if not isinstance(suite, Mapping):
        raise ValueError("invalid_suite")
    split = suite.get("split")
    instances = suite.get("instances")
    given_hash = suite.get("content_hash")
    if (
        suite.get("problem") != PROBLEM_NAME
        or split != "dev_train"
        or not isinstance(instances, list)
        or len(instances) != 1
        or not isinstance(given_hash, str)
        or not isinstance(instances[0], Mapping)
        or not _same_instance(instances[0])
    ):
        raise ValueError("invalid_suite")
    expected = suite_hash(PROBLEM_NAME, str(split), list(instances))
    if given_hash != expected:
        raise ValueError("suite_hash_mismatch")
    return list(instances), expected


def _mean_rms_rows(wavefront: Callable[[np.ndarray], np.ndarray], points: np.ndarray) -> np.ndarray:
    points = np.asarray(points, dtype=np.float64)
    if points.ndim != 2 or points.shape[1] != DIMENSION or points.shape[0] < 1:
        raise ValueError("invalid_instance")
    pieces: list[np.ndarray] = []
    batch = int(EVALUATOR_CONSTANTS["batch_size"])
    if batch < 1:
        raise ValueError("invalid_instance")
    for start in range(0, points.shape[0], batch):
        block = points[start:start + batch]
        values = np.asarray(wavefront(block), dtype=np.float64).reshape(-1)
        if values.shape != (block.shape[0],):
            raise ValueError("invalid_instance")
        pieces.append(values)
    return np.concatenate(pieces)


def _invoke(
    fn: Any,
    phase: int,
    scale: np.ndarray,
    gradient: np.ndarray,
    hessian: np.ndarray,
    current: float,
    slope: float,
    trial_alpha: np.ndarray,
    trial_value: np.ndarray,
) -> Any:
    scale_arg = np.array(scale, dtype=np.float64, copy=True)
    gradient_arg = np.array(gradient, dtype=np.float64, copy=True)
    hessian_arg = np.array(hessian, dtype=np.float64, copy=True)
    alpha_arg = np.array(trial_alpha, dtype=np.float64, copy=True)
    value_arg = np.array(trial_value, dtype=np.float64, copy=True)
    result = fn(
        phase,
        scale_arg,
        gradient_arg,
        hessian_arg,
        float(current),
        float(slope),
        alpha_arg,
        value_arg,
    )
    if (
        not np.array_equal(scale_arg, scale)
        or not np.array_equal(gradient_arg, gradient)
        or not np.array_equal(hessian_arg, hessian)
        or not np.array_equal(alpha_arg, trial_alpha)
        or not np.array_equal(value_arg, trial_value)
    ):
        raise ValueError("candidate_mutated_input")
    return result


def _classify_direction(value: Any) -> tuple[np.ndarray | None, str | None]:
    if (
        not isinstance(value, np.ndarray)
        or value.ndim != 1
        or value.shape != (DIMENSION,)
        or not np.issubdtype(value.dtype, np.floating)
    ):
        return None, "invalid_return"
    direction = np.array(value, dtype=np.float64, copy=True)
    if not np.all(np.isfinite(direction)):
        return None, "invalid_direction"
    return direction, None


def _trial_index(value: Any, trial_count: int) -> int | None:
    # Length-1 integer arrays are accepted. tsp_2opt's index check is not.
    if isinstance(value, (bool, np.bool_)):
        return None
    if isinstance(value, np.ndarray):
        if value.dtype.kind not in "iu":
            return None
        if value.ndim == 0 or value.shape == (1,):
            item = value.reshape(-1)[0]
        else:
            return None
        if isinstance(item, (bool, np.bool_)):
            return None
        integer = int(item)
    elif isinstance(value, np.integer):
        integer = int(value)
    elif isinstance(value, int):
        integer = value
    else:
        return None
    if integer == -1 or 0 <= integer < trial_count:
        return integer
    return None


def _metrics(
    initial: float,
    final: float,
    accepted_steps: int,
    accepted_alphas: list[float],
    step1_rms: float | None,
    status: str,
    iterations_executed: int,
    vectors: int,
) -> dict[str, Any]:
    frozen = _frozen_instance()
    # First accepted RMS sits between the other two. Later steps stay in final_rms_waves.
    step1 = {} if step1_rms is None else {"step1_rms_waves": step1_rms}
    return {
        "fitness_definition": "mean_rms_waves_on_frozen_suite",
        "prescription_version": frozen["prescription_version"],
        "field_indices": list(frozen["field_indices"]),
        "sample_d": frozen["sample_d"],
        "constraints_enabled": False,
        "penalty_merit": None,
        "initial_rms_waves": initial,
        **step1,
        "final_rms_waves": final,
        "accepted_steps": accepted_steps,
        "accepted_alphas": list(accepted_alphas),
        "solver_status": status,
        "iterations_executed": iterations_executed,
        "parameter_vectors_evaluated": vectors,
    }


def run_diagonal_newton(
    fn: Any,
    x0: np.ndarray,
    wavefront: Callable[[np.ndarray], np.ndarray],
) -> tuple[float, np.ndarray, dict[str, Any]]:
    """Run at most two diagonal-Newton iterations against an RMS oracle.

    ``wavefront(points)`` accepts shape ``(n, 62)`` and returns one finite-or-not
    mean RMS per row. The returned objective is the last accepted finite value.
    """
    constants = EVALUATOR_CONSTANTS
    eps = float(constants["eps"])
    zero_scale = float(constants["zero_scale"])
    c1 = float(constants["armijo_c1"])
    gradient_tolerance = float(constants["gradient_tolerance"])
    max_iterations = int(constants["max_iterations"])
    initial_step = float(constants["initial_step"])
    backtrack_factor = float(constants["backtrack_factor"])
    max_backtracks = int(constants["max_backtracks"])
    x = np.array(x0, dtype=np.float64, copy=True)
    if x.shape != (DIMENSION,) or not np.all(np.isfinite(x)):
        raise ValueError("invalid_instance")
    current = float(_mean_rms_rows(wavefront, x.reshape(1, -1))[0])
    vectors = 1
    if not math.isfinite(current):
        raise ValueError("nonfinite_objective")
    initial = current
    accepted_steps = 0
    accepted_alphas: list[float] = []
    step1_rms: float | None = None
    status = "max_iterations"
    iterations_executed = 0
    alphas = np.array(
        [initial_step * backtrack_factor ** exponent for exponent in range(max_backtracks + 1)],
        dtype=np.float64,
    )
    for _ in range(max_iterations):
        iterations_executed += 1
        # Exact zeros stay frozen when zero_scale is 0.
        scale = np.where(x != 0.0, x, zero_scale).astype(np.float64, copy=False)
        step = eps * scale
        plus = np.repeat(x.reshape(1, -1), DIMENSION, axis=0)
        minus = plus.copy()
        diagonal = np.arange(DIMENSION)
        plus[diagonal, diagonal] += step
        minus[diagonal, diagonal] -= step
        f_plus = _mean_rms_rows(wavefront, plus)
        f_minus = _mean_rms_rows(wavefront, minus)
        vectors += int(plus.shape[0] + minus.shape[0])
        gradient = (f_plus - f_minus) / (2.0 * eps)
        hessian = (f_plus + f_minus - 2.0 * current) / (eps ** 2)
        if not np.all(np.isfinite(gradient)) or not np.all(np.isfinite(hessian)):
            status = "invalid_finite_difference"
            break
        if float(np.max(np.abs(gradient))) <= gradient_tolerance:
            status = "gradient_tolerance"
            break
        result = _invoke(
            fn, 0, scale, gradient, hessian, current, 0.0, np.zeros(0, dtype=np.float64), np.zeros(0, dtype=np.float64)
        )
        direction, problem = _classify_direction(result)
        if problem == "invalid_return":
            raise ValueError("invalid_return")
        if problem == "invalid_direction" or direction is None:
            status = "invalid_direction"
            break
        step_p = scale * direction
        # Slope is g * q, not g * p. The genome does not return the physical step.
        slope = float(np.sum(gradient * direction))
        if not math.isfinite(slope) or slope >= 0.0:
            status = "no_descent_direction"
            break
        trials = x.reshape(1, -1) + alphas.reshape(-1, 1) * step_p.reshape(1, -1)
        finite_rows = np.isfinite(trials).all(axis=1)
        trial_values = np.full(alphas.shape[0], np.inf, dtype=np.float64)
        if np.any(finite_rows):
            evaluated = _mean_rms_rows(wavefront, trials[finite_rows])
            trial_values[finite_rows] = np.where(np.isfinite(evaluated), evaluated, np.inf)
            vectors += int(np.count_nonzero(finite_rows))
        choice = _invoke(fn, 1, scale, gradient, hessian, current, slope, alphas, trial_values)
        picked = _trial_index(choice, int(alphas.shape[0]))
        if picked is None:
            raise ValueError("invalid_return")
        if picked < 0:
            status = "line_search_failed"
            break
        alpha = float(alphas[picked])
        value = float(trial_values[picked])
        if not (math.isfinite(value) and value <= current + c1 * alpha * slope):
            status = "line_search_failed"
            break
        x = np.array(trials[picked], dtype=np.float64, copy=True)
        current = value
        accepted_steps += 1
        accepted_alphas.append(alpha)
        if step1_rms is None:
            step1_rms = value
    return current, x.copy(), _metrics(
        initial,
        current,
        accepted_steps,
        accepted_alphas,
        step1_rms,
        status,
        iterations_executed,
        vectors,
    )


def evaluate_instances(
    fn: Any,
    instances: list[Mapping[str, Any]],
    wavefront: Callable[[np.ndarray], np.ndarray] | None = None,
    x0: np.ndarray | None = None,
) -> tuple[list[float], dict[str, Any]]:
    if not isinstance(instances, list) or len(instances) != 1 or not isinstance(instances[0], Mapping):
        raise ValueError("invalid_instance")
    if (wavefront is None) != (x0 is None):
        raise ValueError("invalid_instance")
    if wavefront is None:
        instance = instances[0]
        pinned = PinnedNumpyWavefront(
            prescription_version=instance["prescription_version"],
            field_indices=list(instance["field_indices"]),
            sample_d=instance["sample_d"],
            constraints=instance["constraints"],
            initial_scale=instance["initial_scale"],
            wheel_sha256=instance["physics_wheel_sha256"],
            tree_sha256=instance["physics_tree_sha256"],
        )
        wavefront = pinned.mean_rms
        x0 = pinned.x0
    objective, _final_x, metrics = run_diagonal_newton(fn, x0, wavefront)
    return [objective], metrics
