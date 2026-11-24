"""Feasibility, causal sensitivity, and scale probes for the L3b template."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .contracts import LEGACY_CVRP_PROTOCOL_ID, GateFailure, InterfaceDesign
from .cvrp_l3b import L3B_TEMPLATE_KEY
from .templates import get_template_spec
from .validator import (
    GateProbeContext,
    GateProbeResult,
    ProblemGateProbeSpec,
    _build_gate5_n200_stress_instances,
    _default_gate3_instances,
    _default_gate5_instances,
    build_gate4_l3_6cust_instance,
    register_problem_gate_probe,
)


def _build_recreate_probe_instance() -> dict[str, Any]:
    """Two surviving routes each have room for customer 1 after baseline ruin."""
    return {
        "instance_id": "m32_l3b_gate4_recreate_two_routes",
        "size": 8,
        "depot": [0.5, 0.5],
        "customer_coordinates": [
            [0.02, 0.46], [0.04, 0.54], [0.22, 0.43], [0.25, 0.57],
            [0.98, 0.46], [0.96, 0.54], [0.78, 0.43], [0.75, 0.57],
        ],
        "demands": [2, 2, 3, 3, 2, 2, 3, 3],
        "capacity": 10,
    }


def _gate3_instances(_design: InterfaceDesign) -> Sequence[Mapping[str, Any]]:
    return _default_gate3_instances()


def _gate4(context: GateProbeContext) -> GateProbeResult:
    template = get_template_spec(*L3B_TEMPLATE_KEY)
    ruin, recreate = template.hook_specs
    baseline = template.baseline_implementations()
    ruin_fixture = build_gate4_l3_6cust_instance()
    recreate_fixture = _build_recreate_probe_instance()
    gate_name = "dual_action_causal_sensitivity"
    failures: list[GateFailure] = []

    def fail(code: str, hook_name: str | None, detail: str) -> None:
        failures.append(GateFailure(
            4, gate_name, code, None, hook_name, detail,
            "Return distinct finite priorities for competing feasible actions and use them to choose the first action.",
        ))

    def evaluate_preference(instance: Mapping[str, Any], name: str, expression: str) -> dict[str, Any]:
        signature = next(spec.signature for spec in template.hook_specs if spec.name == name)
        source = f"import numpy as np\n\ndef {name}({', '.join(signature)}):\n    return {expression}\n"
        response = context.evaluate(
            [instance], hook_implementations={**baseline, name: source}, capture_merge_sequence=True,
        )
        records = response.get("records") or []
        return _first_trace(records[0]) if response.get("valid") and len(records) == 1 else {}

    ruin_a = evaluate_preference(ruin_fixture, ruin.name, "np.array([4, 3, 2, 1, 0, 0])")
    ruin_b = evaluate_preference(ruin_fixture, ruin.name, "np.array([0, 0, 4, 3, 2, 1])")
    if (
        ruin_a.get("first_ruin_set") != [1, 2, 3, 4]
        or ruin_b.get("first_ruin_set") != [3, 4, 5, 6]
        or ruin_a.get("pre_postprocess_routes") == ruin_b.get("pre_postprocess_routes")
        or not (ruin_a.get("first_recreate_choice") and ruin_b.get("first_recreate_choice"))
    ):
        fail("hook_not_causally_effective", ruin.name, "Ruin preferences must change the first ruin set and routes.")

    recreate_a = evaluate_preference(
        recreate_fixture, recreate.name, "10.0 * (customer_idx == 1) + (target_route_idx == 0)",
    )
    recreate_b = evaluate_preference(
        recreate_fixture, recreate.name,
        "10.0 * (customer_idx == 1) + (target_route_idx == 1) + 0.5 * (insert_pos == 3)",
    )
    first_a = recreate_a.get("first_recreate_choice") or []
    first_b = recreate_b.get("first_recreate_choice") or []
    if (
        first_a[:2] != [1, 0] or first_b != [1, 1, 3]
        or recreate_a.get("first_ruin_set") != recreate_b.get("first_ruin_set")
        or recreate_a.get("pre_recreate_routes") != recreate_b.get("pre_recreate_routes")
    ):
        fail("hook_not_causally_effective", recreate.name, "Recreate preferences must send customer 1 to different routes.")

    # The controlled comparisons above exercise the dispatcher. Check both
    # submitted hooks on the same fixtures so a constant hook cannot pass.
    candidate = context.evaluate([ruin_fixture, recreate_fixture], capture_merge_sequence=True)
    candidates = candidate.get("records") or []
    if not candidate.get("valid") or len(candidates) != 2:
        fail(
            "probe_execution_failed", None,
            str(candidate.get("error_detail") or "The submitted hooks did not return two feasible probe records."),
        )
    else:
        ruin_trace, recreate_trace = map(_first_trace, candidates)
        if not ruin_trace.get("ruin_scores_vary"):
            fail("hook_not_causally_effective", ruin.name, "The submitted ruin hook did not distinguish first-step customers.")
        if not recreate_trace.get("first_recreate_choice") or not recreate_trace.get("recreate_scores_vary"):
            fail("hook_not_causally_effective", recreate.name, "The submitted recreate hook did not distinguish first-step actions.")

    return GateProbeResult({
        "ruin": {"instance_id": ruin_fixture["instance_id"], "prefer_A": ruin_a, "prefer_B": ruin_b},
        "recreate": {
            "instance_id": recreate_fixture["instance_id"], "prefer_A": recreate_a, "prefer_B": recreate_b,
        },
        "submitted_hooks": [_first_trace(record) for record in candidates],
    }, tuple(failures))


def _first_trace(record: Mapping[str, Any]) -> dict[str, Any]:
    trace = record.get("merge_sequence") or []
    return trace[0] if trace and isinstance(trace[0], dict) else {}


def _gate5_instances(_design: InterfaceDesign) -> Sequence[Mapping[str, Any]]:
    return _build_gate5_n200_stress_instances()


def _gate5(context: GateProbeContext, records: Sequence[Mapping[str, Any]]) -> GateProbeResult:
    _, nominal, scaled = _default_gate5_instances()
    response = context.evaluate([nominal, scaled])
    scale_records = response.get("records") or []
    if (
        not response.get("valid") or len(scale_records) != 2
        or any(record.get("objective") is None for record in scale_records)
    ):
        return GateProbeResult(failures=(GateFailure(
            5, "budget_and_scale_diagnostics", response.get("error_code") or "scale_probe_failed", None, None,
            str(response.get("error_detail") or "The scale pair did not return two feasible objectives."),
            "Return feasible routes at nominal scale and at 1e-3 scale.",
        ),))

    nominal_cost, scaled_cost = (float(record["objective"]) for record in scale_records)
    scale = float(scaled["coord_scale"])
    drift = round(100.0 * abs(scaled_cost / scale - nominal_cost) / max(nominal_cost, 1e-12), 4)
    return GateProbeResult({
        "budget_ms": context.solve_deadline_ms,
        "stress_instance_ids": [record["instance_id"] for record in records],
        "scale_factor": scale,
        "scale_drift_pct": drift,
        "scale_drift_warning": drift > 0.05,
    })


register_problem_gate_probe(ProblemGateProbeSpec(
    problem_family="cvrp",
    protocol_id=LEGACY_CVRP_PROTOCOL_ID,
    gate3_instances=_gate3_instances,
    gate4=_gate4,
    gate5_instances=_gate5_instances,
    gate5=_gate5,
    template_key=L3B_TEMPLATE_KEY,
))
