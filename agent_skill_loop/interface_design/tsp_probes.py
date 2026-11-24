"""Feasibility, causal, and budget/scale probes for TSP interface designs."""

from __future__ import annotations

import random
from collections.abc import Mapping, Sequence
from typing import Any

from .contracts import GateFailure, InterfaceDesign
from .tsp_adapter import TSP_PROTOCOL_ID
from .tsp_templates import TSP_CONSTRUCTIVE, TSP_GUIDED_INSERTION
from .validator import GateProbeContext, GateProbeResult, ProblemGateProbeSpec, register_problem_gate_probe

_GATE4 = "dual_action_causal_sensitivity"
_GATE5 = "budget_and_scale_diagnostics"
_SCALES = (1e-3, 1.0, 1e3)
_SCALE_DRIFT_LIMIT = 0.0005


def _fixture(n: int, seed: int, *, clustered: bool = False) -> dict[str, Any]:
    rng = random.Random(seed)
    coordinates = []
    for city in range(n):
        x, y = rng.random(), rng.random()
        if clustered:
            x, y = (city % 4) * 3 + x, (city % 3) * 2 + y
        coordinates.append((x, y))
    return {"instance_id": f"tsp-probe-{n}-{seed}", "protocol_id": TSP_PROTOCOL_ID, "coordinates": coordinates}


def _gate3_instances(_design: InterfaceDesign) -> list[dict[str, Any]]:
    return [_fixture(3, 10), _fixture(12, 11), _fixture(32, 12, clustered=True)]


def _gate5_instances(_design: InterfaceDesign) -> list[dict[str, Any]]:
    return [_fixture(200, 40), _fixture(200, 41, clustered=True)]


def _gate4(context: GateProbeContext) -> GateProbeResult:
    instance = {
        "instance_id": "tsp-probe-causal-6",
        "protocol_id": TSP_PROTOCOL_ID,
        "coordinates": [(0, 0), (1, 2), (4, 1), (5, 13), (12, 8), (14, 8)],
    }
    design = context.design
    if design.template_id == TSP_CONSTRUCTIVE:
        preferences = (("-unvisited_nodes", 1), ("1.0 * (unvisited_nodes == 2)", 2))
    elif design.template_id == TSP_GUIDED_INSERTION:
        preferences = (("-unvisited_nodes", [1, 0, 5]), ("unvisited_nodes", [4, 0, 5]))
    else:
        raise ValueError(f"unsupported_tsp_causal_probe:{design.template_id}")
    header = f"def {design.hook_name}({', '.join(design.hook_signature)}):\n"
    diagnostics: dict[str, Any] = {"instance_id": instance["instance_id"]}
    traces = []
    for label, (scores, expected) in zip(("prefer_A", "prefer_B"), preferences):
        response = context.evaluate(
            [instance, instance], hook_code=f"{header}    return {scores}\n", capture_merge_sequence=True,
        )
        records = response.get("records", [])
        if not response.get("completed") or len(records) != 2:
            return GateProbeResult(diagnostics, (GateFailure(
                4, _GATE4, "probe_execution_failed", None, design.hook_name,
                f"{label} failed to complete: {response.get('error_code') or response.get('error_detail')}.",
                "Check the solve deadline and the feasibility of the constructed tour.",
            ),))
        trace, replay = [(r.get("first_action"), r.get("pre_postprocess_tour")) for r in records]
        action, tour = trace
        diagnostics[f"{label}_first_action"] = action
        diagnostics[f"{label}_pre_postprocess_tour"] = tour
        if action != expected or not tour or trace != replay:
            return GateProbeResult(diagnostics, (GateFailure(
                4, _GATE4, "hook_not_causally_effective", None, design.hook_name,
                f"{label} expected first action {expected}, got {action}. Trace replay matched: {trace == replay}.",
                "Use the hook scores to make deterministic construction decisions and capture the tour before 2-opt.",
            ),))
        traces.append(tour)

    candidate = context.evaluate([instance], capture_merge_sequence=True)
    records = candidate.get("records", [])
    informative = records[0].get("informative_hook_calls") if records else None
    tours_differ = traces[0] != traces[1]
    diagnostics.update(pre_postprocess_tours_differ=tours_differ, informative_hook_calls=informative)
    if not candidate.get("completed"):
        return GateProbeResult(diagnostics, (GateFailure(
            4, _GATE4, "probe_execution_failed", None, design.hook_name,
            "The candidate did not complete the six-city causal fixture.",
            "Check the hook output and solve deadline on the causal fixture.",
        ),))
    if not tours_differ or not informative:
        return GateProbeResult(diagnostics, (GateFailure(
            4, _GATE4, "hook_not_causally_effective", None, design.hook_name,
            "The forced tours matched or the candidate gave every legal choice the same score at each step.",
            "Score legal choices using features that can distinguish them during construction.",
        ),))
    return GateProbeResult(diagnostics)


def _gate5(context: GateProbeContext, stress_records: Sequence[Mapping[str, Any]]) -> GateProbeResult:
    solve_times = [record["solve_ms"] for record in stress_records]
    diagnostics: dict[str, Any] = {"stress_solve_ms": solve_times, "solve_deadline_ms": context.solve_deadline_ms}
    if any(not record.get("completed") or record["solve_ms"] > context.solve_deadline_ms for record in stress_records):
        return GateProbeResult(diagnostics, (GateFailure(
            5, _GATE5, "solve_deadline_exceeded", None, context.design.hook_name,
            "At least one stress solve exceeded the per-instance deadline.",
            "Reduce the work done on each construction step.",
        ),))

    base = _fixture(24, 51, clustered=True)
    fixtures = [
        {**base, "instance_id": f"{base['instance_id']}-scale-{factor:g}",
         "coordinates": [(x * factor, y * factor) for x, y in base["coordinates"]]}
        for factor in _SCALES
    ]
    response = context.evaluate(fixtures, distance_convention="euc_2d_float", capture_merge_sequence=True)
    records = response.get("records", [])
    if not response.get("completed") or len(records) != len(_SCALES):
        return GateProbeResult(diagnostics, (GateFailure(
            5, _GATE5, "scale_probe_execution_failed", None, context.design.hook_name,
            "The worker failed to complete and verify all scaled tours.",
            "Check score finiteness and solve time at each coordinate scale.",
        ),))

    actions = [record.get("construction_actions") for record in records]
    adjusted_lengths = [record["objective"] / factor for record, factor in zip(records, _SCALES)]
    reference = adjusted_lengths[1]
    drift = max(abs(length - reference) / reference for length in adjusted_lengths)
    actions_match = bool(actions[1]) and all(action == actions[1] for action in actions)
    diagnostics.update(
        scale_factors=list(_SCALES), scale_first_actions=[record.get("first_action") for record in records],
        scale_actions_match=actions_match, scale_adjusted_lengths=adjusted_lengths, scale_max_relative_drift=drift,
    )
    if not actions_match or drift > _SCALE_DRIFT_LIMIT:
        return GateProbeResult(diagnostics, (GateFailure(
            5, _GATE5, "scale_invariance_failed", None, context.design.hook_name,
            f"Scaled construction actions matched: {actions_match}. Adjusted tour length drift: {drift:.3%}.",
            "Keep scores comparable under a uniform change of distance units.",
        ),))
    return GateProbeResult(diagnostics)


register_problem_gate_probe(ProblemGateProbeSpec(
    problem_family="tsp",
    protocol_id=TSP_PROTOCOL_ID,
    gate3_instances=_gate3_instances,
    gate4=_gate4,
    gate5_instances=_gate5_instances,
    gate5=_gate5,
))
