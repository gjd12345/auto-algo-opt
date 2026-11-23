"""Shared AST whitelist, restricted hook compiler, subprocess evaluator, and frozen solver adapter.

Single execution contract shared by:
1. ``InterfaceValidator`` (Gates 1, 2, 3, 4, 5),
2. ``DynamicInterfaceProblem`` (EoH candidate evaluation), and
3. ``run_frozen_workbench_bundle`` (M1 Workbench re-evaluation of frozen M2 solvers).
"""

from __future__ import annotations

import ast
import atexit
import contextlib
import hashlib
import io
import json
import math
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import numpy as np

from agent_skill_loop.cvrp_workbench.protocol import prepare_instance_arrays, verify_cvrp_solution
from agent_skill_loop.evaluator import (
    _ALLOWED_IMPORT_ROOTS,
    _CONTAINER_METHODS,
    _FORBIDDEN_NAMES,
    _MATH_ATTRIBUTES,
    _NP_MATH_ROOTS,
    _NUMPY_ATTRIBUTES,
    _SAFE_BUILTINS,
    _attribute_root_id,
    _collect_np_math_aliases,
    _make_restricted_import,
    kill_process_tree,
)

from .contracts import (
    FrozenInterfaceSolver,
    GateFailure,
    classify_outcome,
    sha256_text,
)
from .templates import get_template_spec

_ALLOWED_ATTRIBUTES = frozenset(_NUMPY_ATTRIBUTES) | frozenset(_MATH_ATTRIBUTES)


class _QuietSink(io.TextIOBase):
    def write(self, text: str) -> int:
        return len(text)

    def flush(self) -> None:
        return None


def capability_contract_dict(*, hook_name: str, hook_signature: Sequence[str], template_id: str, template_version: str) -> dict[str, Any]:
    """Machine-derived capability contract mirroring ``validate_hook_ast`` exactly."""
    return {
        "interface": f"{template_id}/{template_version}:{hook_name}",
        "entrypoint": hook_name,
        "parameters": list(hook_signature),
        "allowed_import_roots": sorted(_ALLOWED_IMPORT_ROOTS),
        "allowed_numpy_math_roots": sorted(_NP_MATH_ROOTS),
        "allowed_numpy_attributes": sorted(_NUMPY_ATTRIBUTES),
        "allowed_math_attributes": sorted(_MATH_ATTRIBUTES),
        "safe_builtins": sorted(_SAFE_BUILTINS),
        "forbidden_names": sorted(_FORBIDDEN_NAMES),
        "input_contract": "All input arrays are read-only; mutating evaluator inputs is forbidden.",
        "side_effect_contract": "Filesystem, network, subprocess, reflection, and dynamic code execution are forbidden.",
    }


def _check_rebinding_target_failures(
    target: ast.expr,
    roots: set[str] | frozenset[str],
    failures: list[GateFailure],
) -> None:
    if isinstance(target, ast.Name):
        if target.id in roots:
            failures.append(GateFailure(
                gate_id=1,
                gate_name="ast_whitelist",
                error_code="forbidden_rebinding",
                line_no=getattr(target, "lineno", None),
                symbol=target.id,
                detail=f"Cannot rebind restricted module root '{target.id}'.",
                fix_hint=f"Rename local variable '{target.id}' so it does not shadow numpy/math.",
            ))
    elif isinstance(target, (ast.Tuple, ast.List)):
        for element in target.elts:
            _check_rebinding_target_failures(element, roots, failures)
    elif isinstance(target, ast.Starred):
        _check_rebinding_target_failures(target.value, roots, failures)


def _check_rebinding_args_failures(
    args: ast.arguments,
    roots: set[str] | frozenset[str],
    line_no: int | None,
    failures: list[GateFailure],
) -> None:
    params = [*args.posonlyargs, *args.args, *args.kwonlyargs]
    if args.vararg is not None:
        params.append(args.vararg)
    if args.kwarg is not None:
        params.append(args.kwarg)
    for param in params:
        if param.arg in roots:
            failures.append(GateFailure(
                gate_id=1,
                gate_name="ast_whitelist",
                error_code="forbidden_rebinding",
                line_no=getattr(param, "lineno", line_no),
                symbol=param.arg,
                detail=f"Function parameter '{param.arg}' shadows restricted module root.",
                fix_hint=f"Rename parameter '{param.arg}' to avoid shadowing numpy/math.",
            ))


def validate_hook_ast(
    code: str,
    *,
    hook_name: str,
    expected_args: Sequence[str],
) -> tuple[list[GateFailure], list[GateFailure]]:
    """Run Gate 1 (AST capability whitelist) and Gate 2 (entrypoint/signature) on hook source.

    Returns ``(gate1_failures, gate2_failures)`` with exact AST line numbers and actionable fix hints.
    Uses the exact same capability allowlists as ``agent_skill_loop.evaluator._validate_candidate_ast``.
    """
    g1: list[GateFailure] = []
    g2: list[GateFailure] = []

    if not isinstance(code, str) or not code.strip() or len(code.encode("utf-8")) > 100_000:
        g1.append(GateFailure(
            gate_id=1,
            gate_name="ast_whitelist",
            error_code="invalid_code",
            line_no=None,
            symbol=None,
            detail="Hook source must be a non-empty UTF-8 string under 100 KB.",
            fix_hint=f"Provide a clean Python function `def {hook_name}({', '.join(expected_args)}): ...`.",
        ))
        return g1, g2

    try:
        tree = ast.parse(code, mode="exec")
        compile(tree, "<m2_hook_candidate>", "exec")
    except SyntaxError as exc:
        g1.append(GateFailure(
            gate_id=1,
            gate_name="ast_whitelist",
            error_code="invalid_code",
            line_no=exc.lineno,
            symbol=None,
            detail=f"SyntaxError: {exc.msg}",
            fix_hint="Fix the Python syntax error at the reported line.",
        ))
        return g1, g2
    except (ValueError, TypeError, UnicodeError) as exc:
        g1.append(GateFailure(
            gate_id=1,
            gate_name="ast_whitelist",
            error_code="invalid_code",
            line_no=None,
            symbol=None,
            detail=f"Code compilation failed: {exc}",
            fix_hint="Ensure hook code contains valid ASCII/UTF-8 Python statements.",
        ))
        return g1, g2

    allowed_aliases = {root: (None, "np" if root == "numpy" else root) for root in _ALLOWED_IMPORT_ROOTS}
    np_math_aliases = _collect_np_math_aliases(tree, _NP_MATH_ROOTS)

    for node in ast.walk(tree):
        line_no = getattr(node, "lineno", None)

        if isinstance(node, ast.Assign):
            for target in node.targets:
                _check_rebinding_target_failures(target, _NP_MATH_ROOTS, g1)
        elif isinstance(node, ast.AnnAssign):
            _check_rebinding_target_failures(node.target, _NP_MATH_ROOTS, g1)
        elif isinstance(node, ast.AugAssign):
            _check_rebinding_target_failures(node.target, _NP_MATH_ROOTS, g1)
        elif isinstance(node, (ast.For, ast.comprehension)):
            _check_rebinding_target_failures(node.target, _NP_MATH_ROOTS, g1)
        elif isinstance(node, ast.NamedExpr):
            _check_rebinding_target_failures(node.target, _NP_MATH_ROOTS, g1)
        elif isinstance(node, (ast.FunctionDef, ast.Lambda)):
            _check_rebinding_args_failures(node.args, _NP_MATH_ROOTS, line_no, g1)

        if isinstance(node, ast.AsyncFunctionDef):
            g1.append(GateFailure(
                gate_id=1,
                gate_name="ast_whitelist",
                error_code="forbidden_syntax",
                line_no=line_no,
                symbol=node.name,
                detail="Async functions are forbidden in candidate hooks.",
                fix_hint="Replace `async def` with a synchronous `def` function.",
            ))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name not in allowed_aliases or alias.asname not in allowed_aliases[alias.name]:
                    g1.append(GateFailure(
                        gate_id=1,
                        gate_name="ast_whitelist",
                        error_code="forbidden_import",
                        line_no=line_no,
                        symbol=alias.name,
                        detail=f"Import '{alias.name}' (as '{alias.asname}') is outside the whitelist.",
                        fix_hint="Only `import numpy as np`, `import numpy`, and `import math` are permitted.",
                    ))
        elif isinstance(node, ast.ImportFrom):
            g1.append(GateFailure(
                gate_id=1,
                gate_name="ast_whitelist",
                error_code="forbidden_import",
                line_no=line_no,
                symbol=node.module or "from_import",
                detail=f"`from {node.module} import ...` is forbidden.",
                fix_hint="Replace with top-level `import numpy as np` or `import math`.",
            ))
        elif isinstance(node, ast.Name):
            if node.id in _FORBIDDEN_NAMES or node.id.startswith("__"):
                g1.append(GateFailure(
                    gate_id=1,
                    gate_name="ast_whitelist",
                    error_code="forbidden_name",
                    line_no=line_no,
                    symbol=node.id,
                    detail=f"Reference to forbidden identifier '{node.id}'.",
                    fix_hint="Remove forbidden I/O, reflection, or dunder references; use numpy/math operations only.",
                ))
        elif isinstance(node, ast.Attribute):
            if isinstance(node.ctx, ast.Store):
                g1.append(GateFailure(
                    gate_id=1,
                    gate_name="ast_whitelist",
                    error_code="forbidden_rebinding",
                    line_no=line_no,
                    symbol=node.attr,
                    detail=f"Attribute assignment to '.{node.attr}' is forbidden.",
                    fix_hint="Compute new local arrays instead of mutating attributes.",
                ))
            elif node.attr.startswith("_"):
                g1.append(GateFailure(
                    gate_id=1,
                    gate_name="ast_whitelist",
                    error_code="forbidden_attribute",
                    line_no=line_no,
                    symbol=node.attr,
                    detail=f"Private/dunder attribute '.{node.attr}' is forbidden.",
                    fix_hint="Use public numpy/math operations only.",
                ))
            else:
                root = _attribute_root_id(node)
                if root in _NP_MATH_ROOTS or root in np_math_aliases:
                    if node.attr not in _ALLOWED_ATTRIBUTES:
                        g1.append(GateFailure(
                            gate_id=1,
                            gate_name="ast_whitelist",
                            error_code="forbidden_attribute",
                            line_no=line_no,
                            symbol=f"{root}.{node.attr}",
                            detail=f"Attribute '{root}.{node.attr}' is not in the numpy/math whitelist.",
                            fix_hint="Use whitelisted vectorized numpy/math functions (e.g., np.where, np.clip, np.sqrt, np.exp).",
                        ))
                elif node.attr not in _ALLOWED_ATTRIBUTES and node.attr not in _CONTAINER_METHODS:
                    g1.append(GateFailure(
                        gate_id=1,
                        gate_name="ast_whitelist",
                        error_code="forbidden_attribute",
                        line_no=line_no,
                        symbol=node.attr,
                        detail=f"Attribute '.{node.attr}' is not allowed.",
                        fix_hint="Avoid non-whitelisted object methods; operate with numpy arrays and Python lists.",
                    ))
        elif isinstance(node, (ast.ClassDef, ast.Lambda, ast.With, ast.AsyncWith, ast.Try, ast.Raise, ast.Delete, ast.Global, ast.Nonlocal)):
            g1.append(GateFailure(
                gate_id=1,
                gate_name="ast_whitelist",
                error_code="forbidden_syntax",
                line_no=line_no,
                symbol=type(node).__name__,
                detail=f"Syntax construct '{type(node).__name__}' is forbidden in candidate hooks.",
                fix_hint="Express the scoring logic using plain functions, loops, conditionals, and vectorized numpy expressions.",
            ))
        elif isinstance(node, ast.Constant) and isinstance(node.value, (bytes, bytearray)):
            g1.append(GateFailure(
                gate_id=1,
                gate_name="ast_whitelist",
                error_code="forbidden_constant",
                line_no=line_no,
                symbol="bytes",
                detail="Byte literal constants are forbidden.",
                fix_hint="Use numeric literals only.",
            ))

    # Gate 2: Entrypoint & exact positional parameter list
    top_funcs = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == hook_name]
    if not top_funcs:
        g2.append(GateFailure(
            gate_id=2,
            gate_name="template_and_signature",
            error_code="missing_entrypoint",
            line_no=None,
            symbol=hook_name,
            detail=f"Top-level function '{hook_name}' not found.",
            fix_hint=f"Define `def {hook_name}({', '.join(expected_args)}):` at top level.",
        ))
    else:
        fn_node = top_funcs[-1]
        arg_names = [a.arg for a in fn_node.args.args]
        has_extra = bool(fn_node.args.posonlyargs or fn_node.args.kwonlyargs or fn_node.args.vararg or fn_node.args.kwarg)
        if has_extra or tuple(arg_names) != tuple(expected_args):
            g2.append(GateFailure(
                gate_id=2,
                gate_name="template_and_signature",
                error_code="signature_mismatch",
                line_no=fn_node.lineno,
                symbol=hook_name,
                detail=f"Expected signature `({', '.join(expected_args)})`, got `({', '.join(arg_names)})` (extra_kinds={has_extra}).",
                fix_hint=f"Change signature to `def {hook_name}({', '.join(expected_args)}):`.",
            ))

    return g1, g2


def compile_hook_function(
    code: str,
    *,
    hook_name: str,
    expected_args: Sequence[str],
) -> Callable[..., Any]:
    """Validate and compile a hook function inside the restricted capability namespace."""
    g1, g2 = validate_hook_ast(code, hook_name=hook_name, expected_args=expected_args)
    if g1:
        f = g1[0]
        raise ValueError(f"{f.error_code}:{f.symbol or f.detail}")
    if g2:
        f = g2[0]
        raise ValueError(f"{f.error_code}:{f.symbol or f.detail}")

    restricted_builtins = dict(_SAFE_BUILTINS)
    restricted_builtins["__import__"] = _make_restricted_import(set(_ALLOWED_IMPORT_ROOTS))
    namespace: dict[str, Any] = {
        "__builtins__": restricted_builtins,
        "np": np,
        "numpy": np,
        "math": math,
    }
    compiled = compile(ast.parse(code, mode="exec"), f"<m2_hook:{hook_name}>", "exec")
    sink = _QuietSink()
    with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
        exec(compiled, namespace, namespace)
    fn = namespace.get(hook_name)
    if not callable(fn):
        raise ValueError(f"missing_entrypoint:{hook_name}")
    return fn


def evaluate_hook_on_instance_inprocess(
    *,
    template_id: str,
    template_version: str,
    hook_fn: Callable[..., Any],
    instance: Mapping[str, Any],
    postprocess_mode: str = "none",
    template_options: Mapping[str, Any] | None = None,
    distance_convention: str = "euc_2d_float",
    vehicle_limit_policy: str = "unconstrained",
    time_budget_ms: float | None = 500.0,
    capture_merge_sequence: bool = False,
) -> dict[str, Any]:
    """Run one registered template + compiled hook on one CVRP instance and verify via M1 verifier."""
    tpl = get_template_spec(template_id, template_version)
    t_pre0 = time.perf_counter()
    matrix, demands, capacity = prepare_instance_arrays(instance, distance_convention=distance_convention)
    matrix_orig = matrix.copy()
    demands_orig = demands.copy()
    preprocess_ms = (time.perf_counter() - t_pre0) * 1000.0

    t_solve0 = time.perf_counter()
    status = "ok"
    error_code: str | None = None
    error_detail: str | None = None
    routes: list[list[int]] = []
    meta: dict[str, Any] = {}
    sink = _QuietSink()
    try:
        with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink), np.errstate(all="ignore"):
            routes, meta = tpl.runner(
                matrix,
                demands,
                capacity,
                hook_fn,
                postprocess_mode=postprocess_mode,
                time_budget_ms=time_budget_ms,
                template_options=template_options,
                capture_merge_sequence=capture_merge_sequence,
            )
    except Exception as exc:
        status = "error"
        msg = str(exc)
        if msg.startswith("candidate_mutated_input"):
            error_code = "candidate_mutated_input"
        elif msg.startswith("invalid_return"):
            error_code = "invalid_return"
        elif msg.startswith("nonfinite_hook_scores"):
            error_code = "nonfinite_objective"
        else:
            error_code = "hook_runtime_exception"
        error_detail = f"{type(exc).__name__}: {exc}"
    solve_ms = (time.perf_counter() - t_solve0) * 1000.0

    if status == "ok":
        verification = verify_cvrp_solution(
            instance,
            routes,
            distance_convention=distance_convention,
            vehicle_limit_policy=vehicle_limit_policy,
            expected_matrix=matrix_orig,
            submitted_matrix=matrix,
            expected_demands=demands_orig,
            submitted_demands=demands,
        )
        if not verification["valid"]:
            status = "infeasible"
            error_code = verification["error_code"]
            error_detail = verification["error_detail"]
    else:
        verification = {
            "valid": False,
            "error_code": error_code,
            "error_detail": error_detail,
            "tour_length": None,
            "route_count": 0,
            "route_loads": [],
            "route_distances": [],
            "capacity": capacity,
            "max_utilization": None,
            "mean_utilization": None,
            "target_vehicles": instance.get("k_vehicles"),
            "within_vehicle_limit": None,
            "exact_vehicle_count": None,
            "vehicle_count_delta": None,
            "verify_ms": 0.0,
        }

    ref_obj = instance.get("reference_objective")
    ref_val = float(ref_obj) if isinstance(ref_obj, (int, float)) and math.isfinite(float(ref_obj)) and float(ref_obj) > 0 else None
    rel_gap = (
        round((float(verification["tour_length"]) - ref_val) / ref_val, 6)
        if (verification["valid"] and verification["tour_length"] is not None and ref_val is not None)
        else None
    )
    stop_reason = meta.get("stop_reason")
    # The v1 templates use this bit for both iteration and wall-clock limits.
    budget_exhausted = bool(meta.get("budget_exhausted", False)) and stop_reason != "max_passes"
    outcome_class = classify_outcome(
        valid=bool(verification["valid"]),
        status=status,
        budget_exhausted=budget_exhausted,
    )

    out: dict[str, Any] = {
        "instance_id": str(instance.get("instance_id", "")),
        "status": status,
        "outcome_class": outcome_class,
        "valid": bool(verification["valid"]),
        "error_code": verification["error_code"],
        "error_detail": verification["error_detail"],
        "routes": routes if verification["valid"] else [],
        "tour_length": verification["tour_length"],
        "reference_objective": ref_val,
        "reference_kind": instance.get("reference_kind"),
        "rel_gap": rel_gap,
        "route_count": verification["route_count"],
        "route_loads": verification["route_loads"],
        "route_distances": verification["route_distances"],
        "max_utilization": verification["max_utilization"],
        "mean_utilization": verification["mean_utilization"],
        "target_vehicles": verification["target_vehicles"],
        "within_vehicle_limit": verification["within_vehicle_limit"],
        "exact_vehicle_count": verification["exact_vehicle_count"],
        "vehicle_count_delta": verification["vehicle_count_delta"],
        "preprocess_ms": round(preprocess_ms, 4),
        "candidate_gen_ms": float(meta.get("candidate_gen_ms", 0.0)),
        "hook_ms": float(meta.get("hook_ms", 0.0)),
        "merge_ms": float(meta.get("merge_ms", 0.0)),
        "postprocess_ms": float(meta.get("postprocess_ms", 0.0)),
        "solve_ms": round(solve_ms, 4),
        "verify_ms": float(verification["verify_ms"]),
        "voluntary_early_return_count": int(meta.get("voluntary_early_return_count", 0)),
        "forced_capacity_return_count": int(meta.get("forced_capacity_return_count", 0)),
        "trace_steps": None,
        "budget_exhausted": budget_exhausted,
        "stop_reason": str(meta.get("stop_reason", "error" if status != "ok" else "completed")),
        "hook_call_count": int(meta.get("hook_call_count", 0)),
        "merges_applied": int(meta.get("merges_applied", 0)),
        "candidate_pair_count": int(meta.get("candidate_pair_count", 0)),
        "template_source_sha256": tpl.template_source_sha256,
    }
    if capture_merge_sequence:
        out["merge_sequence"] = meta.get("merge_sequence")
        out["pre_postprocess_routes"] = meta.get("pre_postprocess_routes")
    return out


def _worker_environment(repo_root: Path) -> dict[str, str]:
    names = ("PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "LANG", "LC_ALL")
    env = {name: os.environ[name] for name in names if name in os.environ}
    return {**env, "PYTHONNOUSERSITE": "1", "PYTHONPATH": str(repo_root)}


class DynamicSubprocessEvaluator:
    """Process-isolated evaluator for M2 templates & hooks with separate candidate timeout vs instance budget."""

    def __init__(self, *, candidate_timeout_s: float = 20.0) -> None:
        self.candidate_timeout_s = float(candidate_timeout_s)

    def evaluate(
        self,
        *,
        template_id: str,
        template_version: str,
        hook_code: str,
        instances: Sequence[Mapping[str, Any]],
        postprocess_mode: str = "none",
        template_options: Mapping[str, Any] | None = None,
        distance_convention: str = "euc_2d_float",
        vehicle_limit_policy: str = "unconstrained",
        instance_time_budget_ms: float | None = 500.0,
        capture_merge_sequence: bool = False,
    ) -> dict[str, Any]:
        """Evaluate a hook across ``instances`` in a dedicated subprocess with hard kill on timeout."""
        request = {
            "template_id": template_id,
            "template_version": template_version,
            "postprocess_mode": postprocess_mode,
            "template_options": dict(template_options or {}),
            "hook_code": hook_code,
            "instances": [dict(inst) for inst in instances],
            "distance_convention": distance_convention,
            "vehicle_limit_policy": vehicle_limit_policy,
            "time_budget_ms": instance_time_budget_ms,
            "capture_merge_sequence": bool(capture_merge_sequence),
            "parent_pid": os.getpid(),
        }
        payload_bytes = json.dumps(request, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")

        repo_root = Path(__file__).resolve().parents[2]
        env = _worker_environment(repo_root)

        t0 = time.perf_counter()
        popen_kwargs: dict[str, Any] = {
            "stdin": subprocess.PIPE,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "cwd": str(repo_root),
            "env": env,
        }
        if os.name == "nt":
            popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        else:
            popen_kwargs["start_new_session"] = True

        proc = subprocess.Popen(
            [sys.executable, "-m", "agent_skill_loop.interface_design.eval_worker"],
            **popen_kwargs,
        )
        try:
            stdout, stderr = proc.communicate(input=payload_bytes, timeout=self.candidate_timeout_s)
        except subprocess.TimeoutExpired:
            kill_process_tree(proc)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            return {
                "valid": False,
                "objective": None,
                "error_code": "candidate_timeout",
                "error_detail": f"Subprocess exceeded candidate_timeout_s={self.candidate_timeout_s}",
                "failures": [
                    GateFailure(
                        gate_id=5,
                        gate_name="budget_and_timeout",
                        error_code="candidate_timeout",
                        line_no=None,
                        symbol=None,
                        detail=f"Candidate subprocess killed after {self.candidate_timeout_s:.2f}s outer timeout.",
                        fix_hint="Remove infinite loops or reduce per-call complexity so the hook finishes well inside budget.",
                    ).as_dict()
                ],
                "records": [],
                "worker_wall_ms": round(elapsed_ms, 4),
                "subprocess_overhead_ms": round(elapsed_ms, 4),
            }

        total_wall_ms = (time.perf_counter() - t0) * 1000.0
        text = stdout.decode("utf-8", errors="replace").strip()
        if not text:
            err_tail = stderr.decode("utf-8", errors="replace").strip()[-300:]
            return {
                "valid": False,
                "objective": None,
                "error_code": "worker_crash",
                "error_detail": err_tail or f"returncode={proc.returncode}",
                "failures": [],
                "records": [],
                "worker_wall_ms": round(total_wall_ms, 4),
                "subprocess_overhead_ms": round(total_wall_ms, 4),
            }
        try:
            resp = json.loads(text)
        except json.JSONDecodeError as exc:
            return {
                "valid": False,
                "objective": None,
                "error_code": "worker_protocol",
                "error_detail": f"JSONDecodeError: {exc}",
                "failures": [],
                "records": [],
                "worker_wall_ms": round(total_wall_ms, 4),
                "subprocess_overhead_ms": round(total_wall_ms, 4),
            }

        inner_ms = float(resp.get("inner_compute_ms", 0.0))
        resp["worker_wall_ms"] = round(total_wall_ms, 4)
        resp["subprocess_overhead_ms"] = round(max(0.0, total_wall_ms - inner_ms), 4)
        return resp


class _FrozenEvaluationWorker:
    """Reuse a worker on successful calls and replace it after a deadline or crash."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._proc: subprocess.Popen[bytes] | None = None
        self._owner_pid = os.getpid()

    def close(self) -> None:
        proc, self._proc = self._proc, None
        if proc is None or self._owner_pid != os.getpid():
            return
        if proc.poll() is None:
            kill_process_tree(proc)
        for pipe in (proc.stdin, proc.stdout):
            if pipe is not None:
                pipe.close()

    def call(self, request: Mapping[str, Any], timeout_s: float) -> dict[str, Any]:
        data = json.dumps(request, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8") + b"\n"
        with self._lock:
            if self._owner_pid != os.getpid():
                self._proc = None
                self._owner_pid = os.getpid()
            if self._proc is None or self._proc.poll() is not None:
                self.close()
                repo_root = Path(__file__).resolve().parents[2]
                self._proc = subprocess.Popen(
                    [sys.executable, "-m", "agent_skill_loop.interface_design.eval_worker", "--stream"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    cwd=repo_root,
                    env=_worker_environment(repo_root),
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                    start_new_session=os.name != "nt",
                )
            proc = self._proc
            response: queue.Queue[bytes] = queue.Queue(maxsize=1)

            def exchange() -> None:
                try:
                    assert proc.stdin is not None and proc.stdout is not None
                    proc.stdin.write(data)
                    proc.stdin.flush()
                    response.put(proc.stdout.readline())
                except (OSError, ValueError):
                    response.put(b"")

            threading.Thread(target=exchange, daemon=True).start()
            try:
                raw = response.get(timeout=timeout_s)
            except queue.Empty:
                self.close()
                return {"error_code": "candidate_timeout", "error_detail": f"Frozen worker exceeded {timeout_s:g}s"}
            try:
                decoded = json.loads(raw)
                if not isinstance(decoded, dict):
                    raise ValueError("worker response must be an object")
                return decoded
            except ValueError:
                self.close()
                return {"error_code": "worker_protocol", "error_detail": "Frozen worker returned no valid response"}


_FROZEN_WORKER = _FrozenEvaluationWorker()
atexit.register(_FROZEN_WORKER.close)


def evaluate_frozen_interface_solver(
    frozen_solver: FrozenInterfaceSolver,
    instance: Mapping[str, Any],
    *,
    distance_convention: str = "euc_2d_float",
    vehicle_limit_policy: str = "unconstrained",
    time_budget_ms: float | None = None,
    capture_merge_sequence: bool = False,
) -> dict[str, Any]:
    """Unified M1 Workbench adapter for a frozen M2 solver.

    Verifies BOTH ``template_source_sha256`` and ``hook_code_sha256`` before execution so
    a named version is guaranteed byte-reproducible between EoH evaluation and Workbench re-evaluation.
    """
    tpl = get_template_spec(frozen_solver.template_id, frozen_solver.template_version)
    if tpl.template_source_sha256 != frozen_solver.template_source_sha256:
        raise ValueError(
            f"template_source_sha256_mismatch:{frozen_solver.solver_id}:"
            f"expected={frozen_solver.template_source_sha256[:12]}_actual={tpl.template_source_sha256[:12]}"
        )
    if sha256_text(frozen_solver.hook_code) != frozen_solver.hook_code_sha256:
        raise ValueError(f"hook_code_sha256_mismatch:{frozen_solver.solver_id}")
    if frozen_solver.hook_name != tpl.hook_name:
        raise ValueError(f"hook_name_mismatch:{frozen_solver.hook_name}!={tpl.hook_name}")

    budget = time_budget_ms if time_budget_ms is not None else frozen_solver.default_budget_ms
    if not math.isfinite(budget) or budget <= 0:
        raise ValueError("frozen_evaluation_budget_must_be_positive_and_finite")
    started = time.perf_counter()
    response = _FROZEN_WORKER.call({
        "template_id": frozen_solver.template_id,
        "template_version": frozen_solver.template_version,
        "hook_code": frozen_solver.hook_code,
        "instances": [dict(instance)],
        "postprocess_mode": frozen_solver.postprocess_mode,
        "template_options": dict(frozen_solver.template_options),
        "distance_convention": distance_convention,
        "vehicle_limit_policy": vehicle_limit_policy,
        "time_budget_ms": budget,
        "capture_merge_sequence": capture_merge_sequence,
        "parent_pid": os.getpid(),
    }, timeout_s=max(5.0, budget / 1000.0 + 2.0))
    records = response.get("records")
    if records:
        if response.get("template_source_sha256") != frozen_solver.template_source_sha256:
            raise ValueError(f"worker_template_source_sha256_mismatch:{frozen_solver.solver_id}")
        return records[0]
    code = response.get("error_code") or "worker_protocol"
    status = "timeout" if code == "candidate_timeout" else "error"
    return {
        "status": status,
        "valid": False,
        "outcome_class": classify_outcome(valid=False, status=status, budget_exhausted=status == "timeout"),
        "error_code": code,
        "error_detail": response.get("error_detail"),
        "budget_exhausted": status == "timeout",
        "tour_length": None,
        "routes": [],
        "route_count": 0,
        "route_loads": [],
        "route_distances": [],
        "max_utilization": None,
        "mean_utilization": None,
        "reference_objective": instance.get("reference_objective"),
        "reference_kind": instance.get("reference_kind"),
        "rel_gap": None,
        "target_vehicles": instance.get("k_vehicles", instance.get("max_vehicles")),
        "within_vehicle_limit": None,
        "exact_vehicle_count": None,
        "vehicle_count_delta": None,
        "preprocess_ms": 0.0,
        "solve_ms": round((time.perf_counter() - started) * 1000.0, 4),
        "verify_ms": 0.0,
    }
