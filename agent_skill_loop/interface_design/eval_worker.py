"""Dedicated JSON stdin/stdout subprocess worker for Milestone 2 interface templates & hooks.

Enforces parent-pid watchdog cancellation (safe on Windows) and runs the exact same
AST capability whitelist, registered template, and M1 ``verify_cvrp_solution`` verifier
for both ``InterfaceValidator`` and ``DynamicInterfaceProblem``.
"""

from __future__ import annotations

import json
import sys
import threading
import time
from typing import Any

from agent_skill_loop.eval_worker import _watch_parent

from .contracts import GateFailure
from .runtime import compile_hook_function, evaluate_hook_on_instance_inprocess, validate_hook_ast
from .templates import get_template_spec


def _handle_request(request: dict[str, Any]) -> dict[str, Any]:
    t0 = time.perf_counter()
    template_id = str(request["template_id"])
    template_version = str(request["template_version"])
    postprocess_mode = str(request.get("postprocess_mode", "none"))
    template_options = dict(request.get("template_options") or {})
    hook_code = str(request["hook_code"])
    instances = list(request.get("instances") or [])
    distance_convention = str(request.get("distance_convention", "euc_2d_float"))
    vehicle_limit_policy = str(request.get("vehicle_limit_policy", "unconstrained"))
    time_budget_ms = request.get("time_budget_ms", 500.0)
    time_budget_ms = float(time_budget_ms) if time_budget_ms is not None else None
    capture_merge_sequence = bool(request.get("capture_merge_sequence", False))

    try:
        tpl = get_template_spec(template_id, template_version)
    except KeyError as exc:
        f = GateFailure(
            gate_id=2,
            gate_name="template_and_signature",
            error_code="unknown_template",
            line_no=None,
            symbol=f"{template_id}/{template_version}",
            detail=str(exc),
            fix_hint="Use a registered template_id/template_version from TEMPLATE_REGISTRY.",
        )
        return {
            "valid": False,
            "objective": None,
            "error_code": "unknown_template",
            "error_detail": str(exc),
            "failures": [f.as_dict()],
            "records": [],
            "inner_compute_ms": round((time.perf_counter() - t0) * 1000.0, 4),
        }

    g1, g2 = validate_hook_ast(hook_code, hook_name=tpl.hook_name, expected_args=tpl.hook_signature)
    if g1 or g2:
        all_f = [*g1, *g2]
        return {
            "valid": False,
            "objective": None,
            "error_code": all_f[0].error_code,
            "error_detail": all_f[0].detail,
            "failures": [f.as_dict() for f in all_f],
            "records": [],
            "template_source_sha256": tpl.template_source_sha256,
            "inner_compute_ms": round((time.perf_counter() - t0) * 1000.0, 4),
        }

    try:
        hook_fn = compile_hook_function(
            hook_code,
            hook_name=tpl.hook_name,
            expected_args=tpl.hook_signature,
        )
    except Exception as exc:
        return {
            "valid": False,
            "objective": None,
            "error_code": "compile_error",
            "error_detail": f"{type(exc).__name__}: {exc}",
            "failures": [],
            "records": [],
            "template_source_sha256": tpl.template_source_sha256,
            "inner_compute_ms": round((time.perf_counter() - t0) * 1000.0, 4),
        }

    records: list[dict[str, Any]] = []
    objectives: list[float] = []
    all_valid = True
    first_error_code: str | None = None
    first_error_detail: str | None = None

    for inst in instances:
        rec = evaluate_hook_on_instance_inprocess(
            template_id=template_id,
            template_version=template_version,
            hook_fn=hook_fn,
            instance=inst,
            postprocess_mode=postprocess_mode,
            template_options=template_options,
            distance_convention=distance_convention,
            vehicle_limit_policy=vehicle_limit_policy,
            time_budget_ms=time_budget_ms,
            capture_merge_sequence=capture_merge_sequence,
        )
        records.append(rec)
        if rec["valid"] and rec["tour_length"] is not None:
            objectives.append(float(rec["tour_length"]))
        else:
            all_valid = False
            if first_error_code is None:
                first_error_code = rec.get("error_code") or "infeasible"
                first_error_detail = rec.get("error_detail")

    mean_obj = (sum(objectives) / len(objectives)) if (all_valid and objectives) else None
    inner_ms = (time.perf_counter() - t0) * 1000.0
    return {
        "valid": bool(all_valid and bool(objectives)),
        "objective": round(mean_obj, 6) if mean_obj is not None else None,
        "instance_objectives": [round(x, 6) for x in objectives],
        "error_code": first_error_code,
        "error_detail": first_error_detail,
        "failures": [],
        "records": records,
        "template_source_sha256": tpl.template_source_sha256,
        "inner_compute_ms": round(inner_ms, 4),
    }


def _process_request(raw: bytes, *, watch_parent: bool) -> dict[str, Any]:
    try:
        request = json.loads(raw.decode("utf-8"))
        if not isinstance(request, dict):
            raise ValueError("request_must_be_object")
        parent_pid = request.get("parent_pid")
        if watch_parent and isinstance(parent_pid, int):
            threading.Thread(
                target=_watch_parent,
                args=(parent_pid,),
                daemon=True,
                name="m2-parent-watch",
            ).start()
        result = _handle_request(request)
    except Exception as exc:
        result = {
            "valid": False,
            "objective": None,
            "error_code": "worker_protocol",
            "error_detail": f"{type(exc).__name__}: {exc}",
            "failures": [],
            "records": [],
            "inner_compute_ms": 0.0,
        }
    return result


def main() -> int:
    streaming = sys.argv[1:] == ["--stream"]
    requests = sys.stdin.buffer if streaming else (sys.stdin.buffer.read(),)
    for index, raw in enumerate(requests):
        result = _process_request(raw, watch_parent=index == 0)
        sys.stdout.write(json.dumps(result, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
