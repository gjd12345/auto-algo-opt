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
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Mapping, Sequence

import numpy as np

from agent_skill_loop.cvrp_workbench.protocol import normalize_routes, prepare_instance_arrays, verify_cvrp_solution
from agent_skill_loop.evaluator import (
    _ALLOWED_IMPORT_ROOTS,
    _CONTAINER_METHODS,
    _FORBIDDEN_NAMES,
    _LEGACY_NUMPY_ATTRIBUTES,
    _MATH_ATTRIBUTES,
    _NP_MATH_ROOTS,
    _NUMPY_ATTRIBUTES,
    _SAFE_BUILTINS,
    _attribute_root_id,
    _collect_np_math_aliases,
    _expr_is_np_math_alias,
    _make_restricted_import,
    kill_process_tree,
)

from .contracts import (
    FrozenInterfaceSolver,
    GateFailure,
    HookSpec,
    LEGACY_CVRP_PROTOCOL_ID,
    OUTCOME_COMPLETED,
    classify_outcome,
    hook_bundle_metadata,
    sha256_text,
)
from .templates import TemplateSpec, get_template_spec

_NUMPY_ROOTS = frozenset({"np", "numpy"})
_MATH_ROOTS = frozenset({"math"})


def _numpy_attributes(allow_extended_numpy_whitelist: bool) -> set[str]:
    return _NUMPY_ATTRIBUTES if allow_extended_numpy_whitelist else _LEGACY_NUMPY_ATTRIBUTES


class _QuietSink(io.TextIOBase):
    def write(self, text: str) -> int:
        return len(text)

    def flush(self) -> None:
        return None


def capability_contract_dict(
    *,
    hook_name: str,
    hook_signature: Sequence[str],
    template_id: str,
    template_version: str,
    allow_extended_numpy_whitelist: bool = True,
) -> dict[str, Any]:
    """Machine-derived capability contract mirroring ``validate_hook_ast`` exactly."""
    return {
        "interface": f"{template_id}/{template_version}:{hook_name}",
        "entrypoint": hook_name,
        "parameters": list(hook_signature),
        "allowed_import_roots": sorted(_ALLOWED_IMPORT_ROOTS),
        "allowed_numpy_math_roots": sorted(_NP_MATH_ROOTS),
        "allowed_numpy_attributes": sorted(_numpy_attributes(allow_extended_numpy_whitelist)),
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
    allow_extended_numpy_whitelist: bool = True,
) -> tuple[list[GateFailure], list[GateFailure]]:
    """Run Gate 1 (AST capability whitelist) and Gate 2 (entrypoint/signature) on hook source.

    Returns ``(gate1_failures, gate2_failures)`` with exact AST line numbers and actionable fix hints.
    Uses the shared capability allowlists with the selected NumPy mode.
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
    numpy_attributes = _numpy_attributes(allow_extended_numpy_whitelist)
    allowed_attributes = numpy_attributes | _MATH_ATTRIBUTES
    numpy_aliases = _collect_np_math_aliases(tree, _NUMPY_ROOTS)
    math_aliases = _collect_np_math_aliases(tree, _MATH_ROOTS)

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
                numpy_receiver = root in _NUMPY_ROOTS or root in numpy_aliases
                math_receiver = root in _MATH_ROOTS or root in math_aliases
                if root is None:
                    receiver = node.value
                    while isinstance(receiver, ast.Attribute):
                        receiver = receiver.value
                    numpy_receiver = _expr_is_np_math_alias(receiver, _NUMPY_ROOTS, numpy_aliases)
                    math_receiver = _expr_is_np_math_alias(receiver, _MATH_ROOTS, math_aliases)
                if numpy_receiver or math_receiver:
                    attributes = numpy_attributes if numpy_receiver else _MATH_ATTRIBUTES
                    if node.attr not in attributes:
                        if node.attr == "ix_":
                            hint = "np.ix_ is outside the AST whitelist; use broadcast indexing like `distance_matrix[nodes[:, None], nodes[None, :]]` instead."
                        elif node.attr == "fill_diagonal":
                            hint = "np.fill_diagonal mutates arrays in-place and is outside the AST whitelist; use `np.where(np.eye(k, dtype=bool), val, sub)` instead."
                        else:
                            hint = "Use whitelisted vectorized numpy/math functions (e.g., np.where, np.clip, np.sqrt, np.exp)."
                        g1.append(GateFailure(
                            gate_id=1,
                            gate_name="ast_whitelist",
                            error_code="forbidden_attribute",
                            line_no=line_no,
                            symbol=f"{root}.{node.attr}",
                            detail=f"Attribute '{root}.{node.attr}' is not in the numpy/math whitelist.",
                            fix_hint=hint,
                        ))
                elif node.attr not in allowed_attributes and node.attr not in _CONTAINER_METHODS:
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
    allow_extended_numpy_whitelist: bool = True,
) -> Callable[..., Any]:
    """Validate and compile a hook function inside the restricted capability namespace."""
    g1, g2 = validate_hook_ast(
        code, hook_name=hook_name, expected_args=expected_args,
        allow_extended_numpy_whitelist=allow_extended_numpy_whitelist,
    )
    if g1:
        f = g1[0]
        raise ValueError(f"{f.error_code}:{f.symbol or f.detail}")
    if g2:
        f = g2[0]
        raise ValueError(f"{f.error_code}:{f.symbol or f.detail}")

    # Limit module access even through aliases whose values cannot be resolved by the AST walk.
    numpy = SimpleNamespace(**{
        name: getattr(np, name) for name in _numpy_attributes(allow_extended_numpy_whitelist)
        if hasattr(np, name)
    })
    math_module = SimpleNamespace(**{name: getattr(math, name) for name in _MATH_ATTRIBUTES})
    allowed_modules = {"numpy": numpy, "math": math_module}
    restricted_import = _make_restricted_import(set(_ALLOWED_IMPORT_ROOTS))
    restricted_builtins = dict(_SAFE_BUILTINS)
    namespace: dict[str, Any] = {
        "__builtins__": restricted_builtins,
        "np": numpy,
        "numpy": numpy,
        "math": math_module,
    }

    def import_module(name, globals=None, locals=None, fromlist=(), level=0):
        if globals is namespace and level == 0 and not fromlist and name in allowed_modules:
            return allowed_modules[name]
        return restricted_import(name, globals, locals, fromlist, level)

    restricted_builtins["__import__"] = import_module
    compiled = compile(ast.parse(code, mode="exec"), f"<m2_hook:{hook_name}>", "exec")
    sink = _QuietSink()
    with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
        exec(compiled, namespace, namespace)
    fn = namespace.get(hook_name)
    if not callable(fn):
        raise ValueError(f"missing_entrypoint:{hook_name}")
    return fn


def validate_hook_bundle(
    hook_specs: Sequence[HookSpec], hook_implementations: Mapping[str, str],
    *, allow_extended_numpy_whitelist: bool = True,
) -> tuple[list[GateFailure], list[GateFailure]]:
    """Validate isolated, named source units under the existing hook whitelist."""
    try:
        hook_bundle_metadata(hook_specs, hook_implementations)
    except ValueError as exc:
        return [], [GateFailure(2, "template_and_signature", str(exc), None, None,
                                "Source units must match the declared hook names.", "Supply every named hook once.")]
    gate1: list[GateFailure] = []
    gate2: list[GateFailure] = []
    for spec in hook_specs:
        source = hook_implementations[spec.name]
        first, second = validate_hook_ast(
            source, hook_name=spec.name, expected_args=spec.signature,
            allow_extended_numpy_whitelist=allow_extended_numpy_whitelist,
        )
        gate1.extend(first)
        gate2.extend(second)
        if first or second:
            continue
        body = ast.parse(source).body
        functions = [node for node in body if isinstance(node, ast.FunctionDef)]
        if (len(functions) != 1 or functions[0].decorator_list or functions[0].args.defaults
                or any(not isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef)) for node in body)):
            gate2.append(GateFailure(
                2, "template_and_signature", "invalid_hook_source_unit", None, spec.name,
                "Each named source unit must contain one undecorated hook with no defaults and optional imports.",
                "Move computation into the hook body.",
            ))
    return gate1, gate2


def compile_hook_bundle(
    hook_specs: Sequence[HookSpec], hook_implementations: Mapping[str, str],
    *, allow_extended_numpy_whitelist: bool = True,
) -> dict[str, Callable[..., Any]]:
    first, second = validate_hook_bundle(
        hook_specs, hook_implementations,
        allow_extended_numpy_whitelist=allow_extended_numpy_whitelist,
    )
    if first or second:
        failure = (first + second)[0]
        raise ValueError(f"{failure.error_code}:{failure.symbol or failure.detail}")
    return {
        spec.name: compile_hook_function(
            hook_implementations[spec.name], hook_name=spec.name, expected_args=spec.signature,
            allow_extended_numpy_whitelist=allow_extended_numpy_whitelist,
        )
        for spec in hook_specs
    }


def _checked_hook(fn: Callable[..., Any], spec: HookSpec) -> Callable[..., Any]:
    position = spec.signature.index(spec.output_shape_arg) if spec.output_shape_arg is not None else None

    def checked(*args: Any, **kwargs: Any) -> Any:
        raw = fn(*args, **kwargs)
        shape = ()
        if position is not None:
            argument = args[position] if position < len(args) else kwargs[spec.output_shape_arg]
            shape = (len(argument),)
        result = np.asarray(raw)
        if result.shape != shape or result.dtype.kind not in "iuf":
            raise ValueError(f"invalid_return:{spec.name}:expected_finite_numeric_shape={shape}")
        if not np.isfinite(result).all():
            raise ValueError(f"nonfinite_hook_scores:{spec.name}")
        return raw

    return checked


@dataclass(frozen=True)
class ProblemRuntimeAdapter:
    """Prepare trusted runner inputs and independently verify a typed solution.

    Verification supplies valid, verify_ms, the declared objective field and
    optional problem-specific fields. record_fields adds solution/trace fields.
    """

    problem_family: str
    prepare_inputs: Callable[[Mapping[str, Any], str], tuple[tuple[Any, ...], dict[str, Any]]]
    verify_solution: Callable[..., dict[str, Any]]
    failure_verification: Callable[[str | None, str | None, Mapping[str, Any], dict[str, Any]], dict[str, Any]]
    protocol_id: str = LEGACY_CVRP_PROTOCOL_ID
    objective_key: str = "objective"
    record_fields: Callable[[Any, Mapping[str, Any], Mapping[str, Any], bool], Mapping[str, Any]] | None = None


def _cvrp_prepare_inputs(instance: Mapping[str, Any], distance_convention: str) -> tuple[tuple[Any, ...], dict[str, Any]]:
    matrix, demands, capacity = prepare_instance_arrays(instance, distance_convention=distance_convention)
    return (matrix, demands, capacity), {
        "expected_matrix": matrix.copy(),
        "expected_demands": demands.copy(),
        "submitted_matrix": matrix,
        "submitted_demands": demands,
        "capacity": capacity,
    }


def _cvrp_verify_solution(
    instance: Mapping[str, Any],
    solution: Any,
    orig_refs: Mapping[str, Any],
    *,
    distance_convention: str,
    vehicle_limit_policy: str,
) -> dict[str, Any]:
    return verify_cvrp_solution(
        instance,
        solution,
        distance_convention=distance_convention,
        vehicle_limit_policy=vehicle_limit_policy,
        expected_matrix=orig_refs["expected_matrix"],
        submitted_matrix=orig_refs["submitted_matrix"],
        expected_demands=orig_refs["expected_demands"],
        submitted_demands=orig_refs["submitted_demands"],
    )


def _cvrp_failure_verification(
    error_code: str | None,
    error_detail: str | None,
    instance: Mapping[str, Any],
    orig_refs: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "valid": False,
        "error_code": error_code,
        "error_detail": error_detail,
        "tour_length": None,
        "route_count": 0,
        "route_loads": [],
        "route_distances": [],
        "capacity": orig_refs.get("capacity"),
        "max_utilization": None,
        "mean_utilization": None,
        "target_vehicles": instance.get("k_vehicles"),
        "within_vehicle_limit": None,
        "exact_vehicle_count": None,
        "vehicle_count_delta": None,
        "verify_ms": 0.0,
    }


def _cvrp_record_fields(
    routes: Any, verification: Mapping[str, Any], meta: Mapping[str, Any], capture: bool,
) -> dict[str, Any]:
    fields = {
        "routes": routes if verification["valid"] else [],
        "voluntary_early_return_count": int(meta.get("voluntary_early_return_count", 0)),
        "forced_capacity_return_count": int(meta.get("forced_capacity_return_count", 0)),
        "trace_steps": None,
        "merges_applied": int(meta.get("merges_applied", 0)),
        "candidate_pair_count": int(meta.get("candidate_pair_count", 0)),
    }
    if capture:
        fields.update(merge_sequence=meta.get("merge_sequence"), pre_postprocess_routes=meta.get("pre_postprocess_routes"))
        fields.update({key: meta[key] for key in ("first_ruin_set", "pre_recreate_routes") if key in meta})
    return fields


PROBLEM_ADAPTERS: dict[str | tuple[str, str], ProblemRuntimeAdapter] = {
    "cvrp": ProblemRuntimeAdapter(
        problem_family="cvrp",
        prepare_inputs=_cvrp_prepare_inputs,
        verify_solution=_cvrp_verify_solution,
        failure_verification=_cvrp_failure_verification,
        objective_key="tour_length",
        record_fields=_cvrp_record_fields,
    ),
}


def register_problem_adapter(adapter: ProblemRuntimeAdapter) -> None:
    key = (adapter.problem_family, adapter.protocol_id)
    legacy = PROBLEM_ADAPTERS.get(adapter.problem_family)
    if key in PROBLEM_ADAPTERS or (legacy is not None and legacy.protocol_id == adapter.protocol_id):
        raise ValueError(f"duplicate_problem_adapter:{key}")
    if not adapter.problem_family.strip() or not adapter.protocol_id.strip():
        raise ValueError("empty_problem_adapter_identity")
    PROBLEM_ADAPTERS[key] = adapter


def resolve_problem_adapter(
    template: TemplateSpec, *, problem_family: str | None = None, protocol_id: str | None = None,
) -> ProblemRuntimeAdapter:
    expected = template.effective_protocol_id
    if problem_family is not None and problem_family != template.problem_family:
        raise ValueError(f"problem_family_mismatch:{problem_family}!={template.problem_family}")
    if protocol_id is not None and protocol_id != expected:
        raise ValueError(f"protocol_id_mismatch:{protocol_id}!={expected}")
    adapter = PROBLEM_ADAPTERS.get((template.problem_family, expected))
    if adapter is None:
        legacy = PROBLEM_ADAPTERS.get(template.problem_family)
        if legacy is not None and legacy.protocol_id == expected:
            return legacy
        raise ValueError(f"unsupported_problem_protocol:{template.problem_family}/{expected}")
    return adapter


def derive_outer_timeout_s(
    instance_count: int, solve_deadline_ms: float | None, *, minimum_s: float = 20.0,
) -> float:
    """Budget a full serial batch plus worker startup, verification, and IPC."""
    if instance_count < 0 or not math.isfinite(minimum_s) or minimum_s <= 0:
        raise ValueError("invalid_outer_timeout")
    if solve_deadline_ms is None:
        return minimum_s
    if isinstance(solve_deadline_ms, bool) or not math.isfinite(solve_deadline_ms) or solve_deadline_ms <= 0:
        raise ValueError("invalid_solve_deadline")
    return max(minimum_s, 3.0 + 1.25 * instance_count * solve_deadline_ms / 1000.0)


def _timed_outcome_fields(
    solve_ms: float | None,
    budget_ms: float,
    budget_exhausted: bool,
    returned_objective: float | None = None,
    returned_exact_k: bool = False,
    incumbents: Mapping[str, tuple[float, float]] | None = None,
) -> dict[str, Any]:
    """Project verified deadline evidence without emitting route snapshots."""
    from .timed_cvrp import TIMED_CVRP_PROTOCOL, TIMED_CVRP_SOURCE_SHA256

    returned = (
        returned_objective is not None and solve_ms is not None
        and solve_ms <= budget_ms and not budget_exhausted
    )
    outcome = {
        "timed_incumbent_protocol": TIMED_CVRP_PROTOCOL,
        "timed_incumbent_source_sha256": TIMED_CVRP_SOURCE_SHA256,
        "solve_censored": budget_exhausted or (solve_ms is not None and solve_ms > budget_ms),
        "deadline_overrun_ms": max(0.0, solve_ms - budget_ms) if solve_ms is not None else None,
    }
    for fleet_suffix in ("", "_exact_k"):
        fleet_returned = returned and (not fleet_suffix or returned_exact_k)
        incumbent = None if incumbents is None else incumbents.get(fleet_suffix)
        if fleet_returned and (incumbent is None or returned_objective < incumbent[0]):
            incumbent = (returned_objective, solve_ms)
        outcome[f"returned_before_deadline{fleet_suffix}"] = fleet_returned
        outcome[f"returned_before_deadline{fleet_suffix}_objective"] = returned_objective if fleet_returned else None
        outcome[f"feasible_before_deadline{fleet_suffix}"] = incumbent is not None
        outcome[f"feasible_before_deadline{fleet_suffix}_objective"] = incumbent[0] if incumbent else None
        outcome[f"feasible_before_deadline{fleet_suffix}_ms"] = incumbent[1] if incumbent else None
    return outcome


class _TimedCvrpIncumbents:
    """Keep a candidate snapshot per fleet and verify after the solve clock stops."""

    def __init__(
        self, start_s: float, budget_ms: float, distance_matrix: np.ndarray, target_k: int | None,
        *, enforce_fleet_cap: bool,
    ) -> None:
        self.start_s = start_s
        self.budget_ms = budget_ms
        self.distance_matrix = distance_matrix
        self.target_k = target_k
        self.enforce_fleet_cap = enforce_fleet_cap
        self.candidates: dict[str, tuple[float, float, Sequence[Sequence[int]]]] = {}

    def record(
        self, routes: Collection[Sequence[int]], objective_hint: float | None = None,
        *, stable_routes: bool = False,
    ) -> None:
        elapsed_ms = (time.perf_counter() - self.start_s) * 1000.0
        if elapsed_ms > self.budget_ms or not routes:
            return
        count = len(routes)
        if self.enforce_fleet_cap and self.target_k is not None and count > self.target_k:
            return
        snapshot: Sequence[Sequence[int]] | None = None
        if objective_hint is None:
            snapshot = normalize_routes(tuple(routes))
            objective_hint = float(sum(
                self.distance_matrix[left, right]
                for route in snapshot
                for left, right in zip(route, route[1:])
            ))
        applicable = ("", "_exact_k") if count == self.target_k else ("",)
        for fleet_suffix in applicable:
            current = self.candidates.get(fleet_suffix)
            if current is None or objective_hint < current[0]:
                if snapshot is None:
                    # Merge steps replace route lists. Their prior lists can be
                    # borrowed and normalized after the solve clock stops.
                    snapshot = tuple(routes) if stable_routes else normalize_routes(tuple(routes))
                self.candidates[fleet_suffix] = (objective_hint, elapsed_ms, snapshot)

    def verified(
        self,
        instance: Mapping[str, Any],
        orig_refs: Mapping[str, Any],
        *,
        distance_convention: str,
        vehicle_limit_policy: str,
    ) -> dict[str, tuple[float, float]]:
        results: dict[str, tuple[float, float]] = {}
        verified_snapshots: dict[int, dict[str, Any]] = {}
        for suffix, (_, elapsed_ms, routes) in self.candidates.items():
            snapshot_id = id(routes)
            if snapshot_id not in verified_snapshots:
                verified_snapshots[snapshot_id] = _cvrp_verify_solution(
                    instance, normalize_routes(routes), orig_refs,
                    distance_convention=distance_convention, vehicle_limit_policy=vehicle_limit_policy,
                )
            evidence = verified_snapshots[snapshot_id]
            if evidence["valid"] and (suffix != "_exact_k" or evidence["exact_vehicle_count"] is True):
                results[suffix] = (float(evidence["tour_length"]), elapsed_ms)
        return results


def evaluate_hook_on_instance_inprocess(
    *,
    template_id: str,
    template_version: str,
    hook_fn: Callable[..., Any] | Mapping[str, Callable[..., Any]],
    instance: Mapping[str, Any],
    postprocess_mode: str = "none",
    template_options: Mapping[str, Any] | None = None,
    distance_convention: str = "euc_2d_float",
    vehicle_limit_policy: str = "unconstrained",
    time_budget_ms: float | None = 500.0,
    capture_merge_sequence: bool = False,
    problem_family: str | None = None,
    protocol_id: str | None = None,
    solve_deadline_ms: float | None = None,
    strict_hook_outputs: bool | None = None,
    capture_timed_incumbents: bool = False,
) -> dict[str, Any]:
    """Run one registered template + compiled hook on one instance via ``PROBLEM_ADAPTERS``."""
    tpl = get_template_spec(template_id, template_version)
    adapter = resolve_problem_adapter(tpl, problem_family=problem_family, protocol_id=protocol_id)
    if "protocol_id" in instance and instance["protocol_id"] != adapter.protocol_id:
        raise ValueError("protocol_id_mismatch:instance")
    if solve_deadline_ms is not None:
        time_budget_ms = solve_deadline_ms
    derive_outer_timeout_s(1, time_budget_ms)
    runner = tpl.runner
    if capture_timed_incumbents:
        from .timed_cvrp import TIMED_CVRP_RUNNERS

        timed_runner = TIMED_CVRP_RUNNERS.get((template_id, template_version))
        if adapter.problem_family != "cvrp" or timed_runner is None or time_budget_ms is None:
            raise ValueError("unsupported_timed_incumbent_evaluator")
        runner = timed_runner
    specs = tpl.effective_hook_specs
    if isinstance(hook_fn, Mapping):
        if set(hook_fn) != {spec.name for spec in specs}:
            raise ValueError("hook_bundle_names_mismatch")
        hooks = hook_fn
    elif len(specs) == 1:
        hooks = {specs[0].name: hook_fn}
    else:
        raise ValueError("hook_bundle_required")
    strict = bool(tpl.hook_specs or tpl.protocol_id) if strict_hook_outputs is None else strict_hook_outputs
    if strict:
        hooks = {spec.name: _checked_hook(hooks[spec.name], spec) for spec in specs}
    runner_hook = hooks[specs[0].name] if len(specs) == 1 else hooks

    t_pre0 = time.perf_counter()
    solver_args, orig_refs = adapter.prepare_inputs(instance, distance_convention)
    preprocess_ms = (time.perf_counter() - t_pre0) * 1000.0

    t_solve0 = time.perf_counter()
    status = "ok"
    error_code: str | None = None
    error_detail: str | None = None
    solution: Any = None
    meta: dict[str, Any] = {}
    sink = _QuietSink()
    incumbents = None
    incumbent_kwargs = {}
    if capture_timed_incumbents:
        target_k = instance.get("k_vehicles")
        if target_k is None:
            target_k = instance.get("max_vehicles")
        incumbents = _TimedCvrpIncumbents(
            t_solve0, time_budget_ms, solver_args[0], int(target_k) if target_k is not None else None,
            enforce_fleet_cap=vehicle_limit_policy == "strict_max_vehicles",
        )
        incumbent_kwargs["record_incumbent"] = incumbents.record
    try:
        with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink), np.errstate(all="ignore"):
            solution, meta = runner(
                *solver_args,
                runner_hook,
                postprocess_mode=postprocess_mode,
                time_budget_ms=time_budget_ms,
                template_options=template_options,
                capture_merge_sequence=capture_merge_sequence,
                **incumbent_kwargs,
            )
    except Exception as exc:
        status = "error"
        msg = str(exc)
        if msg.startswith("candidate_mutated_input") or "read-only" in msg or "WRITEABLE flag" in msg:
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
        verification = adapter.verify_solution(
            instance,
            solution,
            orig_refs,
            distance_convention=distance_convention,
            vehicle_limit_policy=vehicle_limit_policy,
        )
        if not verification["valid"]:
            status = "infeasible"
            error_code = verification.get("error_code")
            error_detail = verification.get("error_detail")
    else:
        verification = adapter.failure_verification(error_code, error_detail, instance, orig_refs)

    ref_obj = instance.get("reference_objective")
    ref_val = float(ref_obj) if isinstance(ref_obj, (int, float)) and math.isfinite(float(ref_obj)) and float(ref_obj) > 0 else None
    valid = bool(verification["valid"])
    raw_objective = verification.get(adapter.objective_key) if valid else None
    objective = None
    if valid:
        if raw_objective is None or isinstance(raw_objective, (bool, np.bool_)):
            valid, status, error_code = False, "error", "missing_objective"
        elif not math.isfinite(float(raw_objective)):
            valid, status, error_code = False, "error", "nonfinite_objective"
        else:
            objective = float(raw_objective)
    if not valid and verification["valid"]:
        verification = adapter.failure_verification(error_code, error_detail, instance, orig_refs)
    rel_gap = round((objective - ref_val) / ref_val, 6) if objective is not None and ref_val is not None else None
    stop_reason = meta.get("stop_reason")
    # The v1 templates use this bit for both iteration and wall-clock limits.
    budget_exhausted = bool(meta.get("budget_exhausted", False)) and stop_reason != "max_passes"
    outcome_class = classify_outcome(
        valid=valid,
        status=status,
        budget_exhausted=budget_exhausted,
    )

    fields = adapter.record_fields(solution, verification, meta, capture_merge_sequence) if adapter.record_fields else {}
    out: dict[str, Any] = {
        **verification,
        **fields,
        "instance_id": str(instance.get("instance_id", "")),
        "problem_family": tpl.problem_family,
        "protocol_id": adapter.protocol_id,
        "objective": objective,
        "completed": outcome_class == OUTCOME_COMPLETED,
        "status": status,
        "outcome_class": outcome_class,
        "valid": valid,
        "error_code": verification.get("error_code") or error_code,
        "error_detail": verification.get("error_detail") or error_detail,
        "reference_objective": ref_val,
        "reference_kind": instance.get("reference_kind"),
        "rel_gap": rel_gap,
        "preprocess_ms": round(preprocess_ms, 4),
        "candidate_gen_ms": float(meta.get("candidate_gen_ms", 0.0)),
        "hook_ms": float(meta.get("hook_ms", 0.0)),
        "merge_ms": float(meta.get("merge_ms", 0.0)),
        "postprocess_ms": float(meta.get("postprocess_ms", 0.0)),
        "solve_ms": round(solve_ms, 4),
        "verify_ms": float(verification.get("verify_ms", 0.0)),
        "budget_exhausted": budget_exhausted,
        "timeout_kind": "solve_deadline" if budget_exhausted else None,
        "stop_reason": str(meta.get("stop_reason", "error" if status != "ok" else "completed")),
        "hook_call_count": int(meta.get("hook_call_count", 0)),
        "template_source_sha256": tpl.template_source_sha256,
    }
    if "first_feasible_ms" in meta:
        out["first_feasible_ms"] = meta["first_feasible_ms"]
    if "anytime_curve" in meta:
        out["anytime_curve"] = meta["anytime_curve"]
    if "iterations_completed" in meta:
        out["iterations_completed"] = int(meta["iterations_completed"])
    if incumbents is not None:
        started_verify = time.perf_counter()
        evidence = incumbents.verified(
            instance, orig_refs,
            distance_convention=distance_convention, vehicle_limit_policy=vehicle_limit_policy,
        )
        out.update(_timed_outcome_fields(
            solve_ms, time_budget_ms, budget_exhausted, objective,
            verification.get("exact_vehicle_count") is True, evidence,
        ))
        out["verify_ms"] = round(out["verify_ms"] + (time.perf_counter() - started_verify) * 1000.0, 4)
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
        hook_code: str | None = None,
        instances: Sequence[Mapping[str, Any]],
        postprocess_mode: str = "none",
        template_options: Mapping[str, Any] | None = None,
        distance_convention: str = "euc_2d_float",
        vehicle_limit_policy: str = "unconstrained",
        instance_time_budget_ms: float | None = 500.0,
        capture_merge_sequence: bool = False,
        hook_implementations: Mapping[str, str] | None = None,
        problem_family: str | None = None,
        protocol_id: str | None = None,
        solve_deadline_ms: float | None = None,
        outer_timeout_s: float | None = None,
        strict_hook_outputs: bool | None = None,
        allow_extended_numpy_whitelist: bool = True,
        enable_degenerate_constant_screen: bool = False,
        fresh_hooks_per_instance: bool = False,
    ) -> dict[str, Any]:
        """Evaluate a hook across ``instances`` in a dedicated subprocess with hard kill on timeout."""
        budget = solve_deadline_ms if solve_deadline_ms is not None else instance_time_budget_ms
        timeout = derive_outer_timeout_s(
            len(instances), budget, minimum_s=self.candidate_timeout_s if outer_timeout_s is None else outer_timeout_s,
        )
        request = {
            "template_id": template_id,
            "template_version": template_version,
            "postprocess_mode": postprocess_mode,
            "template_options": dict(template_options or {}),
            "hook_code": hook_code,
            "instances": [dict(inst) for inst in instances],
            "distance_convention": distance_convention,
            "vehicle_limit_policy": vehicle_limit_policy,
            "solve_deadline_ms": budget,
            "capture_merge_sequence": bool(capture_merge_sequence),
            "allow_extended_numpy_whitelist": allow_extended_numpy_whitelist,
            "enable_degenerate_constant_screen": enable_degenerate_constant_screen,
            "parent_pid": os.getpid(),
        }
        if fresh_hooks_per_instance:
            request["fresh_hooks_per_instance"] = fresh_hooks_per_instance
        if hook_implementations is not None:
            request["hook_implementations"] = dict(hook_implementations)
        if problem_family is not None:
            request["problem_family"] = problem_family
        if protocol_id is not None:
            request["protocol_id"] = protocol_id
        if strict_hook_outputs is not None:
            request["strict_hook_outputs"] = strict_hook_outputs
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
            stdout, stderr = proc.communicate(input=payload_bytes, timeout=timeout)
        except subprocess.TimeoutExpired:
            kill_process_tree(proc)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            return {
                "valid": False,
                "objective": None,
                "error_code": "candidate_timeout",
                "error_detail": f"Subprocess exceeded outer_timeout_s={timeout}",
                "timeout_kind": "outer_worker",
                "outer_timeout_s": timeout,
                "failures": [
                    GateFailure(
                        gate_id=5,
                        gate_name="budget_and_timeout",
                        error_code="candidate_timeout",
                        line_no=None,
                        symbol=None,
                        detail=f"Candidate subprocess killed after {timeout:.2f}s outer timeout.",
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
        resp["outer_timeout_s"] = timeout
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
    protocol_id: str | None = None,
    solve_deadline_ms: float | None = None,
    outer_timeout_s: float | None = None,
    strict_hook_outputs: bool | None = None,
    enforce_wall_deadline: bool = True,
    capture_timed_incumbents: bool = False,
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
    adapter = resolve_problem_adapter(
        tpl, problem_family=frozen_solver.problem_family, protocol_id=frozen_solver.protocol_id,
    )
    if tpl.protocol_id is not None and frozen_solver.protocol_id != tpl.protocol_id:
        raise ValueError("frozen_solver_protocol_id_mismatch")
    if protocol_id is not None and protocol_id != adapter.protocol_id:
        raise ValueError("protocol_id_mismatch:frozen_solver")
    if "protocol_id" in instance and instance["protocol_id"] != adapter.protocol_id:
        raise ValueError("protocol_id_mismatch:instance")
    if frozen_solver.hook_specs != tpl.hook_specs:
        raise ValueError("frozen_solver_hook_contract_mismatch")
    manifest = frozen_solver.to_dict()
    budget = time_budget_ms if time_budget_ms is not None else frozen_solver.default_budget_ms
    if solve_deadline_ms is not None:
        budget = solve_deadline_ms
    if capture_timed_incumbents:
        from .timed_cvrp import TIMED_CVRP_PROTOCOL, TIMED_CVRP_RUNNERS, TIMED_CVRP_SOURCE_SHA256

        if (
            not enforce_wall_deadline or budget is None or adapter.problem_family != "cvrp"
            or (frozen_solver.template_id, frozen_solver.template_version) not in TIMED_CVRP_RUNNERS
        ):
            raise ValueError("unsupported_timed_incumbent_evaluator")
    worker_deadline_ms = budget if enforce_wall_deadline else None
    default_min_s = 5.0 if enforce_wall_deadline else max(15.0, 4.0 * float(budget or 500.0) / 1000.0 + 3.0)
    timeout = derive_outer_timeout_s(1, budget, minimum_s=default_min_s if outer_timeout_s is None else outer_timeout_s)
    started = time.perf_counter()
    request = {
        "template_id": frozen_solver.template_id,
        "template_version": frozen_solver.template_version,
        "hook_code": frozen_solver.hook_code,
        "hook_implementations": manifest.get("hook_implementations"),
        "problem_family": adapter.problem_family,
        "protocol_id": adapter.protocol_id,
        "strict_hook_outputs": strict_hook_outputs,
        "instances": [dict(instance)],
        "postprocess_mode": frozen_solver.postprocess_mode,
        "template_options": dict(frozen_solver.template_options),
        "allow_extended_numpy_whitelist": frozen_solver.template_options.get("allow_extended_numpy_whitelist", True),
        "distance_convention": distance_convention,
        "vehicle_limit_policy": vehicle_limit_policy,
        "solve_deadline_ms": worker_deadline_ms,
        "capture_merge_sequence": capture_merge_sequence,
        "parent_pid": os.getpid(),
    }
    if capture_timed_incumbents:
        request["capture_timed_incumbents"] = True
    response = _FROZEN_WORKER.call(request, timeout_s=timeout)
    records = response.get("records")
    if records:
        if response.get("template_source_sha256") != frozen_solver.template_source_sha256:
            raise ValueError(f"worker_template_source_sha256_mismatch:{frozen_solver.solver_id}")
        if records[0].get("protocol_id") != adapter.protocol_id:
            raise ValueError("worker_protocol_id_mismatch")
        if frozen_solver.hook_specs and response.get("bundle_hash") != frozen_solver.bundle_hash:
            raise ValueError("worker_bundle_hash_mismatch")
        rec0 = records[0]
        if capture_timed_incumbents and (
            rec0.get("timed_incumbent_protocol") != TIMED_CVRP_PROTOCOL
            or rec0.get("timed_incumbent_source_sha256") != TIMED_CVRP_SOURCE_SHA256
        ):
            raise ValueError("worker_timed_incumbent_protocol_mismatch")
        if not enforce_wall_deadline and budget is not None and float(rec0.get("solve_ms") or 0.0) > float(budget):
            rec0["budget_exhausted"] = True
            rec0["timeout_kind"] = "solve_deadline"
        return rec0
    code = response.get("error_code") or "worker_protocol"
    status = "timeout" if code == "candidate_timeout" else "error"
    failure = {
        "instance_id": str(instance.get("instance_id", "")),
        "problem_family": adapter.problem_family,
        "protocol_id": adapter.protocol_id,
        "objective": None,
        "completed": False,
        "status": status,
        "valid": False,
        "outcome_class": classify_outcome(valid=False, status=status, budget_exhausted=status == "timeout"),
        "error_code": code,
        "error_detail": response.get("error_detail"),
        "template_source_sha256": frozen_solver.template_source_sha256,
        "budget_exhausted": status == "timeout",
        "timeout_kind": "outer_worker" if status == "timeout" else None,
        "reference_objective": instance.get("reference_objective"),
        "reference_kind": instance.get("reference_kind"),
        "rel_gap": None,
        "preprocess_ms": 0.0,
        "solve_ms": round((time.perf_counter() - started) * 1000.0, 4),
        "verify_ms": 0.0,
    }
    if adapter.problem_family == "cvrp":
        if capture_timed_incumbents:
            failure.update(_timed_outcome_fields(None, budget, status == "timeout"))
            failure["solve_ms"] = None
        legacy = _cvrp_failure_verification(code, response.get("error_detail"), instance, {})
        legacy.pop("capacity")
        legacy["target_vehicles"] = instance.get("k_vehicles", instance.get("max_vehicles"))
        return {**legacy, "routes": [], **failure}
    return failure
