"""Small, reproducible FME pilot suites and a process-isolated evaluator.

The evaluator deliberately mirrors the public EoH constructive interfaces, but
does not import or instantiate their data generators.  Candidate programs are
executed in a separate process with a finite timeout.  The AST checks are a
policy guard, not an OS security sandbox: this module must not be treated as a
defence against a hostile local process or a kernel escape.
"""
from __future__ import annotations

import ast
import contextlib
import hashlib
import io
import json
import math
import os
import random
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Mapping

try:
    import numpy as np
except Exception:  # pragma: no cover - the project declares numpy
    np = None  # type: ignore[assignment]


_PROBLEMS = ("bp_online", "tsp_construct", "cvrp_construct")
_SPLIT_OFFSETS = {
    "dev_train": 0x0D3E0001,
    "dev_probe": 0x27A91C3D,
    "heldout": 0x51ED270B,
    # Kept for callers of the original pilot API; it has dev_train semantics.
    "dev": 0x0D3E0001,
}
_ALIASES = {
    "bp": "bp_online",
    "bin_packing": "bp_online",
    "bin packing": "bp_online",
    "bp online": "bp_online",
    "obp": "bp_online",
    "online bin packing": "bp_online",
    "online_bin_packing": "bp_online",
    "bp_online": "bp_online",
    "tsp": "tsp_construct",
    "tsp_construct": "tsp_construct",
    "cvrp": "cvrp_construct",
    "cvrp_construct": "cvrp_construct",
}

_FALLBACK_SPECS = {
    "bp_online": {
        "template_program": """def score(item: int, bins: np.ndarray) -> np.ndarray:
    \"\"\"Return one priority score for every feasible remaining capacity.\"\"\"
    return bins
""",
        "task_description": (
            "Design a score function for assigning each incoming item to a feasible "
            "bin; higher score is preferred and the number of used bins is minimized."
        ),
        "baseline_code": """def score(item: int, bins: np.ndarray) -> np.ndarray:
    return -(bins - item)
""",
    },
    "tsp_construct": {
        "template_program": """def select_next_node(current_node: int, destination_node: int,
                     unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]
""",
        "task_description": (
            "Given coordinates, construct a shortest closed TSP tour by selecting "
            "one unvisited node at each step."
        ),
        "baseline_code": """def select_next_node(current_node: int, destination_node: int,
                     unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]
""",
    },
    "cvrp_construct": {
        "template_program": """def select_next_node(current_node: int, depot: int,
                     unvisited_nodes: np.ndarray, rest_capacity: float,
                     demands: np.ndarray, distance_matrix: np.ndarray) -> int:
    return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]
""",
        "task_description": (
            "Given customer coordinates, demands and vehicle capacity, construct "
            "feasible depot-to-depot routes while minimizing total distance."
        ),
        "baseline_code": """def select_next_node(current_node: int, depot: int,
                     unvisited_nodes: np.ndarray, rest_capacity: float,
                     demands: np.ndarray, distance_matrix: np.ndarray) -> int:
    return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]
""",
    },
}


def _canonical_problem(problem: str) -> str:
    if not isinstance(problem, str):
        raise ValueError("unsupported_problem")
    key = problem.strip().lower().replace("-", "_")
    try:
        return _ALIASES[key]
    except KeyError as exc:
        raise ValueError("unsupported_problem") from exc


def _official_spec(problem: str) -> dict[str, str]:
    """Read class constants from the checked-in official examples using AST only."""
    canonical = _canonical_problem(problem)
    example_dir = {
        "bp_online": "bp_online",
        "tsp_construct": "tsp_construct",
        "cvrp_construct": "cvrp_construct",
    }[canonical]
    class_name = {
        "bp_online": "BPONLINE",
        "tsp_construct": "TSPCONST",
        "cvrp_construct": "CVRPCONST",
    }[canonical]
    spec = dict(_FALLBACK_SPECS[canonical])
    source_path = Path(__file__).resolve().parents[2] / "official_eoh" / "examples" / example_dir / "prob.py"
    try:
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    except (OSError, SyntaxError, UnicodeError):
        return spec
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != class_name:
            continue
        for statement in node.body:
            target: str | None = None
            value: ast.AST | None = None
            if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
                target_node = statement.targets[0]
                if isinstance(target_node, ast.Name):
                    target, value = target_node.id, statement.value
            elif isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
                target, value = statement.target.id, statement.value
            if target not in ("template_program", "task_description") or value is None:
                continue
            try:
                literal = ast.literal_eval(value)
            except (ValueError, TypeError, SyntaxError):
                continue
            if isinstance(literal, str):
                spec[target] = literal
        break
    return spec


def get_problem_spec(problem: str) -> dict[str, str]:
    """Return the official template/task text and a small executable baseline."""
    return _official_spec(problem)


def _suite_hash(problem: str, split: str, instances: list[Mapping[str, Any]]) -> str:
    payload = {"problem": problem, "split": split, "instances": instances}
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _finite_float(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError, OverflowError):
        return False


def build_suite(
    problem: str,
    seed: int,
    split: str,
    count: int = 4,
    size: int = 20,
) -> dict[str, Any]:
    """Build deterministic, independent dev or heldout pilot instances.

    BP ``size`` is the item count.  TSP ``size`` is the number of nodes, while
    CVRP ``size`` is the number of customers (the depot is stored separately).
    """
    canonical = _canonical_problem(problem)
    if split not in _SPLIT_OFFSETS:
        raise ValueError("invalid_split")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("invalid_seed")
    if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 32:
        raise ValueError("invalid_count")
    minimum_size = 1 if canonical in ("bp_online", "cvrp_construct") else 2
    if isinstance(size, bool) or not isinstance(size, int) or not minimum_size <= size <= 2000:
        raise ValueError("invalid_size")
    # A large, fixed split offset prevents accidental overlap even when callers
    # reuse the same nominal seed for the two visibility scopes.
    split_seed = seed + _SPLIT_OFFSETS[split]
    rng = random.Random(split_seed)
    instances: list[dict[str, Any]] = []
    for index in range(count):
        instance_id = f"{split}-{index}"
        if canonical == "bp_online":
            # The skewed distribution resembles the official Weibull data while
            # retaining enough large items to exercise exact fit behaviour.
            items = [max(1, min(100, int(round(rng.weibullvariate(35.0, 2.5))))) for _ in range(size)]
            instances.append({"instance_id": instance_id, "items": items, "capacity": 100})
        elif canonical == "tsp_construct":
            coordinates = [[round(rng.random(), 8), round(rng.random(), 8)] for _ in range(size)]
            instances.append({"instance_id": instance_id, "coordinates": coordinates})
        else:
            depot = [round(0.5 + 0.15 * (rng.random() - 0.5), 8), round(0.5 + 0.15 * (rng.random() - 0.5), 8)]
            customers = [[round(rng.random(), 8), round(rng.random(), 8)] for _ in range(size)]
            demands = [rng.randint(1, 9) for _ in range(size)]
            instances.append({
                "instance_id": instance_id,
                "depot": depot,
                "customer_coordinates": customers,
                "demands": demands,
                "capacity": 40,
            })
    return {"problem": canonical, "split": split, "instances": instances, "content_hash": _suite_hash(canonical, split, instances)}


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
    "abs", "add", "all", "allclose", "any", "argmax", "argmin", "argsort", "arange", "array", "array_equal", "asarray",
    "astype", "clip", "column_stack", "concatenate", "copy", "cos", "cumsum", "delete", "diag", "diff", "divide", "dot",
    "dtype", "e", "exp", "float32", "float64", "full", "hstack", "inf", "isfinite",
    "linalg", "max", "mean", "median", "min", "minimum", "nan", "ndarray", "ndim", "norm",
    "nonzero", "ones", "pi", "power", "ravel", "reshape", "round", "shape", "sin",
    "size", "sort", "sqrt", "square", "std", "sum", "tile", "tolist", "trunc", "unique",
    "where", "zeros", "zip", "repeat", "floor", "ceil", "int32", "int64", "uint32", "uint64", "bool_", "newaxis",
    # Safe ndarray properties/methods used by generated numerical heuristics.
    "T", "flatten", "item", "ndim", "astype", "reshape", "copy", "all", "any", "argmax",
    "argmin", "argsort", "clip", "max", "mean", "min", "nonzero", "ravel", "round", "sum",
}
_MATH_ATTRIBUTES = {
    "acos", "asin", "atan", "atan2", "ceil", "cos", "e", "exp", "fabs", "floor", "fmod",
    "hypot", "inf", "isfinite", "isclose", "log", "log10", "pi", "sin", "sqrt", "tan", "trunc",
}


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
                    raise ValueError("forbidden_import")
        elif isinstance(node, ast.ImportFrom):
            raise ValueError("forbidden_import")
        elif isinstance(node, ast.Name):
            if node.id in _FORBIDDEN_NAMES or node.id.startswith("__"):
                raise ValueError("forbidden_name")
        elif isinstance(node, ast.Attribute):
            # Numeric-only attribute whitelist.  In particular, do not expose
            # numpy's ctypeslib/f2py/_core or any other import/IO namespace.
            if node.attr.startswith("_") or node.attr not in (_NUMPY_ATTRIBUTES | _MATH_ATTRIBUTES):
                raise ValueError("forbidden_attribute")
        elif isinstance(node, (ast.ClassDef, ast.Lambda, ast.With, ast.AsyncWith, ast.Try, ast.Raise, ast.Delete, ast.Global, ast.Nonlocal)):
            raise ValueError("forbidden_syntax")
        elif isinstance(node, ast.Constant) and isinstance(node.value, (bytes, bytearray)):
            raise ValueError("forbidden_constant")
    return tree


class _QuietSink(io.TextIOBase):
    def write(self, text: str) -> int:  # pragma: no cover - only used by candidates
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
    canonical = _canonical_problem(problem)
    split = suite.get("split") if isinstance(suite, Mapping) else None
    if not isinstance(suite, Mapping) or suite.get("problem") != canonical or not isinstance(split, str) or split not in _SPLIT_OFFSETS:
        raise ValueError("invalid_suite")
    instances = suite.get("instances")
    given_hash = suite.get("content_hash")
    if not isinstance(instances, list) or not instances or not isinstance(given_hash, str):
        raise ValueError("invalid_suite")
    expected_hash = _suite_hash(canonical, split, instances)
    if given_hash != expected_hash:
        raise ValueError("suite_hash_mismatch")
    return instances, expected_hash


def _evaluate_bp(fn: Any, instances: list[Mapping[str, Any]]) -> list[float]:
    objectives = []
    for instance in instances:
        items, capacity = instance.get("items"), instance.get("capacity")
        if not isinstance(items, list) or not isinstance(capacity, int) or capacity <= 0:
            raise ValueError("invalid_instance")
        bins = np.full(len(items), capacity, dtype=float)
        for item in items:
            feasible = np.flatnonzero(bins + 1e-12 >= item)
            if feasible.size == 0:
                raise ValueError("infeasible_instance")
            view = bins[feasible].copy()
            before = view.copy()
            result = fn(int(item), view)
            if not np.array_equal(view, before):
                raise ValueError("candidate_mutated_input")
            scores = np.asarray(result)
            if scores.ndim != 1 or scores.size != feasible.size or not np.issubdtype(scores.dtype, np.number) or not np.all(np.isfinite(scores)):
                raise ValueError("invalid_return")
            chosen = int(feasible[int(np.argmax(scores))])
            bins[chosen] -= item
            if bins[chosen] < -1e-8:
                raise ValueError("capacity_violation")
        used = float(np.count_nonzero(bins < capacity - 1e-12))
        if not math.isfinite(used):
            raise ValueError("nonfinite_objective")
        objectives.append(used)
    return objectives


def _distance_matrix(points: list[list[float]]) -> np.ndarray:
    coords = np.asarray(points, dtype=float)
    if coords.ndim != 2 or coords.shape[1] != 2 or not np.all(np.isfinite(coords)):
        raise ValueError("invalid_instance")
    delta = coords[:, None, :] - coords[None, :, :]
    return np.sqrt(np.sum(delta * delta, axis=2))


def _evaluate_tsp(fn: Any, instances: list[Mapping[str, Any]]) -> list[float]:
    objectives = []
    for instance in instances:
        coordinates = instance.get("coordinates")
        if not isinstance(coordinates, list) or len(coordinates) < 2:
            raise ValueError("invalid_instance")
        matrix = _distance_matrix(coordinates)
        n = len(coordinates)
        route = [0]
        visited = {0}
        while len(route) < n:
            unvisited = np.asarray(sorted(set(range(n)) - visited), dtype=int)
            candidate_nodes = unvisited.copy()
            candidate_matrix = matrix.copy()
            result = fn(route[-1], 0, candidate_nodes, candidate_matrix)
            if not np.array_equal(candidate_nodes, unvisited) or not np.array_equal(candidate_matrix, matrix):
                raise ValueError("candidate_mutated_input")
            nxt = _as_index(result, set(int(x) for x in unvisited))
            if nxt is None:
                raise ValueError("invalid_return")
            route.append(nxt)
            visited.add(nxt)
        if len(route) != n or len(set(route)) != n:
            raise ValueError("invalid_tour")
        cost = float(sum(matrix[a, b] for a, b in zip(route, route[1:] + route[:1])))
        if not math.isfinite(cost):
            raise ValueError("nonfinite_objective")
        objectives.append(cost)
    return objectives


def _evaluate_cvrp(fn: Any, instances: list[Mapping[str, Any]]) -> list[float]:
    objectives = []
    for instance in instances:
        depot, customers, demands, capacity = (instance.get(key) for key in ("depot", "customer_coordinates", "demands", "capacity"))
        if not isinstance(depot, list) or not isinstance(customers, list) or not isinstance(demands, list) or len(customers) != len(demands) or not customers or not isinstance(capacity, (int, float)) or not _finite_float(capacity) or capacity <= 0:
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
            # The official CVRP contract permits an early depot return (0),
            # after which construction continues with a fresh vehicle.
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


def _evaluate_candidate_request(request: Mapping[str, Any]) -> dict[str, Any]:
    """Worker-side implementation; returns only stable, non-sensitive errors."""
    started = time.monotonic()
    problem = request.get("problem")
    suite = request.get("suite")
    code = request.get("code")
    suite_hash_value: str | None = None
    try:
        canonical = _canonical_problem(problem)
        instances, suite_hash = _validate_suite(suite, canonical)
        suite_hash_value = suite_hash
        entry = "score" if canonical == "bp_online" else "select_next_node"
        tree = _validate_candidate_ast(code, entry)
        def _restricted_import(name: str, globals: Any = None, locals: Any = None, fromlist: tuple[str, ...] = (), level: int = 0) -> Any:
            if level or name not in ("numpy", "math"):
                raise ImportError("restricted_import")
            module = np if name == "numpy" else math
            return module

        builtins_dict = dict(_SAFE_BUILTINS)
        builtins_dict["__import__"] = _restricted_import
        globals_dict = {"__builtins__": builtins_dict, "np": np, "numpy": np, "math": math}
        with contextlib.redirect_stdout(_QuietSink()), contextlib.redirect_stderr(_QuietSink()):
            exec(compile(tree, "<candidate>", "exec"), globals_dict, globals_dict)
        fn = globals_dict.get(entry)
        if not callable(fn):
            raise ValueError("missing_entrypoint")
        with contextlib.redirect_stdout(_QuietSink()), contextlib.redirect_stderr(_QuietSink()):
            if canonical == "bp_online":
                per_instance = _evaluate_bp(fn, instances)
            elif canonical == "tsp_construct":
                per_instance = _evaluate_tsp(fn, instances)
            else:
                per_instance = _evaluate_cvrp(fn, instances)
        objective = float(sum(per_instance) / len(per_instance))
        if not math.isfinite(objective) or any(not math.isfinite(float(x)) for x in per_instance):
            raise ValueError("nonfinite_objective")
        return {"valid": True, "objective": objective, "instance_objectives": per_instance, "suite_hash": suite_hash, "error_code": None, "elapsed_seconds": time.monotonic() - started}
    except ValueError as exc:
        # Error messages intentionally remain coarse and never include candidate
        # source or an exception representation.
        error_code = str(exc) if str(exc) in {
            "unsupported_problem", "invalid_suite", "suite_hash_mismatch", "invalid_code", "missing_entrypoint",
            "forbidden_import", "forbidden_name", "forbidden_attribute", "forbidden_syntax", "forbidden_constant",
            "invalid_instance", "infeasible_instance", "candidate_mutated_input", "invalid_return", "capacity_violation",
            "nonfinite_objective", "invalid_tour", "invalid_route",
        } else "candidate_error"
        return {"valid": False, "objective": None, "instance_objectives": [], "suite_hash": suite_hash_value, "error_code": error_code, "elapsed_seconds": time.monotonic() - started}
    except Exception:
        return {"valid": False, "objective": None, "instance_objectives": [], "suite_hash": suite_hash_value, "error_code": "candidate_exception", "elapsed_seconds": time.monotonic() - started}


class SubprocessEvaluator:
    """Evaluate one candidate in an independent process with a hard timeout."""

    def __init__(self, timeout: float = 20.0):
        if not _finite_float(timeout) or float(timeout) <= 0:
            raise ValueError("invalid_timeout")
        self.timeout = float(timeout)

    def evaluate(self, problem: str, code: str, suite: Mapping[str, Any]) -> dict[str, Any]:
        started = time.monotonic()
        try:
            canonical = _canonical_problem(problem)
            instances, expected_hash = _validate_suite(suite, canonical)
            if not isinstance(code, str):
                raise ValueError("invalid_code")
        except (ValueError, TypeError) as exc:
            error = str(exc) if str(exc) in {"unsupported_problem", "invalid_suite", "suite_hash_mismatch", "invalid_code"} else "invalid_request"
            return {"valid": False, "objective": None, "instance_objectives": [], "suite_hash": None, "error_code": error, "elapsed_seconds": time.monotonic() - started}
        request = {"problem": canonical, "code": code, "suite": dict(suite)}
        worker = Path(__file__).resolve().parents[2] / "scripts" / "fme_pilot_eval_worker.py"
        # Explicit allow-list: no API keys, cloud credentials, proxy secrets, or
        # unrelated application variables are inherited by the candidate process.
        safe_env = {key: os.environ[key] for key in ("PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "LANG", "LC_ALL") if key in os.environ}
        safe_env["PYTHONPATH"] = str(Path(__file__).resolve().parents[2])
        proc: subprocess.Popen[bytes] | None = None
        try:
            with tempfile.TemporaryDirectory(prefix="fme-pilot-") as temp_cwd:
                try:
                    proc = subprocess.Popen(
                        [sys.executable, str(worker)],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL,
                        cwd=temp_cwd,
                        env=safe_env,
                    )
                    payload = json.dumps(request, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                    stdout, _ = proc.communicate(payload, timeout=self.timeout)
                except subprocess.TimeoutExpired:
                    # Terminate and wait while the temporary cwd still exists;
                    # this avoids Windows cleanup races with a live child.
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
                    return {"valid": False, "objective": None, "instance_objectives": [], "suite_hash": expected_hash, "error_code": "timeout", "elapsed_seconds": time.monotonic() - started}
        except subprocess.TimeoutExpired:
            # The inner handler normally owns this path; retain a coarse
            # fallback for unusual process implementations.
            return {"valid": False, "objective": None, "instance_objectives": [], "suite_hash": expected_hash, "error_code": "timeout", "elapsed_seconds": time.monotonic() - started}
        except (OSError, TypeError, ValueError):
            return {"valid": False, "objective": None, "instance_objectives": [], "suite_hash": expected_hash, "error_code": "worker_error", "elapsed_seconds": time.monotonic() - started}
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
                if isinstance(objective, bool) or not _finite_float(objective) or any(isinstance(x, bool) or not _finite_float(x) for x in values):
                    raise ValueError
                expected_objective = float(sum(float(x) for x in values) / len(values))
                if float(objective) != expected_objective:
                    raise ValueError
            elif result.get("suite_hash") not in (expected_hash, None):
                raise ValueError
            # Report wall-clock time observed by the caller, not worker time.
            result["elapsed_seconds"] = time.monotonic() - started
            return result
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
            return {"valid": False, "objective": None, "instance_objectives": [], "suite_hash": expected_hash, "error_code": "worker_protocol", "elapsed_seconds": time.monotonic() - started}


__all__ = ["SubprocessEvaluator", "build_suite", "get_problem_spec"]
