"""Protocol gates for the fleet-aware CVRP merge and repair template."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from .contracts import LEGACY_CVRP_PROTOCOL_ID, GateFailure, HookSpec, InterfaceDesign, sha256_text
from .fleet_exact_k import BASELINE_ADJUSTMENT_CODE, FLEET_EXACT_K_TEMPLATE_KEY, _dissolve_donor, _pack_first_fit
from .multiscale import ONLINE_C2_JOINT_PROBES, generate_c2_joint_probe
from .runtime import DynamicSubprocessEvaluator
from .templates import get_template_spec
from .validator import (
    GateProbeContext,
    GateProbeResult,
    ProblemGateProbeSpec,
    _build_gate5_n200_stress_instances,
    _default_gate5_instances,
    register_problem_gate_probe,
)


def _instance(
    name: str, points: Sequence[Sequence[float]], demands: Sequence[int], capacity: int, target: int | None = None,
) -> dict[str, Any]:
    result = {
        "instance_id": f"c1_{name}",
        "size": len(demands),
        "depot": [0.0, 0.0],
        "customer_coordinates": [list(point) for point in points],
        "demands": list(demands),
        "capacity": capacity,
    }
    if target is not None:
        result["k_vehicles"] = target
    return result


def _gate3_instances(_design: InterfaceDesign) -> list[dict[str, Any]]:
    points = [[1, 0], [2, 0.1], [4, 0.3], [5, 0.4]]
    return [
        _instance("missing_target", points, [1, 2, 3, 4], 10),
        _instance("tight_target", points, [6, 4, 5, 5], 10, 2),
        _instance("under_fleet_witness", points, [1, 2, 3, 4], 10, 3),
        # The load lower bound is two, but the three sixes cannot share bins.
        _instance("unpackable_target", points, [6, 6, 6, 2], 10, 2),
    ]


def _first_merge(record: Mapping[str, Any]) -> list[int]:
    sequence = record.get("merge_sequence") or []
    return sequence[0] if sequence else []


def _interrupted_repair_rolls_back() -> bool:
    class InterruptedDeadline:
        polls = 0

        def __le__(self, _timestamp: float) -> bool:
            self.polls += 1
            # Two survivor checks precede the first insertion. Interrupt the second item.
            return self.polls > 2

        def __gt__(self, timestamp: float) -> bool:
            return not self.__le__(timestamp)

    routes = [[1], [2], [3, 4]]
    demands = np.array([0, 7, 8, 3, 2], dtype=np.float64)
    points = np.arange(len(demands), dtype=np.float64)
    dmat = np.abs(points[:, None] - points)
    result = _dissolve_donor(routes, 2, dmat, demands, 10, InterruptedDeadline())
    return result is None and routes == [[1], [2], [3, 4]]


def _gate4(context: GateProbeContext) -> GateProbeResult:
    template = get_template_spec(*FLEET_EXACT_K_TEMPLATE_KEY)
    static, adjustment = template.hook_specs
    baseline = template.baseline_implementations()
    fixture = _instance("causal_merges", [[1, 0], [2, 0.1], [4, 0.3]], [1, 2, 4], 10, 2)
    failures: list[GateFailure] = []

    def fail(symbol: str, detail: str) -> None:
        failures.append(GateFailure(
            4, "dual_action_causal_sensitivity", "hook_not_causally_effective", None, symbol, detail,
            "Return distinct finite scores for competing feasible merges.",
        ))

    evaluator = DynamicSubprocessEvaluator()

    def prefer(spec: HookSpec, expression: str) -> list[int]:
        source = f"import numpy as np\n\ndef {spec.name}({', '.join(spec.signature)}):\n    return {expression}\n"
        response = evaluator.evaluate(
            template_id=template.template_id,
            template_version=template.template_version,
            protocol_id=context.protocol_id,
            instances=[fixture],
            hook_implementations={**baseline, spec.name: source},
            template_options={"fleet_repair_enabled": False},
            solve_deadline_ms=context.solve_deadline_ms,
            capture_merge_sequence=True,
        )
        records = response.get("records") or []
        return _first_merge(records[0]) if response.get("valid") and len(records) == 1 else []

    static_a = prefer(static, "1.0 * ((i_idx == 1) & (j_idx == 2))")
    static_b = prefer(static, "1.0 * ((i_idx == 2) & (j_idx == 3))")
    if (static_a, static_b) != ([1, 2], [2, 3]):
        fail(static.name, "Changing the static preference must change the first merged pair.")

    adjustment_a = prefer(adjustment, "-128.0 * (load_i_frac + load_j_frac)")
    adjustment_b = prefer(adjustment, "128.0 * (load_i_frac + load_j_frac)")
    if (adjustment_a, adjustment_b) != ([1, 2], [2, 3]):
        fail(adjustment.name, "Changing the fleet adjustment must change the first merged pair.")

    # The first merge reaches K. Check additional fleet feasibility on the same
    # candidate worker because the generic Gate 3 checks only route validity.
    fleet_fixtures = _gate3_instances(context.design)
    response = context.evaluate([fixture, *fleet_fixtures], capture_merge_sequence=True)
    records = response.get("records") or []
    candidate = {}
    if not response.get("valid") or len(records) != 1 + len(fleet_fixtures):
        failures.append(GateFailure(
            4, "dual_action_causal_sensitivity", "probe_execution_failed", None, None,
            str(response.get("error_detail") or "The submitted bundle did not return all feasible probe records."),
            "Check the two hooks' return shapes and feasibility of the returned routes.",
        ))
    else:
        candidate = records[0].get("fleet_diagnostics") or {}
        if not _first_merge(records[0]) or candidate.get("static_scores_vary") is not True:
            fail(static.name, "The submitted static hook did not distinguish competing merges.")
        adjustment_hash = (response.get("hook_hashes") or {}).get(adjustment.name)
        if adjustment_hash != sha256_text(BASELINE_ADJUSTMENT_CODE) and (
            candidate.get("adjustment_features_vary") is not True
            or candidate.get("adjustment_scores_vary") is not True
        ):
            fail(adjustment.name, "The submitted adjustment was constant on non-constant feasible merge features.")

        expected = (None, True, True, False)
        repair_enabled = bool(context.design.template_options.get("fleet_repair_enabled", True))
        for record, exact in zip(records[1:], expected, strict=True):
            if exact is True and not repair_enabled:
                continue
            if record.get("exact_vehicle_count") is not exact:
                failures.append(GateFailure(
                    3, "subprocess_feasibility", "fleet_probe_mismatch", None, record.get("instance_id"),
                    f"Expected exact_vehicle_count={exact} but received {record.get('exact_vehicle_count')}.",
                    "Check missing targets, exact-K packing and splitting, and fallback after failed repair.",
                ))

    rolled_back = _interrupted_repair_rolls_back()
    if not rolled_back:
        failures.append(GateFailure(
            3, "subprocess_feasibility", "interrupted_repair_mutated_incumbent", None, None,
            "The interrupted donor dissolution did not preserve the incumbent routes.",
            "Stage donor insertions and survivor swaps privately until the donor is fully dissolved.",
        ))
    return GateProbeResult({
        "static": {"prefer_A": static_a, "prefer_B": static_b},
        "adjustment": {"prefer_A": adjustment_a, "prefer_B": adjustment_b},
        "submitted": dict(candidate),
        "fleet_feasibility": {record["instance_id"]: record.get("exact_vehicle_count") for record in records[1:]},
        "interrupted_repair_rolled_back": rolled_back,
    }, tuple(failures))


def _with_feasible_target(instance: Mapping[str, Any]) -> dict[str, Any]:
    demands = np.array([0, *instance["demands"]], dtype=np.float64)
    items = sorted(range(1, len(demands)), key=lambda node: -demands[node])
    bins = _pack_first_fit(items, demands, float(instance["capacity"]), math.inf)
    return {**instance, "k_vehicles": len(bins)}


def _gate5_instances(_design: InterfaceDesign) -> list[dict[str, Any]]:
    return [
        *(_with_feasible_target(instance) for instance in _build_gate5_n200_stress_instances()),
        *(generate_c2_joint_probe(**probe) for probe in ONLINE_C2_JOINT_PROBES),
    ]


def _gate5(context: GateProbeContext, stress: Sequence[Mapping[str, Any]]) -> GateProbeResult:
    _, nominal, scaled = _default_gate5_instances()
    nominal = _with_feasible_target(nominal)
    response = context.evaluate([nominal, {**scaled, "k_vehicles": nominal["k_vehicles"]}])
    scale_records = response.get("records") or []
    failures: list[GateFailure] = []
    diagnostics = {
        "budget_ms": context.solve_deadline_ms,
        "stress_instance_ids": [record["instance_id"] for record in stress],
        "stress_exact_k_count": sum(record.get("exact_vehicle_count") is True for record in stress),
        "scale_factor": float(scaled["coord_scale"]),
    }
    if (
        not response.get("valid") or len(scale_records) != 2
        or any(record.get("objective") is None for record in scale_records)
    ):
        failures.append(GateFailure(
            5, "budget_and_scale_diagnostics", "scale_probe_failed", None, None,
            str(response.get("error_detail") or "The scale pair did not return two feasible routes."),
            "Return valid routes for both the nominal and scaled instances.",
        ))
    else:
        nominal_cost, scaled_cost = (float(record["objective"]) for record in scale_records)
        drift = 100.0 * abs(scaled_cost / diagnostics["scale_factor"] - nominal_cost) / max(nominal_cost, 1e-12)
        diagnostics.update(scale_drift_pct=round(drift, 4), scale_drift_warning=drift > 0.05)

    for record in [*stress, *scale_records]:
        solve_ms = record.get("solve_ms")
        if (
            record.get("outcome_class") != "completed"
            or record.get("budget_exhausted") is not False
            or type(solve_ms) not in (int, float)
            or not math.isfinite(solve_ms)
            or not 0.0 <= solve_ms <= context.solve_deadline_ms
        ):
            failures.append(GateFailure(
                5, "budget_and_scale_diagnostics", "strict_return_deadline_missed", None, record.get("instance_id"),
                f"Outcome {record.get('outcome_class')} returned in {solve_ms} ms for a {context.solve_deadline_ms} ms budget.",
                "Poll the shared effective deadline before starting bounded solver work.",
            ))
    return GateProbeResult(diagnostics, tuple(failures))


register_problem_gate_probe(ProblemGateProbeSpec(
    problem_family="cvrp",
    protocol_id=LEGACY_CVRP_PROTOCOL_ID,
    gate3_instances=_gate3_instances,
    gate4=_gate4,
    gate5_instances=_gate5_instances,
    gate5=_gate5,
    template_key=FLEET_EXACT_K_TEMPLATE_KEY,
))
