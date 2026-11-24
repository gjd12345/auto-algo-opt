from __future__ import annotations

import math
from dataclasses import replace

import pytest

from agent_skill_loop.benchmark.catalog import load_profile_suite
from agent_skill_loop.cvrp_workbench.suites import BENCHMARK_ID, load_m31_suite
from agent_skill_loop.cvrp_workbench.tsp_obp import (
    TSP_SOLVER_CATALOG,
    solve_tsp_farthest_insertion,
    verify_tsp_solution,
)
from agent_skill_loop.interface_design.eval_worker import _handle_request
from agent_skill_loop.interface_design.planner import build_interface_design
from agent_skill_loop.interface_design.runtime import resolve_problem_adapter
from agent_skill_loop.interface_design.templates import TEMPLATE_REGISTRY, get_template_spec
from agent_skill_loop.interface_design.tsp_adapter import TSP_PROTOCOL_ID
from agent_skill_loop.interface_design.tsp_templates import (
    TSP_CONSTRUCTIVE,
    TSP_GUIDED_INSERTION,
    TSP_MOCK_CANDIDATES_BY_TEMPLATE,
    TSP_STRONG_COMPARATOR,
)
from agent_skill_loop.interface_design.validator import InterfaceValidator

_TEMPLATES = (TSP_CONSTRUCTIVE, TSP_GUIDED_INSERTION)
_TRIANGLE = {
    "instance_id": "triangle", "protocol_id": TSP_PROTOCOL_ID,
    "coordinates": [(0.0, 0.0), (1.5, 0.0), (0.0, 1.5)],
}


def _adapter():
    return resolve_problem_adapter(get_template_spec(TSP_CONSTRUCTIVE, "v1"), protocol_id="tsp/v1")


def _verify(adapter, instance, tour, refs, convention):
    return adapter.verify_solution(
        instance, tour, refs, distance_convention=convention, vehicle_limit_policy="unconstrained",
    )


def _run(template_id, instances, **options):
    return _handle_request({
        "template_id": template_id, "template_version": "v1", "protocol_id": TSP_PROTOCOL_ID,
        "instances": instances, "hook_code": TSP_MOCK_CANDIDATES_BY_TEMPLATE[template_id][0],
        **options,
    })


@pytest.mark.parametrize("convention,edge,length", [
    ("euc_2d_float", 1.5, 3.0 + math.hypot(1.5, 1.5)),
    ("euc_2d_int", 2.0, 6.0),
    ("tsplib_euc_2d", 2.0, 6.0),
    ("euc_2d_nint", 2.0, 6.0),
])
def test_tsp_adapter_verifies_closed_tour_with_requested_metric(convention, edge, length):
    adapter = _adapter()
    assert adapter.problem_family == "tsp" and adapter.objective_key == "tour_length"
    (matrix,), refs = adapter.prepare_inputs(_TRIANGLE, convention)
    assert matrix[0, 1] == edge
    verified = _verify(adapter, _TRIANGLE, [0, 1, 2], refs, convention)
    assert verified["valid"] and verified["tour_length"] == pytest.approx(length)


def test_tsp_adapter_rejects_invalid_tours_and_matrix_tamper():
    adapter = _adapter()
    convention = "euc_2d_float"
    (matrix,), refs = adapter.prepare_inputs(_TRIANGLE, convention)
    for tour, code in (
        ([0, 1], "invalid_tour_length"), ([0, 1, 2, 0], "invalid_tour_length"),
        ([0, 1, 1], "duplicate_or_oob_city"), ([0, 1, 3], "duplicate_or_oob_city"),
        ([False, 1, 2], "invalid_city_index"), ([0.0, 1, 2], "invalid_city_index"),
    ):
        result = _verify(adapter, _TRIANGLE, tour, refs, convention)
        assert not result["valid"] and result["error_code"] == code and result["tour_length"] is None

    with pytest.raises(ValueError, match="WRITEABLE"):
        matrix.setflags(write=True)
    tampered = matrix.copy()
    tampered[0, 1] = 0.0
    result = _verify(adapter, _TRIANGLE, [0, 1, 2], {**refs, "submitted_matrix": tampered}, convention)
    assert not result["valid"] and result["error_code"] == "candidate_mutated_input"

    mutating_hook = """def select_next_city(current_node, unvisited_nodes, distance_matrix):
    distance_matrix[0, 1] = 0.0
    return -distance_matrix[current_node, unvisited_nodes]
"""
    execution = _run(TSP_CONSTRUCTIVE, [_TRIANGLE], hook_code=mutating_hook)
    assert not execution["valid"] and execution["error_code"] == "candidate_mutated_input"


@pytest.mark.parametrize("template_id", _TEMPLATES)
@pytest.mark.parametrize("deadline", [500, 2000])
def test_tsp_validator_passes_gates_and_scale_invariance(template_id, deadline):
    design = build_interface_design(template_id)
    report = InterfaceValidator(solve_deadline_ms=deadline).validate(design)
    assert report.passed, report.failures
    assert [(gate["gate_id"], gate["passed"]) for gate in report.gates] == [(i, True) for i in range(1, 6)]
    assert report.diagnostics["gate3"]["n_instances"] == 3
    causal = report.diagnostics["gate4"]
    assert causal["prefer_A_first_action"] != causal["prefer_B_first_action"]
    assert causal["prefer_A_pre_postprocess_tour"] != causal["prefer_B_pre_postprocess_tour"]
    scale = report.diagnostics["gate5"]
    assert len(scale["stress_solve_ms"]) == 2 and max(scale["stress_solve_ms"]) <= deadline
    assert scale["scale_factors"] == [1e-3, 1.0, 1e3]
    assert scale["scale_actions_match"] and scale["scale_max_relative_drift"] <= 0.0005


class _LocalEvaluator:
    """Use the worker contract while allowing a patched runner in the test process."""

    def evaluate(self, **request):
        request["solve_deadline_ms"] = request.pop("instance_time_budget_ms")
        return _handle_request(request)


@pytest.mark.parametrize("template_id", _TEMPLATES)
@pytest.mark.parametrize("defect", ["constant", "ignored"])
def test_tsp_gate4_rejects_constant_or_ignored_scoring(template_id, defect, monkeypatch):
    design = build_interface_design(template_id)
    override = None
    if defect == "constant":
        signature = ", ".join(design.hook_signature)
        override = f"def {design.hook_name}({signature}):\n    return np.zeros(len(unvisited_nodes))\n"
    else:
        spec = get_template_spec(template_id, "v1")
        node_argument = spec.hook_signature.index("unvisited_nodes")

        def ignore_candidate(matrix, _hook, **options):
            return spec.runner(matrix, lambda *args: -args[node_argument], **options)

        monkeypatch.setitem(TEMPLATE_REGISTRY, (template_id, "v1"), replace(spec, runner=ignore_candidate))
    report = InterfaceValidator(evaluator=_LocalEvaluator()).validate(design, hook_code_override=override)
    assert not report.passed
    assert [(f.gate_id, f.error_code) for f in report.failures] == [(4, "hook_not_causally_effective")]


@pytest.mark.parametrize("template_id", _TEMPLATES)
def test_tsp_strict_hook_output_requires_finite_one_dimensional_scores(template_id):
    design = build_interface_design(template_id)
    header = f"def {design.hook_name}({', '.join(design.hook_signature)}):\n"
    for scores, code in (
        ("np.zeros((len(unvisited_nodes), 1))", "invalid_return"),
        ("np.full(len(unvisited_nodes), np.inf)", "nonfinite_objective"),
    ):
        response = _run(template_id, [_TRIANGLE], hook_code=f"{header}    return {scores}\n")
        assert not response["valid"] and response["error_code"] == code


def test_tsp_adapter_compatible_with_all_tsplib_profile_references():
    suite = load_profile_suite(BENCHMARK_ID, "tsp_ext_tsplib_euc2d", split="heldout")
    assert len(suite["instances"]) == 18 and suite["distance_convention"] == "euc_2d_nint"
    adapter = _adapter()
    for instance in suite["instances"]:
        _, refs = adapter.prepare_inputs(instance, "tsplib_euc_2d")
        result = _verify(adapter, instance, instance["opt_tour"], refs, "tsplib_euc_2d")
        assert result["valid"], instance["instance_id"]
        assert result["tour_length"] == instance["reference_objective"]


def test_tsp_m31_dev_36_offline_smoke():
    suite = load_m31_suite("tsp_m31_dev_36")
    instances = suite["instances"]
    assert len(instances) == 36
    assert TSP_STRONG_COMPARATOR == "tsp_nn_2opt" and TSP_STRONG_COMPARATOR in TSP_SOLVER_CATALOG
    for template_id in _TEMPLATES:
        result = _run(template_id, instances, solve_deadline_ms=500, capture_merge_sequence=True)
        assert result["completed"], result.get("error_detail")
        assert len(result["records"]) == len(instances)
        for instance, record in zip(instances, result["records"]):
            assert record["instance_id"] == instance["instance_id"] and record["protocol_id"] == TSP_PROTOCOL_ID
            assert record["hook_call_count"] == instance["size"] - (1 if template_id == TSP_CONSTRUCTIVE else 2)
            assert record["first_action"] == record["construction_actions"][0]
            assert record["anytime_curve"]["500"] == pytest.approx(record["tour_length"], rel=1e-12)
            if template_id == TSP_CONSTRUCTIVE:
                assert record["tour"] == record["pre_postprocess_tour"]
                assert record["tour_length"] == pytest.approx(instance["reference_objective"], abs=1e-8)
            else:
                before = verify_tsp_solution(instance, record["pre_postprocess_tour"])
                assert before["valid"] and record["tour_length"] <= before["tour_length"]
        if template_id == TSP_GUIDED_INSERTION:
            first = instances[0]
            (matrix,), _ = _adapter().prepare_inputs(first, suite["distance_convention"])
            reference, _ = solve_tsp_farthest_insertion(matrix)
            assert result["records"][0]["pre_postprocess_tour"] == reference
            assert any(record["two_opt_moves"] > 0 for record in result["records"])
