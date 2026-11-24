from __future__ import annotations

import math

import pytest

from agent_skill_loop.benchmark import load_profile_suite
from agent_skill_loop.cvrp_workbench.suites import BENCHMARK_ID, load_m31_suite
from agent_skill_loop.cvrp_workbench.tsp_obp import evaluate_obp_algorithm_on_instance
from agent_skill_loop.interface_design import (
    DynamicSubprocessEvaluator,
    InterfaceValidator,
    build_interface_design,
    get_template_spec,
)
from agent_skill_loop.interface_design.bpp_templates import BPP_TEMPLATE_ID
from agent_skill_loop.interface_design.eval_worker import _handle_request
from agent_skill_loop.interface_design.obp_templates import OBP_TEMPLATE_ID
from agent_skill_loop.interface_design.packing_probes import PACKING_MOCK_CANDIDATES_BY_TEMPLATE
from agent_skill_loop.interface_design.runtime import resolve_problem_adapter
from agent_skill_loop.problems.bpp_offline import bpp_bfd, bpp_ffd, verify_bpp_solution


OBP_PROTOCOL = "obp_online/v1"
BPP_PROTOCOL = "bpp_offline/v1"
PACKING_CASES = ((OBP_TEMPLATE_ID, "obp", OBP_PROTOCOL), (BPP_TEMPLATE_ID, "bpp", BPP_PROTOCOL))


def _instance(protocol_id, items=(625, 750, 250, 125, 375, 500, 125, 875), capacity=1000, *, name="packing"):
    return {"instance_id": name, "protocol_id": protocol_id, "items": list(items), "capacity": capacity}


def _request(template_id, instances, **overrides):
    template = get_template_spec(template_id, "v1")
    return {
        "template_id": template_id,
        "template_version": "v1",
        "problem_family": template.problem_family,
        "protocol_id": template.effective_protocol_id,
        "hook_code": template.default_baseline_hook_code,
        "instances": instances,
        "solve_deadline_ms": 500.0,
        **overrides,
    }


@pytest.mark.parametrize("template_id,family,protocol", PACKING_CASES)
def test_packing_adapters_verify_results_and_reject_protocol_mismatch(template_id, family, protocol):
    template = get_template_spec(template_id, "v1")
    adapter = resolve_problem_adapter(template, problem_family=family, protocol_id=protocol)
    assert (adapter.problem_family, adapter.protocol_id, adapter.objective_key) == (family, protocol, "bins_used")
    spec, = template.hook_specs
    shape_arg = "feasible_remaining_capacities" if family == "obp" else "item_sizes"
    assert spec.output_shape_arg == shape_arg

    instance = _instance(protocol)
    result = _handle_request(_request(template_id, [instance], capture_merge_sequence=True))
    record, = result["records"]
    assert result["valid"] and record["completed"]
    assert (record["problem_family"], record["protocol_id"]) == (family, protocol)
    assert record["bins_used"] == record["objective"]
    assert result["template_source_sha256"] == template.template_source_sha256
    if family == "obp":
        assert record["decision_trace"] == record["item_to_bin"]
        assert record["decision_trace"][:3] == [0, 1, 1]
        assert record["bin_open_trace"][:3] == [True, True, False]
    else:
        assert record["bins"] == bpp_ffd(instance["items"], instance["capacity"])
        assert record["first_order"] == sorted(range(len(instance["items"])), key=lambda i: -instance["items"][i])
        assert record["pre_repack_bins"] == record["bins"]

    other_protocol = BPP_PROTOCOL if family == "obp" else OBP_PROTOCOL
    for request in (
        _request(template_id, [instance], protocol_id=other_protocol),
        _request(template_id, [{**instance, "protocol_id": other_protocol}]),
    ):
        rejection = _handle_request(request)
        assert rejection["error_code"] == "protocol_id_mismatch"
        assert rejection["records"] == []


def test_offline_repack_preserves_exact_original_ids_and_initial_trace():
    instance = _instance(BPP_PROTOCOL, [4, 7, 2, 5], 10)
    arrival_order = "def rank_items(item_sizes, capacity):\n    return -np.arange(len(item_sizes))\n"
    response = _handle_request(_request(
        BPP_TEMPLATE_ID, [instance], hook_code=arrival_order,
        capture_merge_sequence=True, postprocess_mode="repack",
    ))
    record, = response["records"]
    assert record["valid"] and record["completed"]
    assert record["first_order"] == [0, 1, 2, 3]
    assert record["pre_repack_bins"] == [[0, 2], [1], [3]]
    assert record["bins"] == [[0, 3], [1, 2]]
    assert record["bins_used"] == 2

    assert verify_bpp_solution(instance, bpp_bfd(instance["items"], instance["capacity"]))["valid"]
    for invalid in ([[0, 3], [1, 1]], [[0, 3], [1]], [[0, 3], [1, 4]], [[0, 1], [2, 3]]):
        assert not verify_bpp_solution(instance, invalid)["valid"]


@pytest.mark.parametrize("template_id,family,protocol", PACKING_CASES)
@pytest.mark.parametrize("expression,error", (
    ("0.0", "invalid_return"),
    ("[[0.0] for _ in {shape_arg}]", "invalid_return"),
    ("[float('nan') for _ in {shape_arg}]", "nonfinite_objective"),
    ("[float('inf') for _ in {shape_arg}]", "nonfinite_objective"),
))
def test_packing_templates_enforce_finite_one_dimensional_outputs(template_id, family, protocol, expression, error):
    template = get_template_spec(template_id, "v1")
    spec, = template.hook_specs
    source = f"def {spec.name}({', '.join(spec.signature)}):\n    return {expression.format(shape_arg=spec.output_shape_arg)}\n"
    # The new templates enforce the output contract even when the shared compatibility wrapper is disabled.
    result = _handle_request(_request(
        template_id, [_instance(protocol)], hook_code=source, strict_hook_outputs=False,
    ))
    assert not result["valid"]
    assert result["error_code"] == error


@pytest.mark.parametrize("template_id,family,protocol", PACKING_CASES)
def test_packing_candidates_pass_gates_1_to_5(template_id, family, protocol):
    design = build_interface_design(template_id, postprocess_mode="repack" if family == "bpp" else "none")
    assert design.protocol_id == protocol
    candidate = PACKING_MOCK_CANDIDATES_BY_TEMPLATE[template_id][0]
    report = InterfaceValidator(solve_deadline_ms=500.0).validate(design, hook_code_override=candidate)
    assert report.passed, [failure.as_dict() for failure in report.failures]
    assert [(gate["gate_id"], gate["passed"]) for gate in report.gates] == [(i, True) for i in range(1, 6)]


def test_obp_gate_4_rejects_a_suffix_dependent_open_trace():
    class SuffixDependentTraceEvaluator:
        def evaluate(self, **request):
            request["solve_deadline_ms"] = request.pop("instance_time_budget_ms")
            response = _handle_request(request)
            streams = [instance["items"] for instance in request["instances"]]
            records = response["records"]
            if request["capture_merge_sequence"] and len(streams) >= 3 and len(records) == len(streams):
                shortest = min(streams, key=len)
                if all(stream[:len(shortest)] == shortest for stream in streams):
                    longest = max(range(len(streams)), key=lambda index: len(streams[index]))
                    trace = records[longest]["bin_open_trace"]
                    trace[0] = not trace[0]
            return response

    design = build_interface_design(OBP_TEMPLATE_ID)
    report = InterfaceValidator(evaluator=SuffixDependentTraceEvaluator()).validate(design)
    assert not report.passed
    assert [(failure.gate_id, failure.error_code) for failure in report.failures] == [(4, "prefix_invariance_violation")]


def test_online_template_decides_before_reading_the_next_item():
    calls = []

    def arrivals():
        yield 750
        yield 625
        yield 250
        assert calls == [(250, [250.0, 375.0])]
        yield 125

    def priority(item, remaining):
        with pytest.raises(ValueError):
            remaining.setflags(write=True)
        calls.append((item, remaining.tolist()))
        return -remaining

    template = get_template_spec(OBP_TEMPLATE_ID, "v1")
    assignments, trace = template.runner(arrivals(), 1000, priority, capture_merge_sequence=True)
    assert assignments == trace["decision_trace"] == [0, 1, 0, 1]
    assert trace["bin_open_trace"] == [True, True, False, False]


@pytest.mark.parametrize("template_id,family,protocol", PACKING_CASES)
def test_packing_scale_equivalence_includes_traces_and_normalized_feasibility(template_id, family, protocol):
    # The first two bins tie after the third arrival, including after rescaling.
    nominal = _instance(protocol, (6, 9, 3, 1, 5, 2, 7), 10)
    instances = [
        _instance(protocol, [item * factor for item in nominal["items"]], nominal["capacity"] * factor, name=str(factor))
        for factor in (1e-3, 1, 1e3)
    ]
    result = _handle_request(_request(template_id, instances, capture_merge_sequence=True))
    assert result["valid"] and result["completed"]
    records = result["records"]
    trace_keys = ("decision_trace", "bin_open_trace") if family == "obp" else ("first_order", "pre_repack_bins", "bins")
    for record in records:
        assert record["bins_used"] == records[1]["bins_used"]
        assert all(record[key] == records[1][key] for key in trace_keys)
        loads = record["normalized_bin_loads"]
        assert loads == pytest.approx(records[1]["normalized_bin_loads"])
        assert all(0 < load <= 1 + 1e-12 for load in loads)
        assert math.fsum(loads) == pytest.approx(sum(nominal["items"]) / nominal["capacity"])


def test_new_obp_best_fit_matches_legacy_on_all_70_bpplib_instances():
    suite = load_profile_suite(BENCHMARK_ID, "obp_ext_bpplib", split="heldout")
    assert len(suite["instances"]) == 70
    result = DynamicSubprocessEvaluator().evaluate(**_request(OBP_TEMPLATE_ID, suite["instances"]))
    assert result["valid"] and result["completed"], result["error_detail"]
    expected = [evaluate_obp_algorithm_on_instance("obp_best_fit", row)["bins_used"] for row in suite["instances"]]
    assert result["ordered_instance_objectives"] == expected


@pytest.mark.parametrize("template_id,family,protocol", PACKING_CASES)
def test_m31_packing_dev_suite_smoke(template_id, family, protocol):
    suite = load_m31_suite(f"{family}_m31_dev_36")
    assert suite["protocol_id"] == protocol
    assert len(suite["instances"]) == 36
    result = DynamicSubprocessEvaluator().evaluate(**_request(template_id, suite["instances"]))
    assert result["valid"] and result["completed"], result["error_detail"]
    assert len(result["records"]) == 36
    assert all(row["protocol_id"] == protocol and row["bins_used"] > 0 for row in result["records"])
    if family == "bpp":
        assert result["ordered_instance_objectives"] == [row["reference_objective"] for row in suite["instances"]]
