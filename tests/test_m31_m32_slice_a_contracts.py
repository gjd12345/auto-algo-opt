from __future__ import annotations

import subprocess
from dataclasses import replace

import pytest

from agent_skill_loop.interface_design import (
    LEGACY_CVRP_PROTOCOL_ID,
    PROBLEM_ADAPTERS,
    PROBLEM_GATE_PROBES,
    TEMPLATE_REGISTRY,
    DynamicSubprocessEvaluator,
    FrozenInterfaceSolver,
    GateProbeResult,
    HookSpec,
    InterfaceDesign,
    InterfaceValidator,
    ProblemGateProbeSpec,
    ProblemRuntimeAdapter,
    TemplateSpec,
    build_interface_design,
    derive_outer_timeout_s,
    evaluate_frozen_interface_solver,
    hook_bundle_metadata,
    parse_hook_candidate,
    register_problem_adapter,
    register_problem_gate_probe,
    register_template,
)
from agent_skill_loop.interface_design import runtime
from agent_skill_loop.interface_design.contracts import sha256_text
from agent_skill_loop.interface_design.eval_worker import _handle_request

FAMILY = "slice_a_fixture"
PROTOCOL = "slice-a-fixture/v1"
TEMPLATE = "slice_a_mock"
SOURCES = {
    "choose": "def choose(items):\n    return items\n",
    "score": "def score(value):\n    return value\n",
}
SPECS = (HookSpec("choose", ("items",), "items"), HookSpec("score", ("value",)))


def _runner(items, hooks, *, time_budget_ms, capture_merge_sequence, **_options):
    action = int(hooks["choose"](items)[0])
    value = hooks["score"](action)
    meta = {"hook_call_count": 2, "budget_exhausted": time_budget_ms == 1}
    if capture_merge_sequence:
        meta["first_action"] = action
    return (None if value == -1 else value), meta


def _failure(code, detail, _instance, _refs):
    return {"valid": False, "fixture_score": None, "error_code": code, "error_detail": detail, "verify_ms": 0.0}


@pytest.fixture
def mock_interface(monkeypatch):
    from agent_skill_loop.interface_design import templates, validator

    templates._load_interface_extensions(probes=True)
    for module, registry in ((runtime, runtime.PROBLEM_ADAPTERS),):
        monkeypatch.setattr(module, "PROBLEM_ADAPTERS", dict(registry))
    monkeypatch.setattr(templates, "TEMPLATE_REGISTRY", dict(templates.TEMPLATE_REGISTRY))
    monkeypatch.setattr(validator, "PROBLEM_GATE_PROBES", dict(validator.PROBLEM_GATE_PROBES))
    register_problem_adapter(ProblemRuntimeAdapter(
        FAMILY, lambda instance, _: ((instance["items"],), {}),
        lambda _instance, value, _refs, **_: {"valid": True, "fixture_score": value, "verify_ms": 0.0},
        _failure, protocol_id=PROTOCOL, objective_key="fixture_score",
        record_fields=lambda _solution, _verification, meta, capture: (
            {"first_action": meta.get("first_action")} if capture else {}
        ),
    ))
    template = TemplateSpec(
        TEMPLATE, "v1", FAMILY, "fixture", "choose", ("items",), frozenset({"none"}),
        _runner, "Fixture task", "\n".join(SOURCES.values()), SOURCES["choose"], sha256_text("fixture"),
        protocol_id=PROTOCOL, hook_specs=SPECS, baseline_hook_implementations=SOURCES,
    )
    register_template(template)
    return template


def _request(*instances, **overrides):
    return {
        "template_id": TEMPLATE, "template_version": "v1", "problem_family": FAMILY,
        "protocol_id": PROTOCOL, "hook_implementations": SOURCES, "instances": instances, **overrides,
    }


def _instance(instance_id, value):
    return {"instance_id": instance_id, "protocol_id": PROTOCOL, "items": [value]}


def _frozen(template, design):
    return FrozenInterfaceSolver(
        "frozen", "Fixture", FAMILY, "fixture", TEMPLATE, "v1",
        template.template_source_sha256, "none", {}, "choose", SOURCES["choose"], sha256_text(SOURCES["choose"]),
        design.design_sha256, "fixture", "fixture", protocol_id=PROTOCOL,
        hook_specs=SPECS, hook_implementations=dict(SOURCES),
    )


def test_legacy_templates_and_manifest_schema_are_unchanged():
    expected = {
        "cvrp_sequential_construct": "e1b126be7cc2752bd51ec40f3df22109dc346caa454651c9dba78e50db6e0232",
        "cvrp_parallel_merge_static": "3bca783d3de8eaf5ec4fe559c71f92ccd98afc89d1e69adeb56a85a2d18e53ac",
        "cvrp_parallel_merge_dynamic": "8aaa530513762011dad69eb798e4ec01e5b4c206b26a3bb974ce9a0febeb9af5",
        "cvrp_ruin_recreate": "07206f68a07e520fb4099bf9c49e8b5bda881e4678a16b861fba60aa8aacea42",
    }
    for name, digest in expected.items():
        template = TEMPLATE_REGISTRY[(name, "v1")]
        assert template.template_source_sha256 == digest
        assert template.effective_protocol_id == LEGACY_CVRP_PROTOCOL_ID
        design = build_interface_design(name)
        payload = design.to_dict()
        assert payload["schema_version"] == "m2-interface-design/v1"
        assert payload == InterfaceDesign.from_dict(payload).to_dict()
        assert {"hook_specs", "hook_implementations", "bundle_hash", "protocol_id"}.isdisjoint(payload)
        frozen = FrozenInterfaceSolver(
            name, name, "cvrp", design.paradigm, name, "v1", digest, "none", {},
            design.hook_name, design.baseline_hook_code, design.baseline_hook_sha256,
            design.design_sha256, "fixture", "fixture",
        ).to_dict()
        assert frozen["schema_version"] == "m2-frozen-interface-solver/v1"
        assert frozen == FrozenInterfaceSolver.from_dict(frozen).to_dict()
        assert {"hook_specs", "hook_hashes", "bundle_hash", "protocol_id"}.isdisjoint(frozen)


def test_bundle_metadata_and_frozen_replay_fail_closed(mock_interface, monkeypatch):
    design = build_interface_design(TEMPLATE)
    assert "choose(items), score(value)" in design.hook_task_description
    assert parse_hook_candidate(TEMPLATE, "v1", mock_interface.default_template_program) == SOURCES
    with pytest.raises(ValueError, match="invalid_hook_bundle_program"):
        parse_hook_candidate(TEMPLATE, "v1", "\n".join([*SOURCES.values(), SOURCES["choose"]]))
    assert InterfaceDesign.from_dict(design.to_dict()) == design
    hashes = hook_bundle_metadata(SPECS, SOURCES)
    assert hook_bundle_metadata(SPECS, dict(reversed(list(SOURCES.items())))) == hashes
    assert hook_bundle_metadata(tuple(reversed(SPECS)), SOURCES)["bundle_hash"] != hashes["bundle_hash"]
    frozen = _frozen(mock_interface, design)
    payload = frozen.to_dict()
    assert payload["schema_version"] == "frozen-interface-solver/v2"
    assert payload["bundle_hash"] == hashes["bundle_hash"]
    assert FrozenInterfaceSolver.from_dict(payload) == frozen
    payload["hook_implementations"]["score"] = SOURCES["choose"]
    with pytest.raises(ValueError, match="hook_hashes_mismatch"):
        FrozenInterfaceSolver.from_dict(payload)
    monkeypatch.setattr(runtime._FROZEN_WORKER, "call", lambda request, *, timeout_s: _handle_request(request))
    assert evaluate_frozen_interface_solver(frozen, _instance("zero", 0))["objective"] == 0.0
    with pytest.raises(ValueError, match="protocol_id_mismatch"):
        evaluate_frozen_interface_solver(frozen, _instance("zero", 0), protocol_id="wrong")
    frozen.hook_implementations["score"] = SOURCES["choose"]
    with pytest.raises(ValueError, match="hook_hashes_mismatch"):
        evaluate_frozen_interface_solver(frozen, _instance("zero", 0))


def test_worker_distinguishes_zero_none_mismatched_protocol_and_strict_output(mock_interface):
    good, missing = _instance("zero", 0), _instance("missing", -1)
    success = _handle_request(_request(good))
    assert success["valid"] and success["completed"] and success["objective"] == 0.0
    result = _handle_request(_request(good, missing, good))
    assert not result["valid"] and result["objective"] is None
    assert [r["instance_id"] for r in result["records"]] == ["zero", "missing", "zero"]
    assert result["ordered_instance_objectives"] == [0.0, None, 0.0]
    assert result["records"][1]["error_code"] == "missing_objective"
    mismatch = _handle_request(_request(good, protocol_id="wrong"))
    assert mismatch["error_code"] == "protocol_id_mismatch" and mismatch["records"] == []
    wrong_family = _handle_request(_request(good, problem_family="wrong"))
    assert wrong_family["error_code"] == "problem_family_mismatch"
    mismatched_instance = _handle_request(_request(good, {**good, "protocol_id": "wrong"}))
    assert mismatched_instance["error_code"] == "protocol_id_mismatch"
    wrong_shape = {**SOURCES, "choose": "def choose(items):\n    return [0, 0]\n"}
    assert _handle_request(_request(good, hook_implementations=wrong_shape))["error_code"] == "invalid_return"
    assert _handle_request(_request(good, hook_implementations=wrong_shape, strict_hook_outputs=False))["valid"]
    nonfinite = {**SOURCES, "score": "def score(value):\n    return np.inf\n"}
    assert _handle_request(_request(good, hook_implementations=nonfinite))["error_code"] == "nonfinite_objective"
    exhausted = _handle_request(_request(good, solve_deadline_ms=1))["records"][0]
    assert exhausted["valid"] and not exhausted["completed"] and exhausted["timeout_kind"] == "solve_deadline"


def test_outer_timeout_covers_full_serial_batch(monkeypatch):
    assert derive_outer_timeout_s(24, 500) == 20
    assert derive_outer_timeout_s(24, 2000) == 63

    class FakeWorker:
        def communicate(self, *, input, timeout):
            assert timeout == 63
            raise subprocess.TimeoutExpired("mock", timeout)

    worker = FakeWorker()
    killed = []
    monkeypatch.setattr(runtime.subprocess, "Popen", lambda *_args, **_kwargs: worker)
    monkeypatch.setattr(runtime, "kill_process_tree", killed.append)
    response = DynamicSubprocessEvaluator().evaluate(
        template_id=TEMPLATE, template_version="v1", hook_implementations=SOURCES,
        instances=[_instance(str(i), 0) for i in range(24)], solve_deadline_ms=2000,
    )
    assert killed == [worker]
    assert response["error_code"] == "candidate_timeout"
    assert response["timeout_kind"] == "outer_worker" and response["outer_timeout_s"] == 63


def test_registered_probes_receive_named_hooks_and_pinned_protocol(mock_interface):
    def gate4(context):
        alternate = {**SOURCES, "choose": "def choose(items):\n    return [1]\n"}
        a = context.evaluate([_instance("probe", 0)], capture_merge_sequence=True)
        b = context.evaluate([_instance("probe", 0)], hook_implementations=alternate, capture_merge_sequence=True)
        assert a["records"][0]["first_action"] == 0
        assert b["records"][0]["first_action"] == 1
        return GateProbeResult({"action_differs": True})

    def gate5(context, records):
        assert context.protocol_id == PROTOCOL and context.solve_deadline_ms == 2000
        return GateProbeResult({"zero_survives_scale": records[0]["objective"] == 0})

    register_problem_gate_probe(ProblemGateProbeSpec(
        FAMILY, PROTOCOL, lambda _: [_instance("tiny", 0)], gate4,
        lambda _: [_instance("stress", 0)], gate5, template_key=(TEMPLATE, "v1"),
    ))

    class LocalEvaluator:
        def evaluate(self, **request):
            assert request["protocol_id"] == PROTOCOL
            request["solve_deadline_ms"] = request.pop("instance_time_budget_ms")
            return _handle_request(request)

    validator = InterfaceValidator(evaluator=LocalEvaluator(), solve_deadline_ms=2000)
    design = build_interface_design(TEMPLATE)
    report = validator.validate(design, hook_code_override=mock_interface.default_template_program)
    assert report.passed and len(report.gates) == 5
    assert report.diagnostics["gate4"]["action_differs"]
    assert report.diagnostics["gate5"]["zero_survives_scale"]
    assert report.diagnostics["hook_bundle"] == hook_bundle_metadata(SPECS, SOURCES)
    mismatch = validator.validate(replace(design, protocol_id="wrong"))
    assert not mismatch.passed and mismatch.failures[0].error_code == "protocol_id_mismatch"
