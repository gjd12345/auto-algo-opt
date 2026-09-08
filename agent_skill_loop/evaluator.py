"""Process-isolated CVRP evaluator. Worker imports only this package."""

from __future__ import annotations

import ast
import builtins
import contextlib
import io
import json
import math
import os
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

from agent_skill_loop.contracts import ENTRYPOINT_CVRP, PROBLEM_CVRP, EvaluationResult
from agent_skill_loop.problems.cvrp import SPLIT_OFFSETS, finite_float, suite_hash

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
_KNOWN_ERRORS = {
    "unsupported_problem", "invalid_suite", "suite_hash_mismatch", "invalid_code",
    "missing_entrypoint", "forbidden_import", "forbidden_name", "forbidden_attribute",
    "forbidden_syntax", "forbidden_constant", "invalid_instance", "infeasible_instance",
    "candidate_mutated_input", "invalid_return", "capacity_violation", "nonfinite_objective",
    "invalid_route",
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
    import hashlib
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _attribute_root_id(node: ast.Attribute) -> str | None:
    current: ast.AST = node.value
    while isinstance(current, ast.Attribute):
        current = current.value
    if isinstance(current, ast.Name):
        return current.id
    return None


def _restricted_import(name: str, globals: Any = None, locals: Any = None, fromlist: tuple[str, ...] = (), level: int = 0) -> Any:
    # Candidate AST cannot emit ImportFrom/relative import. Numpy ndarray methods
    # still call __import__ from the candidate frame for numpy.* submodules.
    if level:
        module_name = str(globals.get("__name__") or "") if isinstance(globals, dict) else ""
        if not (module_name == "numpy" or module_name.startswith("numpy.") or module_name == "math" or module_name.startswith("math.")):
            raise ImportError("restricted_import")
        return _REAL_IMPORT(name, globals, locals, fromlist, level)
    root = (name or "").split(".", 1)[0]
    if root not in _ALLOWED_IMPORT_ROOTS:
        raise ImportError("restricted_import")
    return _REAL_IMPORT(name, globals, locals, fromlist, level)


def _validate_candidate_ast(code: str, required_entry: str) -> ast.Module:
    if not isinstance(code, str) or not code.strip() or len(code.encode("utf-8")) > 100_000:
        raise ValueError("invalid_code")
    try:
        tree = ast.parse(code, mode="exec")
        compile(tree, "<candidate>", "exec")
    except (SyntaxError, ValueError, TypeError, UnicodeError) as exc:
        raise ValueError("invalid_code") from exc
    function_names = {node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    if required_entry not in function_names:
        raise ValueError("missing_entrypoint")
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef):
            raise ValueError("forbidden_syntax")
        if isinstance(node, ast.Import):
            for alias in node.names:
                allowed_aliases = {"numpy": (None, "np"), "math": (None, "math")}
                if alias.name not in allowed_aliases or alias.asname not in allowed_aliases[alias.name]:
                    raise EvalError("forbidden_import", alias.name)
        elif isinstance(node, ast.ImportFrom):
            raise EvalError("forbidden_import", node.module or "from_import")
        elif isinstance(node, ast.Name):
            if node.id in _FORBIDDEN_NAMES or node.id.startswith("__"):
                raise EvalError("forbidden_name", node.id)
        elif isinstance(node, ast.Attribute):
            if node.attr.startswith("_"):
                raise EvalError("forbidden_attribute", node.attr)
            root = _attribute_root_id(node)
            if root in _NP_MATH_ROOTS and node.attr not in (_NUMPY_ATTRIBUTES | _MATH_ATTRIBUTES):
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


def _validate_suite(suite: Mapping[str, Any], problem: str) -> tuple[list[Mapping[str, Any]], str]:
    if problem != PROBLEM_CVRP:
        raise ValueError("unsupported_problem")
    split = suite.get("split") if isinstance(suite, Mapping) else None
    if not isinstance(suite, Mapping) or suite.get("problem") != PROBLEM_CVRP or not isinstance(split, str) or split not in SPLIT_OFFSETS:
        raise ValueError("invalid_suite")
    instances = suite.get("instances")
    given_hash = suite.get("content_hash")
    if not isinstance(instances, list) or not instances or not isinstance(given_hash, str):
        raise ValueError("invalid_suite")
    expected = suite_hash(PROBLEM_CVRP, split, instances)
    if given_hash != expected:
        raise ValueError("suite_hash_mismatch")
    return instances, expected


def _distance_matrix(points: list[list[float]]):
    coords = np.asarray(points, dtype=float)
    if coords.ndim != 2 or coords.shape[1] != 2 or not np.all(np.isfinite(coords)):
        raise ValueError("invalid_instance")
    delta = coords[:, None, :] - coords[None, :, :]
    return np.sqrt(np.sum(delta * delta, axis=2))


def _evaluate_cvrp(fn: Any, instances: list[Mapping[str, Any]]) -> list[float]:
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
    return objectives


def evaluate_candidate_request(request: Mapping[str, Any]) -> dict[str, Any]:
    started = time.monotonic()
    problem = request.get("problem")
    suite = request.get("suite")
    code = request.get("code")
    suite_hash_value: str | None = None
    try:
        if problem != PROBLEM_CVRP:
            raise ValueError("unsupported_problem")
        instances, expected = _validate_suite(suite, PROBLEM_CVRP)
        suite_hash_value = expected
        tree = _validate_candidate_ast(code, ENTRYPOINT_CVRP)

        builtins_dict = dict(_SAFE_BUILTINS)
        builtins_dict["__import__"] = _restricted_import
        globals_dict = {"__builtins__": builtins_dict, "np": np, "numpy": np, "math": math}
        with contextlib.redirect_stdout(_QuietSink()), contextlib.redirect_stderr(_QuietSink()):
            exec(compile(tree, "<candidate>", "exec"), globals_dict, globals_dict)
        fn = globals_dict.get(ENTRYPOINT_CVRP)
        if not callable(fn):
            raise ValueError("missing_entrypoint")
        with contextlib.redirect_stdout(_QuietSink()), contextlib.redirect_stderr(_QuietSink()):
            per_instance = _evaluate_cvrp(fn, instances)
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
    return EvaluationResult(
        valid=bool(payload.get("valid")),
        objective=payload.get("objective"),
        instance_objectives=tuple(float(x) for x in values) if payload.get("valid") else (),
        suite_hash=payload.get("suite_hash"),
        error_code=payload.get("error_code"),
        elapsed_seconds=float(payload.get("elapsed_seconds") or 0.0),
        error_detail=payload.get("error_detail"),
    )


class SubprocessEvaluator:
    def __init__(self, timeout: float = 20.0):
        if not finite_float(timeout) or float(timeout) <= 0:
            raise ValueError("invalid_timeout")
        self.timeout = float(timeout)

    def evaluate(self, code: str, suite: Mapping[str, Any]) -> EvaluationResult:
        started = time.monotonic()
        try:
            instances, expected_hash = _validate_suite(suite, PROBLEM_CVRP)
            if not isinstance(code, str):
                raise ValueError("invalid_code")
        except (ValueError, TypeError) as exc:
            error = str(exc) if str(exc) in {"unsupported_problem", "invalid_suite", "suite_hash_mismatch", "invalid_code"} else "invalid_request"
            return EvaluationResult(False, None, (), None, error, time.monotonic() - started)
        request = {"problem": PROBLEM_CVRP, "code": code, "suite": dict(suite)}
        package_root = Path(__file__).resolve().parents[1]
        safe_env = {key: os.environ[key] for key in ("PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "LANG", "LC_ALL") if key in os.environ}
        safe_env["PYTHONPATH"] = str(package_root)
        proc: subprocess.Popen[bytes] | None = None
        stdout = b""
        try:
            with tempfile.TemporaryDirectory(prefix="skill-loop-") as temp_cwd:
                try:
                    proc = subprocess.Popen(
                        [sys.executable, "-m", "agent_skill_loop.eval_worker"],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL,
                        cwd=temp_cwd,
                        env=safe_env,
                    )
                    payload = json.dumps(request, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                    stdout, _ = proc.communicate(payload, timeout=self.timeout)
                except subprocess.TimeoutExpired:
                    if proc is not None:
                        try:
                            proc.kill()
                        except OSError:
                            pass
                        try:
                            proc.communicate(timeout=1.0)
                        except subprocess.TimeoutExpired:
                            try:
                                proc.wait(timeout=1.0)
                            except (OSError, subprocess.TimeoutExpired):
                                pass
                    return EvaluationResult(False, None, (), expected_hash, "timeout", time.monotonic() - started)
        except subprocess.TimeoutExpired:
            return EvaluationResult(False, None, (), expected_hash, "timeout", time.monotonic() - started)
        except (OSError, TypeError, ValueError):
            return EvaluationResult(False, None, (), expected_hash, "worker_error", time.monotonic() - started)
        try:
            result = json.loads(stdout.decode("utf-8"))
            if not isinstance(result, dict) or set(("valid", "objective", "instance_objectives", "suite_hash", "error_code", "elapsed_seconds")) - set(result):
                raise ValueError
            if not isinstance(result.get("valid"), bool):
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
