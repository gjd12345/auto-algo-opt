from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from agent_skill_loop.interface_design import (
    FrozenInterfaceSolver,
    InterfaceValidator,
    build_interface_design,
    evaluate_frozen_interface_solver,
    hook_bundle_metadata,
    parse_hook_candidate,
)
from agent_skill_loop.interface_design import cvrp_l3b, templates
from agent_skill_loop.interface_design.contracts import sha256_text
from agent_skill_loop.interface_design.cvrp_l3b import L3B_MOCK_CANDIDATES, L3B_TEMPLATE_KEY
from agent_skill_loop.interface_design.runtime import compile_hook_bundle, evaluate_hook_on_instance_inprocess
from agent_skill_loop.interface_design.templates import get_template_spec
from agent_skill_loop.interface_design.validator import _default_gate3_instances, build_gate4_l3_6cust_instance

LEGACY_KEY = ("cvrp_ruin_recreate", "v1")
LEGACY_HASH = "07206f68a07e520fb4099bf9c49e8b5bda881e4678a16b861fba60aa8aacea42"


def test_baseline_reproduces_legacy_dev_trajectory(monkeypatch):
    legacy, dual = (get_template_spec(*key) for key in (LEGACY_KEY, L3B_TEMPLATE_KEY))
    assert legacy.template_source_sha256 == LEGACY_HASH

    # Advance logical time at each ruin decision so checkpoints compare
    # trajectories at the same iterations, independent of machine load.
    clock = SimpleNamespace(now=0.0)
    clock.perf_counter = lambda: clock.now
    monkeypatch.setattr(templates, "time", clock)
    monkeypatch.setattr(cvrp_l3b, "time", clock)

    def evaluate(template, instance, mode):
        clock.now = 0.0
        hooks = compile_hook_bundle(template.effective_hook_specs, template.baseline_implementations())
        ruin = hooks["score_ruin_nodes"]

        def tick(*args):
            clock.now += 0.011
            return ruin(*args)

        hooks["score_ruin_nodes"] = tick
        return evaluate_hook_on_instance_inprocess(
            template_id=template.template_id,
            template_version=template.template_version,
            hook_fn=hooks,
            instance=instance,
            postprocess_mode=mode,
            template_options={"max_iters": 8},
            time_budget_ms=None,
        )

    for instance in _default_gate3_instances():
        for mode in ("none", "intra_2opt", "relocate_2opt"):
            before, after = (evaluate(template, instance, mode) for template in (legacy, dual))
            assert before["completed"] and after["completed"], (instance["instance_id"], mode, before, after)
            for field in ("routes", "objective", "iterations_completed", "anytime_curve"):
                assert after[field] == before[field], (instance["instance_id"], mode, field)


@pytest.mark.parametrize("deadline_ms", [500, 2000])
def test_l3b_gate_validation(deadline_ms):
    design = build_interface_design(*L3B_TEMPLATE_KEY)
    report = InterfaceValidator(solve_deadline_ms=deadline_ms).validate(
        design, hook_code_override=L3B_MOCK_CANDIDATES[-1],
    )
    assert report.passed, [failure.as_dict() for failure in report.failures]
    assert [gate["gate_id"] for gate in report.gates if gate["passed"]] == [1, 2, 3, 4, 5]
    ruin = report.diagnostics["gate4"]["ruin"]
    assert ruin["prefer_A"]["first_ruin_set"] == [1, 2, 3, 4]
    assert ruin["prefer_B"]["first_ruin_set"] == [3, 4, 5, 6]
    assert ruin["prefer_A"]["pre_postprocess_routes"] != ruin["prefer_B"]["pre_postprocess_routes"]
    recreate = report.diagnostics["gate4"]["recreate"]
    assert recreate["prefer_B"]["first_recreate_choice"] == [1, 1, 3]
    for label, target in (("prefer_A", 0), ("prefer_B", 1)):
        trace = recreate[label]
        customer, route_idx, position = trace["first_recreate_choice"]
        assert (customer, route_idx) == (1, target)
        partial = trace["pre_recreate_routes"]
        expected = [route.copy() for route in partial]
        expected[target].insert(position, customer)
        assert trace["pre_postprocess_routes"] == expected
    gate5 = report.diagnostics["gate5"]
    assert len(gate5["stress_instance_ids"]) == 2
    assert gate5["scale_factor"] == 1e-3
    assert gate5["scale_drift_pct"] >= 0.0


@pytest.mark.parametrize("hook_name", ["score_ruin_nodes", "score_recreate_action"])
def test_gate4_rejects_either_constant_hook(hook_name):
    design = replace(build_interface_design(*L3B_TEMPLATE_KEY), template_options={"max_iters": 1})
    hook = next(spec for spec in design.hook_specs if spec.name == hook_name)
    constant = (
        f"import numpy as np\n\ndef {hook.name}({', '.join(hook.signature)}):\n"
        f"    return np.zeros(len({hook.output_shape_arg}))\n"
    )
    report = InterfaceValidator(solve_deadline_ms=500).validate(
        design, hook_implementations={**design.hook_implementations, hook.name: constant},
    )
    assert not report.passed
    assert [(failure.gate_id, failure.error_code, failure.symbol) for failure in report.failures] == [
        (4, "hook_not_causally_effective", hook_name),
    ]


def test_frozen_bundle_detects_changes_to_either_hook():
    template = get_template_spec(*L3B_TEMPLATE_KEY)
    design = build_interface_design(*L3B_TEMPLATE_KEY)
    baseline = template.baseline_implementations()
    frozen = FrozenInterfaceSolver(
        solver_id="l3b-test",
        display_name="L3b test",
        problem_family=template.problem_family,
        paradigm=template.paradigm,
        template_id=template.template_id,
        template_version=template.template_version,
        template_source_sha256=template.template_source_sha256,
        postprocess_mode="none",
        template_options={"max_iters": 1},
        hook_name=template.hook_name,
        hook_code=baseline[template.hook_name],
        hook_code_sha256=sha256_text(baseline[template.hook_name]),
        design_sha256=design.design_sha256,
        origin_run="l3b-test",
        kb_release_id="fixture",
        protocol_id=template.protocol_id,
        hook_specs=template.hook_specs,
        hook_implementations=baseline,
    )
    payload = frozen.to_dict()
    assert payload["bundle_hash"] == hook_bundle_metadata(template.hook_specs, baseline)["bundle_hash"]
    replay = FrozenInterfaceSolver.from_dict(payload)
    assert replay == frozen
    instance = build_gate4_l3_6cust_instance()
    executed = evaluate_frozen_interface_solver(replay, instance, capture_merge_sequence=True)
    assert executed["completed"] and executed["merge_sequence"][0]["first_recreate_choice"]

    for spec, mock in zip(template.hook_specs, L3B_MOCK_CANDIDATES[:2], strict=True):
        replacement = parse_hook_candidate(*L3B_TEMPLATE_KEY, mock)[spec.name]
        swapped = {**baseline, spec.name: replacement}
        updated = hook_bundle_metadata(template.hook_specs, swapped)
        assert updated["bundle_hash"] != payload["bundle_hash"]
        tampered = {
            **payload,
            **updated,
            "bundle_hash": payload["bundle_hash"],
            "hook_implementations": swapped,
            "hook_code": swapped[template.hook_name],
            "hook_code_sha256": sha256_text(swapped[template.hook_name]),
        }
        with pytest.raises(ValueError, match="bundle_hash_mismatch"):
            FrozenInterfaceSolver.from_dict(tampered)

    replay.hook_implementations["score_recreate_action"] = swapped["score_recreate_action"]
    with pytest.raises(ValueError, match="hook_hashes_mismatch"):
        evaluate_frozen_interface_solver(replay, instance)
