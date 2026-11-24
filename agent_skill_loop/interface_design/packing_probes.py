"""Protocol-scoped validation fixtures for the two packing interfaces."""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from .bpp_templates import BPP_FFD_HOOK_CODE, BPP_TEMPLATE_ID
from .contracts import GateFailure
from .obp_templates import OBP_BEST_FIT_HOOK_CODE, OBP_FIRST_FIT_HOOK_CODE, OBP_TEMPLATE_ID
from .packing_adapters import BPP_PROTOCOL_ID, OBP_PROTOCOL_ID
from .validator import GateProbeContext, GateProbeResult, ProblemGateProbeSpec, register_problem_gate_probe

_OBP_WORST_FIT_CODE = """def priority(current_item, feasible_remaining_capacities):
    return feasible_remaining_capacities
"""
_BPP_ASCENDING_CODE = """def rank_items(item_sizes, capacity):
    return -item_sizes
"""
PACKING_MOCK_CANDIDATES_BY_TEMPLATE = {
    OBP_TEMPLATE_ID: (OBP_BEST_FIT_HOOK_CODE, OBP_FIRST_FIT_HOOK_CODE, _OBP_WORST_FIT_CODE),
    BPP_TEMPLATE_ID: (BPP_FFD_HOOK_CODE, _BPP_ASCENDING_CODE),
}

_OBP_PREFIX = (750, 625, 250, 125)
_BPP_ACTION_ITEMS = (375, 875, 250, 500)
_SCALE_FACTORS = (1e-3, 1.0, 1e3)
_SCALE_ITEMS = (600, 900, 300, 100, 500, 375, 125, 750, 125, 250)


def _instance(protocol: str, label: str, items: Sequence[float], capacity: float = 1000) -> dict[str, Any]:
    return {"instance_id": label, "protocol_id": protocol, "capacity": capacity, "items": list(items)}


def _gate3_instances(protocol: str) -> list[dict[str, Any]]:
    return [
        _instance(protocol, "gate3-exact-fit", (375, 625, 1000, 750)),
        _instance(protocol, "gate3-repeated-items", (750, 125, 125, 750, 250)),
    ]


def _stress_instances(protocol: str) -> list[dict[str, Any]]:
    return [
        _instance(protocol, "gate5-mixed-weights", _SCALE_ITEMS * 32),
        _instance(protocol, "gate5-many-open-bins", (875,) * 200 + (125,) * 200),
    ]


def _failure(context: GateProbeContext, gate_id: int, code: str, detail: str, hint: str) -> GateFailure:
    gate_name = "dual_action_causal_sensitivity" if gate_id == 4 else "budget_and_scale_diagnostics"
    return GateFailure(gate_id, gate_name, code, None, context.design.hook_name, detail, hint)


def _completed_records(response: Mapping[str, Any], count: int) -> Sequence[Mapping[str, Any]]:
    records = response.get("records") or []
    if response.get("valid") and len(records) == count and all(
        rec.get("valid") and rec.get("completed") for rec in records
    ):
        return records
    return ()


def _obp_gate4(context: GateProbeContext) -> GateProbeResult:
    prefix = _instance(context.protocol_id, "gate4-prefix-only", _OBP_PREFIX)
    prefer_first = context.evaluate([prefix], hook_code=OBP_FIRST_FIT_HOOK_CODE, capture_merge_sequence=True)
    prefer_last = context.evaluate([prefix], hook_code=_OBP_WORST_FIT_CODE, capture_merge_sequence=True)
    controls = []
    for response in (prefer_first, prefer_last):
        records = _completed_records(response, 1)
        controls.append(records[0].get("decision_trace") if records else None)
    failures = []
    if any(not trace or len(trace) != len(_OBP_PREFIX) for trace in controls) or (
        [trace[:3] for trace in controls] != [[0, 1, 0], [0, 1, 1]]
    ):
        failures.append(_failure(
            context, 4, "hook_not_causally_effective",
            "Two open bins fit the third item, but the opposite priority hooks did not choose distinct bins.",
            "Commit the highest-scored feasible bin for the current item before reading the next arrival.",
        ))

    variants = [
        prefix,
        _instance(context.protocol_id, "gate4-prefix-with-suffix-a", (*_OBP_PREFIX, 1000, 875, 125)),
        _instance(context.protocol_id, "gate4-prefix-with-suffix-b", (*_OBP_PREFIX, 125, 250, 750, 375)),
    ]
    records = _completed_records(context.evaluate(variants, capture_merge_sequence=True), len(variants))
    traces = []
    for instance, record in zip(variants, records):
        decisions = record.get("decision_trace") or []
        opened = record.get("bin_open_trace") or []
        if len(decisions) != len(instance["items"]) or len(opened) != len(decisions):
            break
        traces.append((decisions[:len(_OBP_PREFIX)], opened[:len(_OBP_PREFIX)]))
    prefix_equal = len(traces) == len(variants) and all(trace == traces[0] for trace in traces[1:])
    if not prefix_equal:
        failures.append(_failure(
            context, 4, "prefix_invariance_violation",
            "The decision or bin-opening trace changed across streams sharing the same prefix.",
            "Supply the hook only the current item and feasible residual capacities, and commit on arrival.",
        ))
    return GateProbeResult({
        "prefer_first_decisions": controls[0],
        "prefer_last_decisions": controls[1],
        "prefix_length": len(_OBP_PREFIX),
        "prefix_variants": len(variants),
        "prefix_trace_equal": prefix_equal,
    }, tuple(failures))


def _bpp_gate4(context: GateProbeContext) -> GateProbeResult:
    fixture = _instance(context.protocol_id, "gate4-fixed-item-list", _BPP_ACTION_ITEMS)
    orders = []
    initial_bins = []
    for code in (BPP_FFD_HOOK_CODE, _BPP_ASCENDING_CODE):
        records = _completed_records(context.evaluate(
            [fixture], hook_code=code, capture_merge_sequence=True,
        ), 1)
        orders.append(records[0].get("first_order") if records else None)
        initial_bins.append(records[0].get("pre_repack_bins") if records else None)
    causal = orders == [[1, 3, 0, 2], [2, 0, 3, 1]] and initial_bins == [
        [[1], [3, 0], [2]],
        [[2, 0], [3], [1]],
    ]
    failures = () if causal else (_failure(
        context, 4, "hook_not_causally_effective",
        "Opposite rankings failed to produce their expected item orders and initial packings.",
        "Apply stable descending priority to the original item IDs before the first packing pass.",
    ),)
    return GateProbeResult({"first_orders": orders, "pre_repack_bins": initial_bins}, failures)


def _gate5(
    context: GateProbeContext,
    stress_records: Sequence[Mapping[str, Any]],
    trace_keys: tuple[str, ...],
) -> GateProbeResult:
    completed_count = sum(bool(record.get("completed")) for record in stress_records)
    diagnostics = {"solve_deadline_ms": context.solve_deadline_ms, "stress_completed": completed_count}
    if completed_count != len(stress_records):
        return GateProbeResult(diagnostics, (_failure(
            context, 5, "solve_deadline_exceeded", "A stress fixture did not complete within the solve deadline.",
            "Bound hook and packing work so every stress fixture finishes within the solve deadline.",
        ),))
    fixtures = [
        _instance(context.protocol_id, f"gate5-scale-{factor:g}",
                  [item * factor for item in _SCALE_ITEMS], capacity=1000 * factor)
        for factor in _SCALE_FACTORS
    ]
    records = _completed_records(context.evaluate(fixtures, capture_merge_sequence=True), len(fixtures))
    equivalent = False
    if records:
        nominal = records[1]
        nominal_loads = nominal.get("normalized_bin_loads") or []
        equivalent = all(
            record["bins_used"] == nominal["bins_used"] == len(nominal_loads)
            and all(record.get(key) is not None and record[key] == nominal.get(key) for key in trace_keys)
            and len(record.get("normalized_bin_loads", [])) == len(nominal_loads)
            and all(
                0 < load <= 1.0 + 1e-12 and math.isclose(load, expected, rel_tol=1e-12)
                for load, expected in zip(record["normalized_bin_loads"], nominal_loads)
            )
            for record in records
        )
    diagnostics.update(scale_factors=list(_SCALE_FACTORS), scale_equivalent=equivalent,
                       scale_bins_used=[record["bins_used"] for record in records])
    failures = () if equivalent else (_failure(
        context, 5, "scale_invariance_violation",
        "Scaling item sizes and capacity together changed the packing trace, bin count, or normalized loads.",
        "Keep priorities comparable across scales by working with ratios where appropriate.",
    ),)
    return GateProbeResult(diagnostics, failures)


def _obp_gate5(context: GateProbeContext, records: Sequence[Mapping[str, Any]]) -> GateProbeResult:
    return _gate5(context, records, ("decision_trace", "bin_open_trace"))


def _bpp_gate5(context: GateProbeContext, records: Sequence[Mapping[str, Any]]) -> GateProbeResult:
    return _gate5(context, records, ("first_order", "pre_repack_bins", "bins"))


for family, protocol, template, gate4, gate5 in (
    ("obp", OBP_PROTOCOL_ID, OBP_TEMPLATE_ID, _obp_gate4, _obp_gate5),
    ("bpp", BPP_PROTOCOL_ID, BPP_TEMPLATE_ID, _bpp_gate4, _bpp_gate5),
):
    register_problem_gate_probe(ProblemGateProbeSpec(
        problem_family=family,
        protocol_id=protocol,
        gate3_instances=lambda design: _gate3_instances(design.protocol_id),
        gate4=gate4,
        gate5_instances=lambda design: _stress_instances(design.protocol_id),
        gate5=gate5,
        template_key=(template, "v1"),
        distance_convention="not_applicable",
        vehicle_limit_policy="not_applicable",
    ))
