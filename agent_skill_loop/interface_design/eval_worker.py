"""Dedicated JSON stdin/stdout subprocess worker for Milestone 2 interface templates & hooks.

Enforces parent-pid watchdog cancellation and runs the registered adapter and
template under the shared AST capability whitelist.
"""

from __future__ import annotations

import json
import sys
import threading
import time
from typing import Any, Mapping

from agent_skill_loop.eval_worker import _watch_parent

from .contracts import OUTCOME_TIMEOUT_OR_INFEASIBLE, GateFailure, hook_bundle_metadata
from .runtime import (
    compile_hook_bundle,
    compile_hook_function,
    derive_outer_timeout_s,
    evaluate_hook_on_instance_inprocess,
    resolve_problem_adapter,
    validate_hook_ast,
    validate_hook_bundle,
)
from .templates import get_template_spec


def _handle_request(request: dict[str, Any]) -> dict[str, Any]:
    t0 = time.perf_counter()
    template_id = str(request["template_id"])
    template_version = str(request["template_version"])
    postprocess_mode = str(request.get("postprocess_mode", "none"))
    template_options = dict(request.get("template_options") or {})
    hook_code = request.get("hook_code")
    implementations = request.get("hook_implementations")
    instances = list(request.get("instances") or [])
    distance_convention = str(request.get("distance_convention", "euc_2d_float"))
    vehicle_limit_policy = str(request.get("vehicle_limit_policy", "unconstrained"))
    time_budget_ms = request.get("solve_deadline_ms", request.get("time_budget_ms", 500.0))
    capture_merge_sequence = bool(request.get("capture_merge_sequence", False))
    strict = request.get("strict_hook_outputs")

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

    try:
        adapter = resolve_problem_adapter(
            tpl, problem_family=request.get("problem_family"), protocol_id=request.get("protocol_id"),
        )
        if any("protocol_id" in inst and inst["protocol_id"] != adapter.protocol_id for inst in instances):
            raise ValueError("protocol_id_mismatch:instance")
        derive_outer_timeout_s(len(instances), time_budget_ms)
        if strict is not None and not isinstance(strict, bool):
            raise ValueError("invalid_strict_hook_outputs")
        if postprocess_mode not in tpl.allowed_postprocess_modes:
            raise ValueError("unsupported_postprocess_mode")
        if implementations is not None:
            if not isinstance(implementations, Mapping):
                raise ValueError("invalid_hook_implementations")
            if hook_code is not None and hook_code != implementations.get(tpl.hook_name):
                raise ValueError("primary_hook_mismatch")
        elif len(tpl.effective_hook_specs) > 1:
            raise ValueError("hook_bundle_required")
        elif not isinstance(hook_code, str):
            raise ValueError("missing_hook_code")
    except (ValueError, TypeError) as exc:
        return {
            "valid": False, "objective": None, "records": [], "failures": [],
            "error_code": str(exc).partition(":")[0], "error_detail": str(exc),
        }

    specs = tpl.effective_hook_specs
    if tpl.hook_specs and implementations is None:
        implementations = {tpl.hook_name: hook_code}
    if implementations is None:
        g1, g2 = validate_hook_ast(hook_code, hook_name=tpl.hook_name, expected_args=tpl.hook_signature)
    else:
        g1, g2 = validate_hook_bundle(specs, implementations)
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
        if implementations is None:
            hook_fn = compile_hook_function(hook_code, hook_name=tpl.hook_name, expected_args=tpl.hook_signature)
        else:
            hook_fn = compile_hook_bundle(specs, implementations)
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
        try:
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
                protocol_id=adapter.protocol_id,
                strict_hook_outputs=strict,
            )
        except (ValueError, TypeError, KeyError) as exc:
            if tpl.protocol_id is None and not tpl.hook_specs:
                raise
            rec = {
                "instance_id": str(inst.get("instance_id", "")),
                "problem_family": adapter.problem_family,
                "protocol_id": adapter.protocol_id,
                "status": "error",
                "valid": False, "completed": False, "objective": None,
                "outcome_class": OUTCOME_TIMEOUT_OR_INFEASIBLE,
                "preprocess_ms": None, "solve_ms": None, "verify_ms": None,
                "error_code": "instance_evaluation_error", "error_detail": str(exc),
                "timeout_kind": None,
            }
        records.append(rec)
        if rec["valid"] and rec["objective"] is not None:
            objectives.append(float(rec["objective"]))
        else:
            all_valid = False
            if first_error_code is None:
                first_error_code = rec.get("error_code") or "infeasible"
                first_error_detail = rec.get("error_detail")

    mean_obj = (sum(objectives) / len(objectives)) if (all_valid and objectives) else None
    inner_ms = (time.perf_counter() - t0) * 1000.0
    return {
        "valid": bool(all_valid and bool(objectives)),
        "completed": bool(records) and all(rec["completed"] for rec in records),
        "protocol_id": adapter.protocol_id,
        "objective": round(mean_obj, 6) if mean_obj is not None else None,
        "instance_objectives": [round(x, 6) for x in objectives],
        "ordered_instance_objectives": [rec["objective"] for rec in records],
        "error_code": first_error_code,
        "error_detail": first_error_detail,
        "failures": [],
        "records": records,
        "template_source_sha256": tpl.template_source_sha256,
        "inner_compute_ms": round(inner_ms, 4),
        **(hook_bundle_metadata(specs, implementations) if implementations is not None else {}),
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
