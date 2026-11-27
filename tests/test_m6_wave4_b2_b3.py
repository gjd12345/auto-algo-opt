"""Offline verification of the Wave 4 diagnostic and memory gates."""

from __future__ import annotations

import ast
import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

import pytest

from agent_skill_loop.interface_design import templates
from agent_skill_loop.interface_design.validator import InterfaceValidator
from agent_skill_loop.memory import MemoryAPI, MemoryEntry
from agent_skill_loop.memory.auto_dream import auto_dream, evidence_digest
from agent_skill_loop.memory.retrieval_m35 import admission_allowed
from research_agent import AgentConfig, run_research_agent
from research_agent.sandbox_worker import _execute_sandbox_script
from research_agent.tools.math_sandbox import MathSandboxTool
from research_agent.tools.session_tools import SessionRunnerTool


_SUBMIT = {"action": "submit_plan", "direction": "Evaluate a ranking change", "hypothesis": "Rankings differ."}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_bytes())


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def _sandbox(script: str) -> dict[str, Any]:
    return {"action": "call_tool", "tool": "run_math_sandbox", "arguments": {"script": script}}


def test_sandbox_read_only_builtins_keep_reflection_and_import_guards() -> None:
    outcome = _execute_sandbox_script("RESULT = {'length': len(repr([1])), 'int': int(isinstance(1, int))}")
    assert outcome["result"] == {"length": 3, "int": 1}

    for script, name in (
        ("RESULT = dir()", "dir"),
        ("RESULT = globals()", "globals"),
        ("RESULT = eval('42')", "eval"),
        ("import os\nRESULT = 0", "os"),
        ("RESULT = np.__version__", "__version__"),
    ):
        with pytest.raises(ValueError, match=name):
            _execute_sandbox_script(script)


@pytest.mark.parametrize(
    ("script", "detail"),
    [
        ("RESULT = dir()", "dir"),
        ("import os\nRESULT = 1", "os"),
        ("print(3)", "result"),
        ("RESULT = {'distance': float('nan'), 'ratio': float('inf')}", "finite"),
        ("RESULT = 'three'", "finite"),
        ("RESULT = 1 / 0", "division"),
        ("RESULT = {", "syntax"),
    ],
)
def test_sandbox_repair_hint_records_exact_failure(tmp_path: Path, script: str, detail: str) -> None:
    response = MathSandboxTool(tmp_path).run(script=script)
    hint = response["repair_hint"]
    assert detail in hint.lower()
    assert _read_json(tmp_path / response["artifact_ref"])["repair_hint"] == hint
    for helper in (
        "np", "math", "load_dev_suite", "eval_hook", "eval_baseline", "slice_stats",
        "scale_invariance_audit", "radial_share_stats", "RESULT =",
    ):
        assert helper in hint
    key_hint = MathSandboxTool(tmp_path).run(script="insts = load_dev_suite(max_instances=1)\nRESULT = {'d': len(insts[0]['distance_matrix'])}")["repair_hint"]
    assert "customer_coordinates" in key_hint and "distance_matrix" in key_hint
    from research_agent.tools.math_sandbox import _repair_hint
    attr_hint = _repair_hint({"ok": False, "error_code": "ValueError", "error_detail": "forbidden_attribute:np.linspace"}, set(), result_truncated=False)
    assert "np.zeros" in attr_hint and "np.linspace" in attr_hint


@pytest.mark.parametrize(("mode", "repair"), [("sandbox_only", False), ("slice_only", False), ("sandbox_only", True)])
def test_strict_diagnostic_gate_blocks_submit_and_cap_until_valid_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str, repair: bool,
) -> None:
    plans = []

    def fake_round(_tool: SessionRunnerTool, **plan: Any) -> dict[str, Any]:
        plans.append(plan)
        return {
            "session_status": "RUNNING",
            "stop_reason": "stagnation_early_stop" if plan["round_id"] == 1 else None,
            "frozen_solver": {"solver_id": f"w4-solver-{plan['round_id']}"},
            "dev_eval": {
                "penalized_mean_objective": 5.0, "valid_count": 1, "completion_rate": 1.0,
                "all_feasible": True, "records": [],
            },
        }

    monkeypatch.setattr(SessionRunnerTool, "run_round", fake_round)
    decisions = []
    repaired_steps = [
        _SUBMIT, _SUBMIT, _sandbox("RESULT = 'invalid'"), _SUBMIT,
        _sandbox("RESULT = {'delta': 1 - 1}"), _SUBMIT,
    ]

    class Driver:
        def decide_step(self, *, round_id, phase, step_index, messages, last_tool_result):
            if phase == "reflect":
                return {"action": "finish_round"}
            if round_id == 1:
                return _SUBMIT
            decisions.append(step_index)
            if repair and step_index in (3, 4):
                assert last_tool_result["repair_hint"]
            if repair and step_index == 4:
                assert last_tool_result["error_code"] == "stagnation_diagnostic_required"
            return repaired_steps[step_index] if repair else _SUBMIT

    config = AgentConfig(
        run_id="w4-strict-diagnostic", output_dir=str(tmp_path), max_rounds=2,
        outer_requests_per_round_cap=2, archive_feedback_enabled=False, kb_enabled=False,
        stagnation_diagnostic_mode=mode, strict_diagnostic_gate=True,
    )
    summary = run_research_agent(config, driver=Driver())
    checkpoint = _read_json(tmp_path / "agent_checkpoint.json")
    assert decisions == list(range(6))
    assert checkpoint["gate_bypass_count"] == 0
    assert checkpoint["gate_bypass_events"] == []
    assert not any(plan.get("diagnostic_bypassed_on_cap") for plan in plans)
    assert [plan["round_id"] for plan in plans] == ([1, 2] if repair else [1])
    if repair:
        assert summary["completed_rounds"] == [1, 2]
        assert checkpoint["sandbox_success_count"] == 1
        assert plans[-1]["direction"] == _SUBMIT["direction"]
        evidence = _read_json(tmp_path / "agent_artifacts" / "round_0002_dev_eval.json")
        assert evidence["sandbox_ref"] == checkpoint["last_sandbox_ref"]
    else:
        assert summary["final_phase"] == "budget_stopped"
        assert checkpoint["phase"] == "budget_stopped"
        assert checkpoint["round_plan_args"] is None


def test_auto_dream_c2_tags_and_rejects_unsafe_transfer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    template_id = "cvrp_parallel_merge_static"
    linear = templates.CLASSIC_CW_STATIC_HOOK_CODE
    quadratic = linear.replace(
        "    return distance_matrix",
        "    size = len(demands)\n"
        "    total = 0\n"
        "    for i in range(size):\n"
        "        for j in range(size):\n"
        "            total += (i + j) % 2\n"
        "    return 0.0 * total + distance_matrix",
    )
    scope = {
        "problem": "cvrp_construct", "interface_id": template_id,
        "fleet_policy": "unconstrained", "evaluator_version": "wave4-fixture",
    }
    codes = {"linear": linear, "quadratic": quadratic, "insight": linear}
    anchors = {
        name: {
            "code_sha256": hashlib.sha256(code.encode()).hexdigest(),
            "canonical_ast_sha256": hashlib.sha256(ast.unparse(ast.parse(code)).encode()).hexdigest(),
        }
        for name, code in codes.items()
    }
    facts = {
        **scope,
        "interface_selection": {"template_id": template_id, "template_version": "v2"},
        "evidence_refs": [f"evaluation:{name}" for name in codes],
        "candidates": [
            {"evaluation_id": name, "valid": True, "code": code, **anchors[name]}
            for name, code in codes.items()
        ],
    }
    digest = evidence_digest(facts)
    source = tmp_path / "source_memory"
    api = MemoryAPI(source, json_only=True)
    claims = []
    for name, code in codes.items():
        anchor = anchors[name]
        reference = f"evaluation:{name}"
        is_solution = name != "insight"
        body = "**Why:** Pair scores affect the merge order.\n**How to apply:** Compare under the same evaluator."
        if is_solution:
            body = f"## Execution\n```python\n{code}```\n**Reusable Experience:** Compare speeds across scales.\n{body}"
        written = api.write(
            MemoryEntry(
                name, f"Dev CVRP {name} admission fixture", "solution" if is_solution else "insight",
                scope["problem"], template_id, body, code_anchor=anchor,
            ),
            format_version=3,
            provenance={
                "evaluation_facts_sha256": digest, "evidence_ref": reference,
                "candidate_code_sha256": anchor["code_sha256"], "parent_version_id": "fixture-parent",
                "canonical_ast_sha256": anchor["canonical_ast_sha256"],
                "evaluator_hash": scope["evaluator_version"], "interface_id": template_id,
            },
        )
        claims.append({
            "claim_id": name, "source_reference": written["reference"], "applicability_scope": scope,
            "denominators": {"attempted": 2, "valid": 2}, "adverse_results": [], "contradictions": [],
            "code_anchor": anchor, "evaluation_facts_sha256": digest, "evidence_ref": reference,
        })

    probes = []

    def fake_probe_transport(self, design, instances, hook_code_override, hook_implementations):
        assert design.template_id == template_id and design.template_version == "v2"
        assert self.instance_time_budget_ms == 500.0
        assert hook_code_override in (linear, quadratic)
        probes.append(hook_code_override)
        return {"records": [
            {
                "instance_id": instance["instance_id"], "valid": True,
                "solve_ms": 10.0 if instance["size"] == 100 else 120.0 if hook_code_override == quadratic else 20.0,
            }
            for instance in instances
        ]}, 5.0

    # Stub elapsed timings at the transport boundary to exercise the actual C2
    # screen without making the result depend on the test host's CPU load.
    monkeypatch.setattr(InterfaceValidator, "_evaluate_synthetic_latency_probes", fake_probe_transport)
    artifact = tmp_path / "dev_evidence.json"
    _write_json(artifact, {"split": "dev", "evaluation_facts": facts, "claims": claims})
    output = tmp_path / "dream"
    result = auto_dream(
        dev_artifacts=[artifact], source_stores=[source], output_store=output / "memory", output_dir=output,
        require_c2_multiscale_admission=True,
    )
    assert set(probes) == {linear, quadratic}
    assert len(result["cards"]) == 2
    assert _read_json(output / "auto_dream_manifest.json")["rejected_candidates"] == result["rejected_candidates"]
    rejected, = result["rejected_candidates"]
    assert rejected["claim_id"] == "quadratic"
    assert rejected["rejection_reason"] == "c2_joint_latency_exceeded"

    dream = MemoryAPI(output / "memory", read_only=True)
    cards = [dream.read_version(item["reference"]) for item in result["cards"]]
    solution, = [card for card in cards if card["type"] == "solution"]
    assert solution["code_anchor"] == anchors["linear"]
    assert {card["type"] for card in cards} == {"solution", "insight"}
    provenance = solution["provenance"]
    assert provenance["c2_multiscale_screen_passed"] is True
    assert provenance["c2_probe_budget_ms"] == 500.0
    assert provenance["c2_latency_ratio_max"] == 2.0
    assert provenance["scale_range"] == [100, 200]
    assert set(provenance["spatial_regime"]) == {"clustered", "uniform"}
    assert set(provenance["demand_cv_regime"]) == {"cv0", "cv1_5"}
    assert set(provenance["eccentricity_regime"]) == {"center", "corner"}
    context = {
        **scope, "require_c2_multiscale_admission": True, "target_max_n": 200,
        "target_spatial_regime": "uniform", "target_demand_cv_regime": "cv0", "target_eccentricity_regime": "center",
    }
    assert admission_allowed(solution, context)
    assert not admission_allowed(solution, {**context, "target_max_n": 201})
    assert not admission_allowed(solution, {**context, "target_spatial_regime": "corridor"})
    assert not admission_allowed({**solution, "provenance": {**provenance, "c2_multiscale_screen_passed": False}}, context)
    assert not list(output.rglob("*.md"))

    _write_json(artifact, {"split": "dev", "evaluation_facts": facts, "claims": claims[1:]})
    all_failed = auto_dream(
        dev_artifacts=[artifact], source_stores=[source],
        output_store=tmp_path / "all_failed_memory", output_dir=tmp_path / "all_failed",
        require_c2_multiscale_admission=True,
    )
    insight, = all_failed["cards"]
    assert "/insight_" in insight["reference"]
    assert [row["claim_id"] for row in all_failed["rejected_candidates"]] == ["quadratic"]


def test_b3_audit_requires_actual_reads_and_published_writes(tmp_path: Path) -> None:
    from tools import run_m6_wave4_b2_b3 as runner

    arm = "arm_b3_3_full_closed_loop_c2_gated"
    kb_events = tmp_path / "agent_artifacts" / "kb_events.jsonl"
    kb_events.parent.mkdir()
    kb_events.write_text('{"op":"kb_search"}\n{"op":"kb_read","entry_id":"fixture"}\n', encoding="utf-8")
    session = tmp_path / "session_run"
    session.mkdir()
    ledger = session / "session.sqlite3"
    with closing(sqlite3.connect(ledger)) as con, con:
        con.executescript("""
            CREATE TABLE memory_searches(status TEXT);
            CREATE TABLE memory_reads(status TEXT, returned_chars INTEGER, reference TEXT);
            CREATE TABLE memory_writes(status TEXT, reference TEXT);
            INSERT INTO memory_searches VALUES ('hit');
            INSERT INTO memory_reads VALUES ('failed', 0, 'bad');
            INSERT INTO memory_writes VALUES ('proposed', NULL);
        """)
    empty = runner.audit_b3_cell(tmp_path, arm)
    assert empty["kb_search_count"] == empty["kb_read_count"] == empty["memory_search_count"] == 1
    assert empty["memory_read_count"] == empty["memory_write_count"] == 0
    assert empty["zero_read_alarm"] and empty["zero_write_alarm"] and not empty["attribution_valid"]

    with closing(sqlite3.connect(ledger)) as con, con:
        con.execute("INSERT INTO memory_reads VALUES ('complete', 20, 'fixture')")
        con.execute("INSERT INTO memory_writes VALUES ('published', 'fixture')")
    active = runner.audit_b3_cell(tmp_path, arm)
    assert active["memory_read_count"] == active["memory_write_count"] == 1
    assert not active["zero_read_alarm"] and not active["zero_write_alarm"] and active["attribution_valid"]


def test_mock_wave4_runs_keep_runtime_json_only_and_templates_immutable(tmp_path: Path) -> None:
    from tools import run_m6_wave4_b2_b3 as runner

    def template_hashes() -> dict[str, str]:
        return {
            version: templates.get_template_spec("cvrp_parallel_merge_static", version).template_source_sha256
            for version in ("v1", "v2")
        }

    original_hashes = template_hashes()
    template_source = Path(templates.__file__)
    original_source_hash = hashlib.sha256(template_source.read_bytes()).hexdigest()
    output, custody = tmp_path / "wave4", tmp_path / "custody"
    common = ["--output-dir", str(output), "--custody-dir", str(custody)]
    assert runner.main(["--stage", "b2_mock", *common]) == 0
    assert runner.main(["--stage", "b3_mock", *common]) == 0
    assert _read_json(output / "b2_sandbox" / "mock" / "b2_mock_report.json")["passed"] is True
    assert _read_json(output / "b3_memory_kb" / "mock" / "b3_mock_report.json")["passed"] is True
    assert runner.main(["--stage", "b2_pilot_mux", *common]) == 0
    pilot_mux = _read_json(output / "b2_sandbox" / "mock" / "b2_pilot_mux.json")
    assert pilot_mux["panes"] and all("--resume" in pane["command"] for pane in pilot_mux["panes"])
    assert not list(output.rglob("*.md"))
    assert template_hashes() == original_hashes
    assert hashlib.sha256(template_source.read_bytes()).hexdigest() == original_source_hash


def test_b3_offline_audit_requires_matching_seed_receipt_and_memory(tmp_path: Path) -> None:
    from tools import run_m6_wave4_b2_b3 as runner

    arm = runner.B3_ARMS[2]
    session = tmp_path / "session_run"
    round_dir = session / "rounds" / "round_0001"
    round_dir.mkdir(parents=True)
    _write_json(round_dir / "memory_consumption.json", {"compiled": [{"reference": "fixture"}]})
    with closing(sqlite3.connect(session / "session.sqlite3")) as con, con:
        con.executescript("""
            CREATE TABLE memory_searches(status TEXT);
            CREATE TABLE memory_reads(status TEXT, returned_chars INTEGER);
            CREATE TABLE memory_writes(status TEXT);
            INSERT INTO memory_reads VALUES ('complete', 20);
        """)

    def assert_failed_audit() -> None:
        audit = runner.audit_b3_cell(tmp_path, arm)
        assert audit["read_only_memory_intact"] is False
        assert audit["zero_injection_alarm"] is True
        assert audit["attribution_valid"] is False

    assert_failed_audit()
    receipt = tmp_path / "memory_seed.json"
    _write_json(receipt, {})
    assert_failed_audit()

    memory = tmp_path / "memory"
    asset = memory / "cvrp" / "fixture.json"
    asset.parent.mkdir(parents=True)
    _write_json(asset, {"fixture": True})
    assert_failed_audit()

    _write_json(receipt, {"cvrp/fixture.json": hashlib.sha256(asset.read_bytes()).hexdigest()})
    audit = runner.audit_b3_cell(tmp_path, arm)
    assert audit["read_only_memory_intact"] is True
    assert audit["zero_injection_alarm"] is False
    assert audit["attribution_valid"] is True


def test_b3_offline_roster_requires_seed_receipt_bound_to_fork(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace
    from tools import run_m6_wave4_b2_b3 as runner

    cell = next(cell for cell in runner.B3_CELLS if cell[2] == runner.B3_ARMS[2])
    fork = {"merged_kb": {}, "memory_assets": {"cvrp/fixture.json": "expected_digest"}}
    config = SimpleNamespace(output_dir=str(tmp_path))
    monkeypatch.setattr(runner, "_persisted_config", lambda *args, **kwargs: config)
    monkeypatch.setattr(runner, "_finished", lambda config: {})

    receipt = tmp_path / "memory_seed.json"
    for contents in (None, {"cvrp/fixture.json": "different_digest"}):
        if contents is not None:
            _write_json(receipt, contents)
        with pytest.raises(ValueError, match="wave4_b3_memory_seed_mismatch"):
            runner._lock_roster(tmp_path, [cell], SimpleNamespace(live=False), {}, fork=fork)


def test_b3_audit_flags_missing_injection_and_online_solution_c2_screening(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from contextlib import nullcontext
    from types import SimpleNamespace
    from agent_skill_loop.memory import auto_dream
    from tools import run_m6_wave4_b2_b3 as runner

    arm = "arm_b3_3_full_closed_loop_c2_gated"
    kb_events = tmp_path / "agent_artifacts" / "kb_events.jsonl"
    kb_events.parent.mkdir()
    kb_events.write_text('{"op":"kb_search"}\n{"op":"kb_read","entry_id":"fixture"}\n', encoding="utf-8")
    session = tmp_path / "session_run"
    round_dir = session / "rounds" / "round_0001"
    round_dir.mkdir(parents=True)
    with closing(sqlite3.connect(session / "session.sqlite3")) as con, con:
        con.executescript("""
            CREATE TABLE memory_searches(status TEXT);
            CREATE TABLE memory_reads(status TEXT, returned_chars INTEGER, reference TEXT);
            CREATE TABLE memory_writes(status TEXT, reference TEXT);
            INSERT INTO memory_searches VALUES ('hit');
            INSERT INTO memory_reads VALUES ('complete', 20, 'fixture');
            INSERT INTO memory_writes VALUES ('published', 'fixture');
        """)
    _write_json(round_dir / "memory_consumption.json", {"round_id": 1, "compiled": []})
    no_injection = runner.audit_b3_cell(tmp_path, arm)
    assert no_injection["zero_injection_alarm"] is True
    assert no_injection["attribution_valid"] is False

    _write_json(round_dir / "memory_consumption.json", {"round_id": 1, "compiled": [{"reference": "fixture"}]})
    injected = runner.audit_b3_cell(tmp_path, arm)
    assert injected["memory_injected_rounds"] == 1
    assert injected["zero_injection_alarm"] is False
    assert injected["attribution_valid"] is True

    linear = templates.CLASSIC_CW_STATIC_HOOK_CODE
    parent = templates.CLASSIC_CW_STATIC_HOOK_CODE.replace("return distance_matrix", "return 1.0 * distance_matrix")
    good_code = linear.replace("return distance_matrix", "return 0.99 * distance_matrix")
    parent_path = session / "parent.json"
    good_path = session / "good.json"
    _write_json(parent_path, {
        "schema_version": "eoh-skill/v1", "version_id": "v-parent", "problem": "cvrp_construct",
        "suite_hash": "sh", "evaluator_hash": "eh", "valid": True, "mean_objective": 100.0,
        "code": parent, "code_sha256": hashlib.sha256(parent.encode()).hexdigest(), "parent_version_id": None,
    })
    _write_json(good_path, {
        "schema_version": "eoh-skill/v1", "version_id": "v-good", "problem": "cvrp_construct",
        "suite_hash": "sh", "evaluator_hash": "eh", "valid": True, "mean_objective": 90.0,
        "code": good_code, "code_sha256": hashlib.sha256(good_code.encode()).hexdigest(), "parent_version_id": "v-parent",
    })
    monkeypatch.setattr(auto_dream, "screen_cvrp_c2_solution", lambda code, **kw: (
        ({"c2_multiscale_screen_passed": True, "c2_latency_ratio_max": 1.4, "c2_probe_budget_ms": 500.0}, None)
        if code == good_code else
        ({"c2_multiscale_screen_passed": False, "c2_latency_ratio_max": 9.0, "c2_probe_budget_ms": 500.0}, "c2_joint_latency_exceeded")
    ))
    monkeypatch.setattr("research_agent.tools.session_tools.load_skill", lambda p: SimpleNamespace(
        version_id="v-good" if Path(p) == good_path else "v-parent",
        problem="cvrp_construct", suite_hash="sh", evaluator_hash="eh", valid=True,
        mean_objective=90.0 if Path(p) == good_path else 100.0,
        code=good_code if Path(p) == good_path else parent,
        code_sha256=hashlib.sha256((good_code if Path(p) == good_path else parent).encode()).hexdigest(),
        parent_version_id="v-parent" if Path(p) == good_path else None,
    ))
    fake_runner = SessionRunnerTool.__new__(SessionRunnerTool)
    fake_runner.config = SimpleNamespace(
        memory_enabled=True, memory_online_writeback_enabled=True, memory_mode="m35_full",
        require_c2_multiscale_admission=True,
    )
    fake_runner.session_dir = session
    facts = {
        "problem": "cvrp_construct", "round_id": 1, "terminal_reason": None,
        "baseline": {"objective": 100.0}, "incumbent_before": {"ref": "parent.json"},
        "best_generated_ref": "good.json", "evidence_refs": ["evaluation:e1"],
        "interface_selection": {"template_id": "cvrp_parallel_merge_static", "template_version": "v2", "postprocess_mode": "relocate_2opt"},
        "candidates": [{"evaluation_id": "e1", "origin": "generated", "valid": True, "objective": 90.0,
                        "code": good_code, "code_sha256": hashlib.sha256(good_code.encode()).hexdigest()}],
    }
    monkeypatch.setattr("research_agent.tools.session_tools.opened", lambda *a, **kw: nullcontext((session, None)))
    monkeypatch.setattr("research_agent.tools.session_tools.session_db._require_run", lambda *a, **kw: None)
    monkeypatch.setattr("research_agent.tools.session_tools._memory_applicability", lambda *a, **kw: {
        "problem": "cvrp_construct", "interface_id": "cvrp_parallel_merge_static",
        "fleet_policy": "unconstrained", "evaluator_version": "eh", "n": (20, 40), "budget_ms": 500.0,
    })
    admitted = fake_runner._memory_action(facts)
    assert admitted["kind"] == "solution"
    monkeypatch.setattr(auto_dream, "screen_cvrp_c2_solution", lambda code, **kw: (
        {"c2_multiscale_screen_passed": False, "c2_latency_ratio_max": 9.0, "c2_probe_budget_ms": 500.0}, "c2_joint_latency_exceeded"
    ))
    downgraded = fake_runner._memory_action(facts)
    assert downgraded["kind"] == "insight"
    assert "c2_joint_latency_exceeded" in downgraded["body"]
