"""Subprocess sandbox worker executing AST-whitelisted diagnostic Python/NumPy code.

Runs with stripped zero-key ``_worker_environment``, strictly read-only
``cvrp_dev_hetero_24`` inputs, and hard timeout protection.
"""

from __future__ import annotations

import ast
import copy
import json
import math
import sys
import threading
import time
from typing import Any, Mapping, Sequence

import numpy as np

from agent_skill_loop.benchmark.catalog import load_profile_suite
from agent_skill_loop.cvrp_workbench.protocol import compute_distance_matrix
from agent_skill_loop.cvrp_workbench.solvers import evaluate_algorithm_on_instance
from agent_skill_loop.cvrp_workbench.suites import BENCHMARK_ID
from agent_skill_loop.eval_worker import _watch_parent
from agent_skill_loop.interface_design.blind_commitment import assert_suite_allowed_for_interactive_role
from agent_skill_loop.interface_design.diagnostics import analyze_instance_records
from agent_skill_loop.interface_design.runtime import compile_hook_function, evaluate_hook_on_instance_inprocess
from agent_skill_loop.interface_design.templates import get_template_spec

_FORBIDDEN_IMPORTS = frozenset({
    "os", "sys", "subprocess", "socket", "pathlib", "shutil", "ctypes",
    "importlib", "builtins", "io", "sqlite3", "pickle", "urllib", "http",
    "threading", "multiprocessing", "tempfile", "glob", "signal",
})
_ALLOWED_IMPORTS = frozenset({"numpy", "math"})
_FORBIDDEN_CALLS = frozenset({
    "open", "eval", "exec", "compile", "__import__", "getattr", "setattr",
    "delattr", "globals", "locals", "vars", "dir", "input", "breakpoint",
    "exit", "quit", "memoryview",
})
_FORBIDDEN_STRINGS = ("cvrp_m2_blind_120", "cvrp_m3_blind_120", "cvrp_m32_blind_120", "cvrp_select_multiscale_64", ".agent_skill_custody", ".secrets")


def validate_sandbox_ast(script: str) -> None:
    """Validate script AST before execution inside isolated subprocess."""
    lower = script.lower()
    for token in _FORBIDDEN_STRINGS:
        if token in lower:
            raise ValueError(f"forbidden_suite_or_path_reference:{token}")
    tree = ast.parse(script)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root in _FORBIDDEN_IMPORTS or root not in _ALLOWED_IMPORTS:
                    raise ValueError(f"forbidden_import:{alias.name}")
        elif isinstance(node, ast.ImportFrom):
            mod = (node.module or "").split(".", 1)[0]
            if mod in _FORBIDDEN_IMPORTS or mod not in _ALLOWED_IMPORTS:
                raise ValueError(f"forbidden_import:{node.module}")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in _FORBIDDEN_CALLS:
                raise ValueError(f"forbidden_builtin_call:{node.func.id}")
        elif isinstance(node, ast.Name):
            if node.id in _FORBIDDEN_CALLS or node.id.startswith("__"):
                raise ValueError(f"forbidden_name:{node.id}")
        elif isinstance(node, ast.Attribute):
            if node.attr.startswith("__"):
                raise ValueError(f"forbidden_dunder_attribute:{node.attr}")


def _safe_load_dev_suite(suite_id: str = "cvrp_dev_hetero_24", max_instances: int | None = None) -> list[dict[str, Any]]:
    assert_suite_allowed_for_interactive_role(suite_id, role="interactive_sandbox")
    suite = load_profile_suite(BENCHMARK_ID, suite_id, split="dev_train")
    assert_suite_allowed_for_interactive_role(suite_id, suite, role="interactive_sandbox")
    insts = list(suite["instances"])
    if max_instances is not None:
        insts = insts[: int(max_instances)]
    return copy.deepcopy(insts)


def _safe_eval_hook(
    code: str,
    template_id: str,
    instance: Mapping[str, Any],
    *,
    postprocess_mode: str = "none",
    time_budget_ms: float = 500.0,
) -> dict[str, Any]:
    tpl = get_template_spec(template_id, "v1")
    fn = compile_hook_function(code, hook_name=tpl.hook_name, expected_args=tpl.hook_signature)
    return evaluate_hook_on_instance_inprocess(
        template_id=template_id,
        template_version="v1",
        hook_fn=fn,
        instance=copy.deepcopy(dict(instance)),
        postprocess_mode=postprocess_mode,
        time_budget_ms=time_budget_ms,
    )


def _safe_eval_baseline(algorithm_id: str, instance: Mapping[str, Any], *, time_budget_ms: float = 500.0) -> dict[str, Any]:
    return evaluate_algorithm_on_instance(
        algorithm_id,
        copy.deepcopy(dict(instance)),
        distance_convention="euc_2d_float",
        vehicle_limit_policy="unconstrained",
        time_budget_ms=time_budget_ms,
        record_trace=False,
    )


def _scale_cvrp_instance(instance: Mapping[str, Any], s: float) -> dict[str, Any]:
    scaled = copy.deepcopy(dict(instance))
    scaled["depot"] = [float(x) * s for x in scaled["depot"]]
    scaled["customer_coordinates"] = [[float(x) * s for x in pt] for pt in scaled["customer_coordinates"]]
    return scaled


def scale_invariance_audit(
    code: str,
    template_id: str,
    instance: Mapping[str, Any],
    *,
    postprocess_mode: str = "none",
    scales: Sequence[float] = (1e-3, 1.0, 1e3),
    time_budget_ms: float = 500.0,
) -> dict[str, Any]:
    """Fast (<10ms typical) similarity-group scale audit across s in {1e-3, 1, 1e3}."""
    tpl = get_template_spec(template_id, "v1")
    fn = compile_hook_function(code, hook_name=tpl.hook_name, expected_args=tpl.hook_signature)
    by_scale: dict[str, dict[str, Any]] = {}
    normalized: list[float] = []
    for s in scales:
        s_val = float(s)
        scaled = _scale_cvrp_instance(instance, s_val)
        rec = evaluate_hook_on_instance_inprocess(
            template_id=template_id,
            template_version="v1",
            hook_fn=fn,
            instance=scaled,
            postprocess_mode=postprocess_mode,
            time_budget_ms=time_budget_ms,
        )
        obj = rec.get("tour_length")
        norm_obj = (float(obj) / s_val) if (rec.get("valid") and obj is not None) else None
        if norm_obj is not None:
            normalized.append(norm_obj)
        by_scale[str(s_val)] = {
            "valid": bool(rec.get("valid")),
            "tour_length": obj,
            "normalized_tour_length": round(norm_obj, 6) if norm_obj is not None else None,
            "route_count": rec.get("route_count"),
        }
    drift_pct = (
        round(100.0 * (max(normalized) - min(normalized)) / max(min(normalized), 1e-12), 4)
        if len(normalized) == len(scales) and normalized
        else None
    )
    return {
        "instance_id": instance.get("instance_id"),
        "scales": by_scale,
        "max_scale_drift_pct": drift_pct,
        "scale_invariant": bool(drift_pct is not None and drift_pct <= 0.05),
    }


def radial_share_stats(routes: Sequence[Sequence[int]], instance: Mapping[str, Any]) -> dict[str, Any]:
    """Lightweight (<1ms) online HRK radial-star fraction and capacity-slack helper."""
    demands = [0.0] + [float(d) for d in instance["demands"]]
    cap = float(instance["capacity"])
    mat = compute_distance_matrix(
        instance["depot"],
        instance["customer_coordinates"],
        distance_convention="euc_2d_float",
    )
    total_len = 0.0
    radial_len = 0.0
    loads: list[float] = []
    for r in routes:
        seq = [int(c) for c in r if int(c) != 0]
        if not seq:
            continue
        radial_len += float(mat[0, seq[0]]) + float(mat[seq[-1], 0])
        total_len += float(mat[0, seq[0]]) + float(mat[seq[-1], 0])
        for a, b in zip(seq[:-1], seq[1:]):
            total_len += float(mat[a, b])
        loads.append(sum(demands[c] for c in seq))
    sum_dem = sum(demands[1:])
    r_lb = (2.0 / max(cap, 1e-12)) * sum(demands[i] * float(mat[0, i]) for i in range(1, len(demands)))
    return {
        "route_count": len(loads),
        "total_length": round(total_len, 6),
        "radial_stem_length": round(radial_len, 6),
        "eta_rad": round(radial_len / max(total_len, 1e-12), 6),
        "hrk_radial_lower_bound": round(r_lb, 6),
        "mean_load_utilization": round((sum_dem / max(len(loads) * cap, 1e-12)), 6) if loads else 0.0,
    }


def _restricted_import(name: str, globals: Any = None, locals: Any = None, fromlist: Any = (), level: int = 0) -> Any:
    root = name.split(".", 1)[0]
    if root in _FORBIDDEN_IMPORTS or root not in _ALLOWED_IMPORTS:
        raise ImportError(f"forbidden_import:{name}")
    return __import__(name, globals, locals, fromlist, level)


def _execute_sandbox_script(script: str) -> dict[str, Any]:
    t0 = time.perf_counter()
    stdout_buf: list[str] = []

    def _safe_print(*args: Any, **kwargs: Any) -> None:
        sep = str(kwargs.get("sep", " "))
        stdout_buf.append(sep.join(str(a) for a in args))

    validate_sandbox_ast(script)
    safe_builtins = {
        "abs": abs, "all": all, "any": any, "bool": bool, "dict": dict,
        "enumerate": enumerate, "float": float, "int": int, "len": len,
        "list": list, "max": max, "min": min, "pow": pow, "range": range,
        "round": round, "set": set, "sorted": sorted, "str": str, "sum": sum,
        "tuple": tuple, "zip": zip, "Exception": Exception, "ValueError": ValueError,
        "print": _safe_print, "__import__": _restricted_import,
    }
    env: dict[str, Any] = {
        "__builtins__": safe_builtins,
        "np": np,
        "math": math,
        "load_dev_suite": _safe_load_dev_suite,
        "eval_hook": _safe_eval_hook,
        "eval_baseline": _safe_eval_baseline,
        "slice_stats": analyze_instance_records,
        "scale_invariance_audit": scale_invariance_audit,
        "radial_share_stats": radial_share_stats,
    }
    exec(compile(script, "<research_math_sandbox>", "exec"), env, env)
    result_val = env.get("RESULT", env.get("result"))
    return {
        "ok": True,
        "stdout": "\n".join(stdout_buf),
        "result": result_val,
        "elapsed_ms": round((time.perf_counter() - t0) * 1000.0, 4),
    }


def main() -> int:
    raw = sys.stdin.buffer.read()
    try:
        req = json.loads(raw.decode("utf-8"))
        parent_pid = req.get("parent_pid")
        if isinstance(parent_pid, int):
            threading.Thread(target=_watch_parent, args=(parent_pid,), daemon=True, name="sandbox-parent-watch").start()
        out = _execute_sandbox_script(str(req["script"]))
    except Exception as exc:
        out = {
            "ok": False,
            "error_code": type(exc).__name__,
            "error_detail": str(exc),
            "stdout": "",
            "result": None,
            "elapsed_ms": 0.0,
        }
    sys.stdout.write(json.dumps(out, ensure_ascii=False, default=str) + "\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
