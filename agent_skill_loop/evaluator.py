"""Process-isolated CVRP evaluator. Worker imports only this package."""

from __future__ import annotations

import ast
import builtins
import contextlib
import io
import json
import math
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Mapping

try:
    import numpy as np
except Exception:  # pragma: no cover
    np = None  # type: ignore[assignment]

from agent_skill_loop.contracts import EvaluationResult
from agent_skill_loop.problems.base import ProblemSpec, get_problem, register_problem
from agent_skill_loop.problems.cvrp import (
    BASELINE_CODE,
    BASELINE_DESCRIPTION,
    ENTRYPOINT,
    PROBLEM_NAME,
    SPLIT_OFFSETS,
    TASK_DESCRIPTION,
    TEMPLATE_PROGRAM,
    build_suite,
    finite_float,
    suite_hash,
)
from agent_skill_loop.problems.tsp import (
    BASELINE_CODE as TSP_BASELINE_CODE,
    BASELINE_DESCRIPTION as TSP_BASELINE_DESCRIPTION,
    ENTRYPOINT as TSP_ENTRYPOINT,
    PROBLEM_NAME as TSP_PROBLEM_NAME,
    SPLIT_OFFSETS as TSP_SPLIT_OFFSETS,
    TASK_DESCRIPTION as TSP_TASK_DESCRIPTION,
    TEMPLATE_PROGRAM as TSP_TEMPLATE_PROGRAM,
    build_suite as tsp_build_suite,
    suite_hash as tsp_suite_hash,
)
from agent_skill_loop.problems.tsp_2opt import (
    BASELINE_CODE as TSP2_BASELINE_CODE,
    BASELINE_DESCRIPTION as TSP2_BASELINE_DESCRIPTION,
    ENTRYPOINT as TSP2_ENTRYPOINT,
    PROBLEM_NAME as TSP2_PROBLEM_NAME,
    SPLIT_OFFSETS as TSP2_SPLIT_OFFSETS,
    TASK_DESCRIPTION as TSP2_TASK_DESCRIPTION,
    TEMPLATE_PROGRAM as TSP2_TEMPLATE_PROGRAM,
    build_suite as tsp2_build_suite,
    suite_hash as tsp2_suite_hash,
)

_SAFE_BUILTINS = {
    "abs": abs, "all": all, "any": any, "bool": bool, "dict": dict,
    "enumerate": enumerate, "filter": filter, "float": float, "int": int,
    "len": len, "list": list, "map": map, "max": max, "min": min,
    "range": range, "reversed": reversed, "round": round, "set": set,
    "sorted": sorted, "sum": sum, "tuple": tuple, "zip": zip,
}
_FORBIDDEN_NAMES = {
    "__import__", "open", "input", "exec", "eval", "compile", "globals", "locals",
    "vars", "dir", "getattr", "setattr", "delattr", "breakpoint", "help", "quit",
    "exit", "os", "sys", "subprocess", "socket", "pathlib", "shutil", "requests",
}
_NUMPY_ATTRIBUTES = {
    "abs", "add", "all", "allclose", "any", "argmax", "argmin", "argsort", "arange", "array",
    "array_equal", "asarray", "astype", "clip", "column_stack", "concatenate", "copy", "cos",
    "cumsum", "delete", "diag", "diff", "divide", "dot", "dtype", "e", "exp", "float32",
    "float64", "full", "hstack", "inf", "isfinite", "linalg", "max", "mean", "median", "min",
    "minimum", "nan", "ndarray", "ndim", "norm", "nonzero", "ones", "pi", "power", "ravel",
    "reshape", "round", "shape", "sin", "size", "sort", "sqrt", "square", "std", "sum", "tile",
    "tolist", "trunc", "unique", "where", "zeros", "zip", "repeat", "floor", "ceil", "int32",
    "int64", "uint32", "uint64", "bool_", "newaxis", "T", "flatten", "item",
    "isinf", "isnan", "arctan2", "arccos", "arcsin", "arctan", "acos", "asin", "atan", "tan",
    "log", "log1p", "log2", "log10", "expm1", "hypot", "isclose", "fabs",
    "zeros_like", "ones_like", "full_like", "eye", "maximum",
}
_NP_MATH_ROOTS = {"np", "numpy", "math"}
_ALLOWED_IMPORT_ROOTS = {"numpy", "math"}
_REAL_IMPORT = builtins.__import__
_MATH_ATTRIBUTES = {
    "acos", "asin", "atan", "atan2", "ceil", "cos", "e", "exp", "fabs", "floor", "fmod",
    "hypot", "inf", "isfinite", "isclose", "log", "log10", "pi", "sin", "sqrt", "tan", "trunc",
}
# Default-deny for attributes on receivers that are not a restricted module
# (np/numpy/math) or a tracked alias of one. Such attributes are allowed only
# when they appear in the spec's numpy/math whitelist or are one of the small
# set of ordinary container methods below. Everything else (``arr.tofile``,
# ``arr.save``, ``obj.foo``) is rejected.
_CONTAINER_METHODS = {
    "append", "extend", "insert", "pop", "remove", "sort", "reverse",
    "count", "index", "clear",
}
_KNOWN_ERRORS = {
    "unsupported_problem", "invalid_suite", "suite_hash_mismatch", "invalid_code",
    "missing_entrypoint", "forbidden_import", "forbidden_name", "forbidden_attribute",
    "forbidden_syntax", "forbidden_constant", "invalid_instance", "infeasible_instance",
    "candidate_mutated_input", "invalid_return", "capacity_violation", "nonfinite_objective",
    "invalid_route",
    "forbidden_rebinding",
}


class EvalError(ValueError):
    def __init__(self, code: str, detail: str | None = None) -> None:
        super().__init__(code)
        self.error_code = code
        self.detail = sanitize_error_detail(detail)


def sanitize_error_detail(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = "".join(ch if ch.isalnum() or ch in "._:-" else "_" for ch in str(value).strip())[:80]
    cleaned = cleaned.strip(".:-")
    return cleaned or None


def evaluator_source_hash() -> str:
    """Hash of the evaluator and suite-generator sources.

    Identity covers worker semantics (validation + suite generation), not just
    this file: the worker imports evaluator.py, and problems/cvrp.py defines
    TASK_DESCRIPTION / TEMPLATE_PROGRAM / BASELINE_CODE plus the suite
    instances the worker validates against.
    """
    import hashlib
    parts = [Path(__file__).read_bytes()]
    parent = Path(__file__).resolve().parent
    parts.append(parent.joinpath("problems", "cvrp.py").read_bytes())
    parts.append(parent.joinpath("problems", "tsp.py").read_bytes())
    parts.append(parent.joinpath("problems", "tsp_2opt.py").read_bytes())
    parts.append(parent.joinpath("problems", "base.py").read_bytes())
    return hashlib.sha256(b"|".join(parts)).hexdigest()


def kill_process_tree(proc: subprocess.Popen) -> None:
    """Best-effort kill of *proc* and its entire descendant tree.

    On Windows the official EoH outer process cannot reach our grandchild
    (os.setsid/killpg is POSIX-only), so the tree must be torn down here.
    """
    if proc is None:
        return
    pid = proc.pid
    if pid is None or pid <= 0:
        return
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except (OSError, subprocess.SubprocessError):
            pass
        if proc.poll() is None:
            try:
                proc.kill()
            except OSError:
                pass
    else:
        try:
            pgid = os.getpgid(pid)
            own_pgid = os.getpgid(0)
        except OSError:
            pgid = None
            own_pgid = None
        # Only signal a group we own: the child is started in its own session
        # (start_new_session=True), so a shared pgid means we must not killpg.
        if pgid and own_pgid is not None and pgid != own_pgid:
            try:
                os.killpg(pgid, signal.SIGKILL)
            except OSError:
                pass
        else:
            try:
                proc.kill()
            except OSError:
                pass
    try:
        proc.wait(timeout=2.0)
    except (OSError, subprocess.TimeoutExpired):
        pass


def _attribute_root_id(node: ast.Attribute) -> str | None:
    current: ast.AST = node.value
    while isinstance(current, ast.Attribute):
        current = current.value
    if isinstance(current, ast.Name):
        return current.id
    return None


def _make_restricted_import(allowed_roots: set[str]) -> Any:
    """Return a __import__ wrapper that only allows the spec's import roots.

    Candidate AST cannot emit ImportFrom/relative import. Numpy ndarray methods
    still call __import__ from the candidate frame for numpy.* submodules.
    """

    def restricted_import(name: str, globals: Any = None, locals: Any = None, fromlist: tuple[str, ...] = (), level: int = 0) -> Any:
        if level:
            module_name = str(globals.get("__name__") or "") if isinstance(globals, dict) else ""
            if not (module_name == "numpy" or module_name.startswith("numpy.") or module_name == "math" or module_name.startswith("math.")):
                raise ImportError("restricted_import")
            return _REAL_IMPORT(name, globals, locals, fromlist, level)
        root = (name or "").split(".", 1)[0]
        if root not in allowed_roots:
            raise ImportError("restricted_import")
        return _REAL_IMPORT(name, globals, locals, fromlist, level)

    return restricted_import


def _collect_np_math_aliases(tree: ast.Module, roots: set[str] | frozenset[str]) -> set[str]:
    """Resolve simple ``alias = np`` / ``alias = math`` assignments, chains included."""
    assignments: list[tuple[str, ast.expr]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            assignments.append((node.targets[0].id, node.value))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
            assignments.append((node.target.id, node.value))
    aliases: set[str] = set()
    changed = True
    while changed:
        changed = False
        for name, value in assignments:
            if name in aliases:
                continue
            if _expr_is_np_math_alias(value, roots, aliases):
                aliases.add(name)
                changed = True
    return aliases


def _expr_is_np_math_alias(value: ast.expr, roots: set[str] | frozenset[str], aliases: set[str]) -> bool:
    """Recognise only transparent alias expressions for restricted modules.

    The previous checker handled ``lib = np`` but missed aliases hidden in a
    literal/container (``lib = [np][0]``).  Such expressions are still fully
    static and must retain the source module's attribute whitelist.
    """
    if isinstance(value, ast.Name):
        return value.id in roots or value.id in aliases
    if isinstance(value, ast.Subscript):
        return _expr_is_np_math_alias(value.value, roots, aliases)
    if isinstance(value, (ast.Tuple, ast.List)) and len(value.elts) == 1:
        return _expr_is_np_math_alias(value.elts[0], roots, aliases)
    # Be conservative for computed expressions: if a restricted module name is
    # present anywhere in the value, the assigned name may carry that module or
    # one of its objects. Treating it as restricted can reject a harmless
    # numeric expression, but never permits a capability escape.
    return any(
        isinstance(node, ast.Name) and (node.id in roots or node.id in aliases)
        for node in ast.walk(value)
    )


def _check_rebinding_target(target: ast.expr, roots: set[str] | frozenset[str]) -> None:
    """Reject assignment/loop targets that rebind a restricted module root.

    Handles plain names as well as tuple/list unpacking and starred targets so
    ``a, b = np, math`` and ``for np in ...`` cannot smuggle a restricted module
    into a locally named receiver.
    """
    if isinstance(target, ast.Name):
        if target.id in roots:
            raise EvalError("forbidden_rebinding", target.id)
    elif isinstance(target, (ast.Tuple, ast.List)):
        for element in target.elts:
            _check_rebinding_target(element, roots)
    elif isinstance(target, ast.Starred):
        _check_rebinding_target(target.value, roots)


def _check_rebinding_args(args: ast.arguments, roots: set[str] | frozenset[str]) -> None:
    """Reject function/lambda parameters that shadow a restricted module root."""
    parameters = [*args.posonlyargs, *args.args, *args.kwonlyargs]
    if args.vararg is not None:
        parameters.append(args.vararg)
    if args.kwarg is not None:
        parameters.append(args.kwarg)
    for parameter in parameters:
        if parameter.arg in roots:
            raise EvalError("forbidden_rebinding", parameter.arg)


def _validate_candidate_ast(code: str, spec: ProblemSpec) -> ast.Module:
    if not isinstance(code, str) or not code.strip() or len(code.encode("utf-8")) > 100_000:
        raise ValueError("invalid_code")
    try:
        tree = ast.parse(code, mode="exec")
        compile(tree, "<candidate>", "exec")
    except EvalError:
        raise
    except SyntaxError as exc:
        location = f"line_{exc.lineno}" if exc.lineno is not None else None
        if exc.offset is not None:
            location = f"{location}_column_{exc.offset}" if location else f"column_{exc.offset}"
        raise EvalError("invalid_code", location) from None
    except (ValueError, TypeError, UnicodeError):
        raise ValueError("invalid_code") from None
    function_names = {node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    if spec.entrypoint not in function_names:
        raise EvalError("missing_entrypoint", spec.entrypoint)
    allowed_aliases = {root: (None, "np" if root == "numpy" else root) for root in spec.allowed_import_roots}
    np_math_aliases = _collect_np_math_aliases(tree, spec.np_math_roots)
    for node in ast.walk(tree):
        # Rebinding a restricted module root is always forbidden: assignment,
        # annotated/augmented assignment, loop and comprehension targets, walrus
        # targets, and function/lambda parameters (nested defs included by walk).
        if isinstance(node, ast.Assign):
            for target in node.targets:
                _check_rebinding_target(target, spec.np_math_roots)
        elif isinstance(node, ast.AnnAssign):
            _check_rebinding_target(node.target, spec.np_math_roots)
        elif isinstance(node, ast.AugAssign):
            _check_rebinding_target(node.target, spec.np_math_roots)
        elif isinstance(node, (ast.For, ast.comprehension)):
            _check_rebinding_target(node.target, spec.np_math_roots)
        elif isinstance(node, ast.NamedExpr):
            _check_rebinding_target(node.target, spec.np_math_roots)
        elif isinstance(node, (ast.FunctionDef, ast.Lambda)):
            _check_rebinding_args(node.args, spec.np_math_roots)

        if isinstance(node, ast.AsyncFunctionDef):
            raise ValueError("forbidden_syntax")
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name not in allowed_aliases or alias.asname not in allowed_aliases[alias.name]:
                    raise EvalError("forbidden_import", alias.name)
        elif isinstance(node, ast.ImportFrom):
            raise EvalError("forbidden_import", node.module or "from_import")
        elif isinstance(node, ast.Name):
            if node.id in spec.forbidden_names or node.id.startswith("__"):
                raise EvalError("forbidden_name", node.id)
        elif isinstance(node, ast.Attribute):
            if isinstance(node.ctx, ast.Store):
                raise EvalError("forbidden_rebinding", node.attr)
            if node.attr.startswith("_"):
                raise EvalError("forbidden_attribute", node.attr)
            root = _attribute_root_id(node)
            if root in spec.np_math_roots or root in np_math_aliases:
                if node.attr not in spec.allowed_attributes:
                    raise EvalError("forbidden_attribute", node.attr)
            elif node.attr not in spec.allowed_attributes and node.attr not in _CONTAINER_METHODS:
                raise EvalError("forbidden_attribute", node.attr)
        elif isinstance(node, (ast.ClassDef, ast.Lambda, ast.With, ast.AsyncWith, ast.Try, ast.Raise, ast.Delete, ast.Global, ast.Nonlocal)):
            raise ValueError("forbidden_syntax")
        elif isinstance(node, ast.Constant) and isinstance(node.value, (bytes, bytearray)):
            raise ValueError("forbidden_constant")
    return tree


class _QuietSink(io.TextIOBase):
    def write(self, text: str) -> int:
        return len(text)

    def flush(self) -> None:
        return None


def _as_index(value: Any, allowed: set[int]) -> int | None:
    if isinstance(value, (bool, np.bool_ if np is not None else bool)):
        return None
    if np is not None and isinstance(value, np.ndarray) and value.ndim != 0:
        return None
    try:
        numeric = float(value)
        integer = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(numeric) or numeric != integer or integer not in allowed:
        return None
    return integer


def _validate_cvrp_suite(suite: Mapping[str, Any]) -> tuple[list[Mapping[str, Any]], str]:
    split = suite.get("split") if isinstance(suite, Mapping) else None
    if not isinstance(suite, Mapping) or suite.get("problem") != PROBLEM_NAME or not isinstance(split, str) or split not in SPLIT_OFFSETS:
        raise ValueError("invalid_suite")
    instances = suite.get("instances")
    given_hash = suite.get("content_hash")
    if not isinstance(instances, list) or not instances or not isinstance(given_hash, str):
        raise ValueError("invalid_suite")
    expected = suite_hash(PROBLEM_NAME, split, instances)
    if given_hash != expected:
        raise ValueError("suite_hash_mismatch")
    return instances, expected


def _validate_tsp_suite(suite: Mapping[str, Any]) -> tuple[list[Mapping[str, Any]], str]:
    split = suite.get("split") if isinstance(suite, Mapping) else None
    if not isinstance(suite, Mapping) or suite.get("problem") != TSP_PROBLEM_NAME or not isinstance(split, str) or split not in TSP_SPLIT_OFFSETS:
        raise ValueError("invalid_suite")
    instances = suite.get("instances")
    given_hash = suite.get("content_hash")
    if not isinstance(instances, list) or not instances or not isinstance(given_hash, str):
        raise ValueError("invalid_suite")
    expected = tsp_suite_hash(TSP_PROBLEM_NAME, split, instances)
    if given_hash != expected:
        raise ValueError("suite_hash_mismatch")
    return instances, expected


def _validate_tsp2_suite(suite: Mapping[str, Any]) -> tuple[list[Mapping[str, Any]], str]:
    split = suite.get("split") if isinstance(suite, Mapping) else None
    if not isinstance(suite, Mapping) or suite.get("problem") != TSP2_PROBLEM_NAME or not isinstance(split, str) or split not in TSP2_SPLIT_OFFSETS:
        raise ValueError("invalid_suite")
    instances = suite.get("instances")
    given_hash = suite.get("content_hash")
    if not isinstance(instances, list) or not instances or not isinstance(given_hash, str):
        raise ValueError("invalid_suite")
    expected = tsp2_suite_hash(TSP2_PROBLEM_NAME, split, instances)
    if given_hash != expected:
        raise ValueError("suite_hash_mismatch")
    return instances, expected


def _validate_suite(spec: ProblemSpec, suite: Mapping[str, Any]) -> tuple[list[Mapping[str, Any]], str]:
    """Validate a suite against a resolved problem spec (problem-driven)."""
    return spec.validate_suite(suite)


def _distance_matrix(points: list[list[float]]):
    coords = np.asarray(points, dtype=float)
    if coords.ndim != 2 or coords.shape[1] != 2 or not np.all(np.isfinite(coords)):
        raise ValueError("invalid_instance")
    delta = coords[:, None, :] - coords[None, :, :]
    return np.sqrt(np.sum(delta * delta, axis=2))


def _evaluate_cvrp_instances(fn: Any, instances: list[Mapping[str, Any]]) -> tuple[list[float], None]:
    objectives = []
    for instance in instances:
        depot, customers, demands, capacity = (instance.get(key) for key in ("depot", "customer_coordinates", "demands", "capacity"))
        if not isinstance(depot, list) or not isinstance(customers, list) or not isinstance(demands, list) or len(customers) != len(demands) or not customers or not isinstance(capacity, (int, float)) or not finite_float(capacity) or capacity <= 0:
            raise ValueError("invalid_instance")
        points = [depot] + customers
        matrix = _distance_matrix(points)
        demand_array = np.asarray([0] + demands, dtype=float)
        if np.any(~np.isfinite(demand_array)) or np.any(demand_array < 0) or np.any(demand_array > float(capacity)):
            raise ValueError("invalid_instance")
        unvisited = set(range(1, len(points)))
        route = [0]
        current = 0
        remaining = float(capacity)
        steps = 0
        while unvisited:
            steps += 1
            if steps > len(points) * len(points):
                raise ValueError("invalid_route")
            feasible = sorted(node for node in unvisited if demand_array[node] <= remaining + 1e-12)
            if not feasible:
                route.append(0)
                current, remaining = 0, float(capacity)
                continue
            feasible_array = np.asarray(feasible, dtype=int)
            candidate_nodes, candidate_demands, candidate_matrix = feasible_array.copy(), demand_array.copy(), matrix.copy()
            result = fn(current, 0, candidate_nodes, remaining, candidate_demands, candidate_matrix)
            if not np.array_equal(candidate_nodes, feasible_array) or not np.array_equal(candidate_demands, demand_array) or not np.array_equal(candidate_matrix, matrix):
                raise ValueError("candidate_mutated_input")
            nxt = _as_index(result, set(feasible) | {0})
            if nxt is None:
                raise ValueError("invalid_return")
            if nxt == 0:
                route.append(0)
                current, remaining = 0, float(capacity)
                continue
            route.append(nxt)
            unvisited.remove(nxt)
            remaining -= float(demand_array[nxt])
            current = nxt
        if route[-1] != 0:
            route.append(0)
        if set(route) - set(range(len(points))) or set(range(1, len(points))) - set(route) or any(route.count(node) != 1 for node in range(1, len(points))):
            raise ValueError("invalid_route")
        cost = float(sum(matrix[a, b] for a, b in zip(route, route[1:])))
        if not math.isfinite(cost):
            raise ValueError("nonfinite_objective")
        objectives.append(cost)
    return objectives, None


def _evaluate_tsp_instances(fn: Any, instances: list[Mapping[str, Any]]) -> tuple[list[float], None]:
    """Closed-tour TSP construction. No capacity; every city visited once."""
    objectives = []
    for instance in instances:
        coordinates = instance.get("coordinates")
        if not isinstance(coordinates, list) or len(coordinates) < 2:
            raise ValueError("invalid_instance")
        points = coordinates
        matrix = _distance_matrix(points)
        node_count = len(points)
        unvisited = set(range(1, node_count))
        tour = [0]
        current = 0
        steps = 0
        while unvisited:
            steps += 1
            if steps > node_count * node_count:
                raise ValueError("invalid_route")
            candidate_nodes = np.asarray(sorted(unvisited), dtype=int)
            candidate_matrix = matrix.copy()
            result = fn(current, 0, candidate_nodes, candidate_matrix)
            if not np.array_equal(candidate_nodes, np.asarray(sorted(unvisited), dtype=int)) or not np.array_equal(candidate_matrix, matrix):
                raise ValueError("candidate_mutated_input")
            nxt = _as_index(result, set(unvisited))
            if nxt is None:
                raise ValueError("invalid_return")
            tour.append(nxt)
            unvisited.remove(nxt)
            current = nxt
        tour.append(0)
        cost = float(sum(matrix[a, b] for a, b in zip(tour, tour[1:])))
        if not math.isfinite(cost):
            raise ValueError("nonfinite_objective")
        objectives.append(cost)
    return objectives, None


def _nearest_neighbour_tour(matrix: Any, node_count: int) -> list[int]:
    unvisited = set(range(1, node_count))
    tour = [0]
    current = 0
    while unvisited:
        nxt = min(unvisited, key=lambda node: (float(matrix[current][node]), node))
        tour.append(nxt)
        unvisited.remove(nxt)
        current = nxt
    return tour


def _tsp2_candidates(tour: list[int], matrix: Any) -> tuple[list[int], list[int], list[float], int]:
    """All strictly improving 2-opt moves for a closed tour, in stable order.

    Also returns the number of candidate pairs scanned (enumeration workload).
    """
    node_count = len(tour)
    starts: list[int] = []
    ends: list[int] = []
    deltas: list[float] = []
    pairs_scanned = 0
    for i in range(1, node_count - 1):
        for j in range(i + 1, node_count):
            if i == 1 and j == node_count - 1:
                continue  # reversing the whole tour is a no-op for a closed tour
            pairs_scanned += 1
            prev, first = tour[i - 1], tour[i]
            last, nxt = tour[j], tour[(j + 1) % node_count]
            delta = float(
                matrix[prev][last] + matrix[first][nxt] - matrix[prev][first] - matrix[last][nxt]
            )
            if delta < -1e-12:
                starts.append(i)
                ends.append(j)
                deltas.append(delta)
    return starts, ends, deltas, pairs_scanned


def _evaluate_tsp2_instances(fn: Any, instances: list[Mapping[str, Any]]) -> tuple[list[float], dict[str, Any]]:
    """Bounded 2-opt refinement of a fixed nearest-neighbour tour.

    The evaluator owns the initial tour, the improving-move enumeration, the
    move application, and the objective. The evolved entrypoint only selects
    which candidate move to apply, at most one operation per step and at most
    ``n`` operations per instance (n = city count). The per-instance operation
    budget, moves applied, and enumeration workload are returned as metrics so
    they can be recorded next to the wall-clock time.
    """
    objectives = []
    budget_per_instance: list[int] = []
    moves_applied: list[int] = []
    improving_offered: list[int] = []
    pairs_scanned: list[int] = []
    for instance in instances:
        coordinates = instance.get("coordinates")
        if not isinstance(coordinates, list) or len(coordinates) < 3:
            raise ValueError("invalid_instance")
        matrix = _distance_matrix(coordinates)
        node_count = len(coordinates)
        tour = _nearest_neighbour_tour(matrix, node_count)
        budget = node_count
        moves = 0
        offered = 0
        scanned = 0
        for step in range(budget):
            starts, ends, deltas, pairs = _tsp2_candidates(tour, matrix)
            scanned += pairs
            offered += len(starts)
            if not starts:
                break
            move_start = np.asarray(starts, dtype=int)
            move_end = np.asarray(ends, dtype=int)
            move_delta = np.asarray(deltas, dtype=float)
            tour_array = np.asarray(tour, dtype=int)
            tour_arg, matrix_arg = tour_array.copy(), matrix.copy()
            start_arg, end_arg, delta_arg = move_start.copy(), move_end.copy(), move_delta.copy()
            result = fn(tour_arg, matrix_arg, start_arg, end_arg, delta_arg, budget - step)
            if (
                not np.array_equal(tour_arg, tour_array)
                or not np.array_equal(matrix_arg, matrix)
                or not np.array_equal(start_arg, move_start)
                or not np.array_equal(end_arg, move_end)
                or not np.array_equal(delta_arg, move_delta)
            ):
                raise ValueError("candidate_mutated_input")
            pick = _as_index(result, set(range(len(starts))))
            if pick is None:
                raise ValueError("invalid_return")
            i, j = starts[pick], ends[pick]
            tour[i:j + 1] = reversed(tour[i:j + 1])
            moves += 1
        cost = float(sum(matrix[a, b] for a, b in zip(tour, tour[1:] + tour[:1])))
        if not math.isfinite(cost):
            raise ValueError("nonfinite_objective")
        objectives.append(cost)
        budget_per_instance.append(budget)
        moves_applied.append(moves)
        improving_offered.append(offered)
        pairs_scanned.append(scanned)
    metrics = {
        "operation_budget_per_instance": budget_per_instance,
        "moves_applied": moves_applied,
        "improving_candidates_offered": improving_offered,
        "pairs_scanned": pairs_scanned,
        "total_moves_applied": sum(moves_applied),
        "total_pairs_scanned": sum(pairs_scanned),
    }
    return objectives, metrics


def _evaluate_problem(spec: ProblemSpec, fn: Any, instances: list[Mapping[str, Any]]) -> tuple[list[float], dict[str, Any] | None]:
    """Per-instance objective evaluation dispatched by problem spec."""
    return spec.evaluate_instances(fn, instances)


def evaluate_candidate_request(request: Mapping[str, Any]) -> dict[str, Any]:
    started = time.monotonic()
    problem = request.get("problem")
    suite = request.get("suite")
    code = request.get("code")
    suite_hash_value: str | None = None
    try:
        spec = get_problem(problem)
        instances, expected = _validate_suite(spec, suite)
        suite_hash_value = expected
        tree = _validate_candidate_ast(code, spec)

        builtins_dict = dict(spec.safe_builtins)
        builtins_dict["__import__"] = _make_restricted_import(spec.allowed_import_roots)
        globals_dict = {"__builtins__": builtins_dict, "np": np, "numpy": np, "math": math}
        with contextlib.redirect_stdout(_QuietSink()), contextlib.redirect_stderr(_QuietSink()):
            exec(compile(tree, "<candidate>", "exec"), globals_dict, globals_dict)
        fn = globals_dict.get(spec.entrypoint)
        if not callable(fn):
            raise ValueError("missing_entrypoint")
        with contextlib.redirect_stdout(_QuietSink()), contextlib.redirect_stderr(_QuietSink()):
            per_instance, metrics = _evaluate_problem(spec, fn, instances)
        objective = float(sum(per_instance) / len(per_instance))
        if not math.isfinite(objective) or any(not math.isfinite(float(x)) for x in per_instance):
            raise ValueError("nonfinite_objective")
        return {
            "valid": True,
            "objective": objective,
            "instance_objectives": per_instance,
            "suite_hash": expected,
            "error_code": None,
            "error_detail": None,
            "elapsed_seconds": time.monotonic() - started,
            "metrics": metrics,
        }
    except EvalError as exc:
        return {
            "valid": False,
            "objective": None,
            "instance_objectives": [],
            "suite_hash": suite_hash_value,
            "error_code": exc.error_code,
            "error_detail": exc.detail,
            "elapsed_seconds": time.monotonic() - started,
        }
    except ValueError as exc:
        error_code = str(exc) if str(exc) in _KNOWN_ERRORS else "candidate_error"
        return {
            "valid": False,
            "objective": None,
            "instance_objectives": [],
            "suite_hash": suite_hash_value,
            "error_code": error_code,
            "error_detail": None,
            "elapsed_seconds": time.monotonic() - started,
        }
    except Exception as exc:
        lineno = None
        frame = exc.__traceback__
        while frame is not None:
            if frame.tb_frame.f_code.co_filename == "<candidate>":
                lineno = frame.tb_lineno
                break
            frame = frame.tb_next
        detail = type(exc).__name__ + (f":line_{lineno}" if lineno else "")
        return {
            "valid": False,
            "objective": None,
            "instance_objectives": [],
            "suite_hash": suite_hash_value,
            "error_code": "candidate_exception",
            "error_detail": sanitize_error_detail(detail),
            "elapsed_seconds": time.monotonic() - started,
        }


def _result_from_dict(payload: Mapping[str, Any]) -> EvaluationResult:
    values = payload.get("instance_objectives") or []
    metrics = payload.get("metrics")
    return EvaluationResult(
        valid=bool(payload.get("valid")),
        objective=payload.get("objective"),
        instance_objectives=tuple(float(x) for x in values) if payload.get("valid") else (),
        suite_hash=payload.get("suite_hash"),
        error_code=payload.get("error_code"),
        elapsed_seconds=float(payload.get("elapsed_seconds") or 0.0),
        error_detail=payload.get("error_detail"),
        metrics=metrics if isinstance(metrics, dict) else None,
    )


class SubprocessEvaluator:
    def __init__(self, timeout: float = 20.0):
        if not finite_float(timeout) or float(timeout) <= 0:
            raise ValueError("invalid_timeout")
        self.timeout = float(timeout)

    def evaluate(self, code: str, suite: Mapping[str, Any]) -> EvaluationResult:
        started = time.monotonic()
        try:
            problem_id = suite.get("problem") if isinstance(suite, Mapping) else None
            spec = get_problem(problem_id)
            instances, expected_hash = _validate_suite(spec, suite)
            if not isinstance(code, str):
                raise ValueError("invalid_code")
        except (ValueError, TypeError) as exc:
            error = str(exc) if str(exc) in {"unsupported_problem", "invalid_suite", "suite_hash_mismatch", "invalid_code"} else "invalid_request"
            return EvaluationResult(False, None, (), None, error, time.monotonic() - started)
        request = {"problem": spec.problem_id, "code": code, "suite": dict(suite), "parent_pid": os.getpid()}
        package_root = Path(__file__).resolve().parents[1]
        safe_env = {key: os.environ[key] for key in ("PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "LANG", "LC_ALL") if key in os.environ}
        safe_env["PYTHONPATH"] = str(package_root)
        proc: subprocess.Popen[bytes] | None = None
        stdout = b""
        try:
            with tempfile.TemporaryDirectory(prefix="skill-loop-") as temp_cwd:
                try:
                    popen_kwargs: dict[str, Any] = {}
                    if os.name != "nt":
                        # Own process group so a timeout killpg never touches the caller.
                        popen_kwargs["start_new_session"] = True
                    proc = subprocess.Popen(
                        [sys.executable, "-m", "agent_skill_loop.eval_worker"],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL,
                        cwd=temp_cwd,
                        env=safe_env,
                        **popen_kwargs,
                    )
                    payload = json.dumps(request, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                    stdout, _ = proc.communicate(payload, timeout=self.timeout)
                except subprocess.TimeoutExpired:
                    if proc is not None:
                        kill_process_tree(proc)
                        try:
                            proc.communicate(timeout=1.0)
                        except subprocess.TimeoutExpired:
                            try:
                                proc.wait(timeout=1.0)
                            except (OSError, subprocess.TimeoutExpired):
                                pass
                    return EvaluationResult(False, None, (), expected_hash, "timeout", time.monotonic() - started)
        except subprocess.TimeoutExpired:
            if proc is not None:
                kill_process_tree(proc)
            return EvaluationResult(False, None, (), expected_hash, "timeout", time.monotonic() - started)
        except (OSError, TypeError, ValueError):
            return EvaluationResult(False, None, (), expected_hash, "worker_error", time.monotonic() - started)
        try:
            result = json.loads(stdout.decode("utf-8"))
            if not isinstance(result, dict) or set(("valid", "objective", "instance_objectives", "suite_hash", "error_code", "elapsed_seconds")) - set(result):
                raise ValueError
            if not isinstance(result.get("valid"), bool):
                raise ValueError
            if "metrics" in result and result["metrics"] is not None and not isinstance(result["metrics"], dict):
                raise ValueError
            if result["valid"]:
                values = result.get("instance_objectives")
                objective = result.get("objective")
                if result.get("suite_hash") != expected_hash or not isinstance(values, list) or len(values) != len(instances):
                    raise ValueError
                if isinstance(objective, bool) or not finite_float(objective) or any(isinstance(x, bool) or not finite_float(x) for x in values):
                    raise ValueError
                expected_objective = float(sum(float(x) for x in values) / len(values))
                if float(objective) != expected_objective:
                    raise ValueError
            elif result.get("suite_hash") not in (expected_hash, None):
                raise ValueError
            result["elapsed_seconds"] = time.monotonic() - started
            return _result_from_dict(result)
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
            return EvaluationResult(False, None, (), expected_hash, "worker_protocol", time.monotonic() - started)


# --- problem spec registration ---------------------------------------------
# The CVRP spec encapsulates exactly the pre-refactor literals (identity,
# entrypoint, prompt strings, suite builder/hash/validation, objective math,
# and the execution capability whitelist). Registering here makes the evaluator
# problem-driven while keeping every observable behavior identical.
CVRP_SPEC = ProblemSpec(
    problem_id=PROBLEM_NAME,
    entrypoint=ENTRYPOINT,
    interface_version="v1",
    task_description=TASK_DESCRIPTION,
    template_program=TEMPLATE_PROGRAM,
    baseline_code=BASELINE_CODE,
    objective_direction="minimize",
    split_offsets=SPLIT_OFFSETS,
    build_suite=build_suite,
    suite_hash=suite_hash,
    validate_suite=_validate_cvrp_suite,
    evaluate_instances=_evaluate_cvrp_instances,
    safe_builtins=_SAFE_BUILTINS,
    forbidden_names=frozenset(_FORBIDDEN_NAMES),
    numpy_attributes=frozenset(_NUMPY_ATTRIBUTES),
    math_attributes=frozenset(_MATH_ATTRIBUTES),
    np_math_roots=frozenset(_NP_MATH_ROOTS),
    allowed_import_roots=frozenset(_ALLOWED_IMPORT_ROOTS),
    baseline_description=BASELINE_DESCRIPTION,
)

register_problem(CVRP_SPEC)


# --- TSP spec registration ---------------------------------------------------
# Second problem on the same loop: closed-tour construction, no capacity, its
# own split offsets and suite hash. Shares the execution whitelist.
TSP_SPEC = ProblemSpec(
    problem_id=TSP_PROBLEM_NAME,
    entrypoint=TSP_ENTRYPOINT,
    interface_version="v1",
    task_description=TSP_TASK_DESCRIPTION,
    template_program=TSP_TEMPLATE_PROGRAM,
    baseline_code=TSP_BASELINE_CODE,
    objective_direction="minimize",
    split_offsets=TSP_SPLIT_OFFSETS,
    build_suite=tsp_build_suite,
    suite_hash=tsp_suite_hash,
    validate_suite=_validate_tsp_suite,
    evaluate_instances=_evaluate_tsp_instances,
    safe_builtins=_SAFE_BUILTINS,
    forbidden_names=frozenset(_FORBIDDEN_NAMES),
    numpy_attributes=frozenset(_NUMPY_ATTRIBUTES),
    math_attributes=frozenset(_MATH_ATTRIBUTES),
    np_math_roots=frozenset(_NP_MATH_ROOTS),
    allowed_import_roots=frozenset(_ALLOWED_IMPORT_ROOTS),
    baseline_description=TSP_BASELINE_DESCRIPTION,
)

register_problem(TSP_SPEC)


# --- TSP 2-opt spec registration ---------------------------------------------
# Second type of algorithm interface: a bounded local-search decision. The
# evaluator owns the nearest-neighbour initial tour, the improving-move
# enumeration, move application, and the objective; the evolved entrypoint
# only selects among the candidates within a fixed move budget.
TSP2_SPEC = ProblemSpec(
    problem_id=TSP2_PROBLEM_NAME,
    entrypoint=TSP2_ENTRYPOINT,
    interface_version="v1",
    task_description=TSP2_TASK_DESCRIPTION,
    template_program=TSP2_TEMPLATE_PROGRAM,
    baseline_code=TSP2_BASELINE_CODE,
    objective_direction="minimize",
    split_offsets=TSP2_SPLIT_OFFSETS,
    build_suite=tsp2_build_suite,
    suite_hash=tsp2_suite_hash,
    validate_suite=_validate_tsp2_suite,
    evaluate_instances=_evaluate_tsp2_instances,
    safe_builtins=_SAFE_BUILTINS,
    forbidden_names=frozenset(_FORBIDDEN_NAMES),
    numpy_attributes=frozenset(_NUMPY_ATTRIBUTES),
    math_attributes=frozenset(_MATH_ATTRIBUTES),
    np_math_roots=frozenset(_NP_MATH_ROOTS),
    allowed_import_roots=frozenset(_ALLOWED_IMPORT_ROOTS),
    baseline_description=TSP2_BASELINE_DESCRIPTION,
)

register_problem(TSP2_SPEC)
