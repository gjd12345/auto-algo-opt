"""Acceptance tests for the S1 stagnation gate and blinded ablation workflow."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pytest

from agent_skill_loop.request_budget import PersistentRequestBudget
from research_agent import AgentConfig, run_research_agent
from research_agent.contracts import AgentCheckpoint, atomic_write_json, sha256_file
from research_agent.loop import _build_initial_baseline_solver
from research_agent.prompts import AGENT_TOOL_SCHEMAS, build_round_system_prompt
from research_agent.tools.diagnostic_tools import DiagnosticTool
from research_agent.tools.ledger_tools import HypothesisLedgerTool
from research_agent.tools.math_sandbox import MathSandboxTool, _has_finite_numeric_evidence
from research_agent.tools.session_tools import SessionRunnerTool


_SUBMIT = {"action": "submit_plan", "direction": "Compare local scores", "hypothesis": "Scaling affects ranking."}
_SLICE = {"action": "call_tool", "tool": "diagnose_suite", "arguments": {}}
_SANDBOX = {"action": "call_tool", "tool": "run_math_sandbox", "arguments": {"script": "result = {'delta': 0}"}}
_BINDING_KEYS = ("artifact_ref", "artifact_sha256", "script_ref", "script_sha256")


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _config(path: Path, mode: str, *, cap: int = 6, legacy_gate: bool = False) -> AgentConfig:
    return AgentConfig(
        run_id="s1-test",
        output_dir=str(path),
        max_rounds=2,
        outer_requests_per_round_cap=cap,
        archive_feedback_enabled=False,
        kb_enabled=False,
        enable_stagnation_diagnostic_gate=legacy_gate,
        stagnation_diagnostic_mode=mode,
    )


def _round_outcome(round_id: int) -> dict[str, Any]:
    return {
        "session_status": "RUNNING",
        "stop_reason": "stagnation_early_stop" if round_id == 1 else None,
        "frozen_solver": {"solver_id": f"s1-solver-{round_id}"},
        "dev_eval": {
            "penalized_mean_objective": 5.0,
            "valid_count": 1,
            "completion_rate": 1.0,
            "all_feasible": True,
            "records": [],
        },
    }


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, True), (0.0, True), ({"nested": [False, {"delta": 0}]}, True),
        (None, False), (True, False), (float("nan"), False), (float("inf"), False),
        ("", False), ("{\"delta\": 0}", False), ("[0, 1...[TRUNCATED]", False),
        ({}, False), ([], False), ({"flags": [False, True, None, "2"]}, False),
    ],
)
def test_numeric_evidence_requires_structured_finite_values(value: Any, expected: bool) -> None:
    assert _has_finite_numeric_evidence(value) is expected


def test_sandbox_persists_exact_script_and_result_bindings(tmp_path: Path) -> None:
    script = "left = 3\nright = 3\nresult = {'delta': left - right}\n"
    binding = MathSandboxTool(tmp_path).run(script=script)
    assert binding["ok"] is True
    assert (tmp_path / binding["script_ref"]).suffix == ".py"
    assert (tmp_path / binding["script_ref"]).read_bytes() == script.encode("utf-8")
    assert (tmp_path / binding["artifact_ref"]).suffix == ".json"
    for kind in ("script", "artifact"):
        assert sha256_file(tmp_path / binding[f"{kind}_ref"]) == binding[f"{kind}_sha256"]
    assert _read(tmp_path / binding["artifact_ref"])["result"] == {"delta": 0}


@pytest.mark.parametrize(
    ("mode", "legacy_gate", "wrong_tool", "required_tool"),
    [
        ("off", True, None, None),
        ("slice_only", False, _SANDBOX, _SLICE),
        ("sandbox_only", False, _SLICE, _SANDBOX),
        ("any", False, None, None),
        ("any", True, None, _SANDBOX),
    ],
)
def test_gate_precedence_and_designated_tool(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    legacy_gate: bool,
    wrong_tool: dict[str, Any] | None,
    required_tool: dict[str, Any] | None,
) -> None:
    plans = []

    def run_round(_self: SessionRunnerTool, **plan: Any) -> dict[str, Any]:
        plans.append(plan)
        return _round_outcome(plan["round_id"])

    monkeypatch.setattr(SessionRunnerTool, "run_round", run_round)
    monkeypatch.setattr(DiagnosticTool, "diagnose_suite", lambda *_a, **_kw: {"ok": True, "valid_count": 1})
    steps = []
    if wrong_tool is not None:
        steps.append(wrong_tool)
    if mode == "sandbox_only":
        steps.append({**_SANDBOX, "arguments": {"script": "print(42)\nresult = '[42]'"}})
    if required_tool is not None:
        steps.extend([_SUBMIT, required_tool])
    steps.append(_SUBMIT)

    class Driver:
        def decide_step(self, *, round_id, phase, step_index, messages, last_tool_result):
            if phase == "reflect":
                return {"action": "finish_round"}
            if round_id == 1:
                return _SUBMIT
            if step_index == 0:
                observation = json.loads(messages[0]["content"])
                assert bool(observation.get("trajectory_control", {}).get("diagnostic_required")) is bool(required_tool)
            if mode == "sandbox_only" and step_index == 2:
                assert last_tool_result["ok"] is True
                assert last_tool_result["has_finite_numeric_evidence"] is False
            if required_tool is not None and step_index == len(steps) - 2:
                assert last_tool_result["error_code"] == "stagnation_diagnostic_required"
                tools = ["diagnose_suite", "run_math_sandbox"] if mode == "any" else [required_tool["tool"]]
                assert last_tool_result["recommended_tools"] == tools
            return steps[step_index]

    summary = run_research_agent(_config(tmp_path, mode, legacy_gate=legacy_gate), driver=Driver())
    assert summary["completed_rounds"] == [1, 2]
    assert plans[1]["direction"] == _SUBMIT["direction"]
    assert _read(tmp_path / "agent_checkpoint.json")["gate_bypass_count"] == 0


def test_system_prompts_only_change_stagnation_guidance() -> None:
    kwargs = {
        "arm_id": "s1-common",
        "problem_family": "cvrp",
        "tools_enabled": True,
        "allowed_templates": ("cvrp_parallel_merge_static",),
        "allowed_postprocess_modes": ("none",),
        "instance_time_budget_ms": 500.0,
    }
    prompts = {
        mode: build_round_system_prompt(**kwargs, stagnation_diagnostic_mode=mode).splitlines()
        for mode in ("off", "slice_only", "sandbox_only")
    }
    slice_lines = set(prompts["slice_only"]) - set(prompts["off"])
    sandbox_lines = set(prompts["sandbox_only"]) - set(prompts["off"])
    off_lines = set(prompts["off"]) - set(prompts["slice_only"])
    assert len(off_lines) == len(slice_lines) == len(sandbox_lines) == 1
    assert "diagnose_suite" in next(iter(slice_lines))
    assert "run_math_sandbox" in next(iter(sandbox_lines))
    assert (
        [line for line in prompts["off"] if line not in off_lines]
        == [line for line in prompts["slice_only"] if line not in slice_lines]
        == [line for line in prompts["sandbox_only"] if line not in sandbox_lines]
    )
    assert {row["function"]["name"] for row in AGENT_TOOL_SCHEMAS} >= {"diagnose_suite", "run_math_sandbox"}


def test_verified_binding_survives_failed_calls_and_resume(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(SessionRunnerTool, "run_round", lambda _self, **plan: _round_outcome(plan["round_id"]))
    config = _config(tmp_path, "sandbox_only")
    ledger = HypothesisLedgerTool(tmp_path)
    ledger.propose(round_id=2, statement="Equal work yields a zero delta", hypothesis_id="H_delta")
    latest: dict[str, Any] = {}
    rejected = [
        {**_SANDBOX, "arguments": {"script": "result = '[0]'"}},
        {**_SANDBOX, "arguments": {"script": "result = 1 / 0"}},
    ]

    class Driver:
        def __init__(self, crash: bool) -> None:
            self.crash = crash

        def decide_step(self, *, round_id, phase, step_index, messages, last_tool_result):
            if phase == "diagnose":
                if round_id == 1:
                    return _SUBMIT
                if step_index == 1:
                    latest.update({key: last_tool_result[key] for key in _BINDING_KEYS})
                return [_SANDBOX, *rejected, _SUBMIT][step_index]
            if round_id == 1 or step_index > 0:
                return {"action": "finish_round"}
            assert last_tool_result["sandbox_ref"] == latest
            if self.crash:
                raise RuntimeError("interrupted before evidence citation")
            return {
                "action": "call_tool",
                "tool": "hypothesis_update",
                "arguments": {
                    "hypothesis_id": "H_delta",
                    "status": "supported",
                    "evidence_artifacts": [{"kind": "sandbox", "use_latest_sandbox": True}],
                },
            }

    with pytest.raises(RuntimeError, match="interrupted before evidence citation"):
        run_research_agent(config, driver=Driver(crash=True))
    ckpt_path = tmp_path / "agent_checkpoint.json"
    checkpoint = _read(ckpt_path)
    assert checkpoint["last_sandbox_ref"] == latest
    assert checkpoint["sandbox_success_count"] == 1
    assert len(checkpoint["sandbox_run_refs"]) == 3
    assert checkpoint["round_plan_args"]["sandbox_ref"] == latest
    assert _read(tmp_path / "agent_artifacts" / "round_0002_dev_eval.json")["sandbox_ref"] == latest

    summary = run_research_agent(config, driver=Driver(crash=False), resume=True)
    assert summary["completed_rounds"] == [1, 2]
    assert _read(ckpt_path)["last_sandbox_ref"] == latest
    assert _read(ckpt_path)["sandbox_success_count"] == 1
    assert _read(ckpt_path)["sandbox_run_refs"] == checkpoint["sandbox_run_refs"]
    evidence = HypothesisLedgerTool(tmp_path).list_records()[0]["evidence_artifacts"]
    assert {row["path"]: row["sha256"] for row in evidence} == {
        latest["script_ref"]: latest["script_sha256"],
        latest["artifact_ref"]: latest["artifact_sha256"],
    }


@pytest.mark.parametrize(("outer_cap", "reason"), [(3, "submit_after_two_blocks"), (2, "outer_step_cap")])
def test_bypass_records_actual_transition_once_after_resume(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, outer_cap: int, reason: str,
) -> None:
    config = _config(tmp_path, "sandbox_only", cap=outer_cap)
    attempted = []

    def interrupted_round(_self: SessionRunnerTool, **plan: Any) -> dict[str, Any]:
        if plan["round_id"] == 2 and not attempted:
            attempted.append(plan)
            raise RuntimeError("interrupted after gate transition")
        return _round_outcome(plan["round_id"])

    monkeypatch.setattr(SessionRunnerTool, "run_round", interrupted_round)

    class Driver:
        def decide_step(self, *, round_id, phase, step_index, messages, last_tool_result):
            if phase == "reflect":
                return {"action": "finish_round"}
            if round_id == 2 and step_index > 0:
                assert _read(tmp_path / "agent_checkpoint.json")["gate_bypass_count"] == 0
            return _SUBMIT

    with pytest.raises(RuntimeError, match="interrupted after gate transition"):
        run_research_agent(config, driver=Driver())
    before = _read(tmp_path / "agent_checkpoint.json")
    assert before["gate_bypass_count"] == 1
    assert [(event["round_id"], event["reason"]) for event in before["gate_bypass_events"]] == [(2, reason)]
    if reason == "outer_step_cap":
        assert "Fallback plan" in attempted[0]["direction"]
    else:
        assert attempted[0]["direction"] == _SUBMIT["direction"]

    assert run_research_agent(config, driver=Driver(), resume=True)["completed_rounds"] == [1, 2]
    after = _read(tmp_path / "agent_checkpoint.json")
    assert after["gate_bypass_count"] == 1
    assert after["gate_bypass_events"] == before["gate_bypass_events"]


def test_inspect_scripts_audits_numeric_evidence_and_detects_tampering(tmp_path: Path) -> None:
    from tools import run_s1_sandbox_ablation as runner

    sandbox = MathSandboxTool(tmp_path)
    numeric = sandbox.run(script="result = {'zero': 2 - 2}")
    shell = sandbox.run(script="result = '[0]'")
    checkpoint = AgentCheckpoint(
        last_sandbox_ref={key: numeric[key] for key in _BINDING_KEYS},
        sandbox_run_refs=[{key: binding[key] for key in _BINDING_KEYS} for binding in (numeric, shell)],
        sandbox_success_count=1,
        gate_bypass_count=1,
        gate_bypass_events=[{
            "round_id": 2, "reason": "outer_step_cap", "stagnation_diagnostic_mode": "sandbox_only",
            "round_diagnostic_blocks": 2,
        }],
    )
    atomic_write_json(tmp_path / "agent_checkpoint.json", checkpoint.to_dict())

    audit = runner.inspect_scripts(tmp_path)
    assert audit["errors"] == []
    assert audit["gate_bypass_count"] == audit["sandbox_success_count"] == 1
    by_ref = {row["artifact_ref"]: row for row in audit["scripts"]}
    assert by_ref[numeric["artifact_ref"]]["bindings_ok"] is True
    assert by_ref[numeric["artifact_ref"]]["finite_numeric_evidence"] is True
    assert by_ref[numeric["artifact_ref"]]["script"] == "result = {'zero': 2 - 2}"
    assert by_ref[numeric["artifact_ref"]]["result"] == {"zero": 0}
    assert by_ref[shell["artifact_ref"]]["bindings_ok"] is True
    assert by_ref[shell["artifact_ref"]]["finite_numeric_evidence"] is False

    numeric_script = tmp_path / numeric["script_ref"]
    original_script = numeric_script.read_bytes()
    numeric_script.write_text("result = 42", encoding="utf-8")
    tampered = runner.inspect_scripts(tmp_path)
    assert tampered["errors"]
    assert next(row for row in tampered["scripts"] if row["artifact_ref"] == numeric["artifact_ref"])["bindings_ok"] is False

    numeric_script.write_bytes(original_script)
    shell_artifact = tmp_path / shell["artifact_ref"]
    atomic_write_json(shell_artifact, {**_read(shell_artifact), "result": "replacement"})
    tampered = runner.inspect_scripts(tmp_path)
    assert tampered["errors"]
    assert next(row for row in tampered["scripts"] if row["artifact_ref"] == shell["artifact_ref"])["bindings_ok"] is False


def test_mock_seal_run_lock_unseal_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from tools import run_s1_sandbox_ablation as runner

    output_dir = tmp_path / "s1"
    observed_configs: dict[tuple[str, int], AgentConfig] = {}
    fixture_seed = "b5" * 32
    seeds = (20261124, 20261125)
    base_cli = ["--out-dir", str(output_dir), "--mock", "--seeds", *map(str, seeds)]

    def mock_run(config: AgentConfig, *, resume: bool) -> dict[str, Any]:
        assert config.mode == "mock" and not resume
        observed_configs[(config.arm_id, config.search_seed)] = config
        run_dir = Path(config.output_dir)
        atomic_write_json(run_dir / "agent_config.json", config.to_dict())
        budget = PersistentRequestBudget(run_dir / "agent_budget.sqlite3", config.total_request_cap, run_id=config.run_id)
        request = budget.reserve(purpose="planner", problem=config.problem_family, model=config.planner_model)
        assert request is not None
        budget.mark_sent(request)
        budget.finish(request, "complete", status=200)
        best_ref = "agent_artifacts/round_0001_frozen_solver.json"
        atomic_write_json(run_dir / best_ref, _build_initial_baseline_solver(config).to_dict())

        checkpoint = AgentCheckpoint(
            run_id=config.run_id, phase="completed", current_round=2, completed_rounds=[1],
            best_solver_manifest_ref=best_ref, best_dev_objective=1.0,
        )
        if config.stagnation_diagnostic_mode == "sandbox_only":
            binding = MathSandboxTool(run_dir).run(script="result = {'delta': 0}")
            checkpoint.last_sandbox_ref = {key: binding[key] for key in _BINDING_KEYS}
            checkpoint.sandbox_run_refs.append(checkpoint.last_sandbox_ref)
            checkpoint.sandbox_success_count = 1
        atomic_write_json(run_dir / "agent_checkpoint.json", checkpoint.to_dict())
        summary = {
            "run_id": config.run_id,
            "final_phase": "completed",
            "best_solver_manifest_ref": best_ref,
            "completed_rounds": [1],
            "sandbox_success_count": checkpoint.sandbox_success_count,
            "gate_bypass_count": 0,
            "gate_bypass_events": [],
        }
        atomic_write_json(run_dir / "research_summary.json", summary)
        return summary

    def mock_outcome(solver: Any, instance: dict[str, Any], *_args: Any, **kwargs: Any) -> dict[str, Any]:
        assert kwargs["solve_deadline_ms"] == 500.0
        sandbox = "sandbox_only" in solver.solver_id
        timed_out = sandbox and instance["size"] == 200
        return {
            "valid": True, "completed": not timed_out, "budget_exhausted": timed_out,
            "objective": float(instance["reference_objective"]) * (0.9 if sandbox else 1.0),
            "solve_ms": 500.0 if timed_out else 3.0,
            "exact_vehicle_count": not sandbox,
            "routes": [[0, 1, 0]], "demands": [2], "customer_coordinates": [[0, 0]],
        }

    monkeypatch.setattr(runner, "run_research_agent", mock_run)
    monkeypatch.setattr(runner, "evaluate_public_frozen_solver", mock_outcome)
    original_bootstrap = runner.paired_bootstrap_comparison
    bootstrap_calls = []

    def record_bootstrap(left, right, *, n_boot, seed):
        bootstrap_calls.append((len(left), len(right), n_boot, seed))
        return original_bootstrap(left, right, n_boot=n_boot, seed=seed)

    monkeypatch.setattr(runner, "paired_bootstrap_comparison", record_bootstrap)
    with TemporaryDirectory(prefix="s1-test-custody-") as temp_dir:
        custody = Path(temp_dir) / "custody"
        cli = [*base_cli, "--custody-dir", str(custody)]
        with monkeypatch.context() as seal:
            seal.setattr("secrets.token_hex", lambda _n: fixture_seed)
            assert runner.main(["seal-blind", *cli]) == 0
        assert runner.main(["emit-mux", *cli]) == 0
        panes = _read(output_dir / "mux_s1_pilot.json")["panes"]
        assert len({pane["id"] for pane in panes}) == 6
        for pane in panes:
            assert runner.main(pane["command"][2:]) == 0
        assert set(observed_configs) == {(arm, seed) for arm in runner.ARMS for seed in seeds}
        fields_to_ignore = {"run_id", "output_dir", "arm_id", "stagnation_diagnostic_mode"}
        for seed in seeds:
            configs = [observed_configs[(arm, seed)] for arm in runner.ARMS]
            shared = [{key: value for key, value in asdict(cfg).items() if key not in fields_to_ignore} for cfg in configs]
            assert shared[0] == shared[1] == shared[2]
        cfg = next(iter(observed_configs.values()))
        assert cfg.pinned_kb_release_id == "20261124-main-co-workbench-m4"
        assert len(cfg.allowed_templates) == 4
        assert cfg.total_request_cap == 36
        assert cfg.instance_time_budget_ms == 500.0
        assert cfg.dev_instance_count == 24
        assert runner.main(["inspect-scripts", *cli]) == 0
        assert runner.main(["lock-roster", *cli]) == 0
        lock = _read(output_dir / runner.LOCK)
        snapshot = output_dir / lock["roster"][0]["snapshot_ref"]
        original = snapshot.read_bytes()
        snapshot.write_bytes(original + b"\n")
        with pytest.raises(ValueError, match="snapshot.*mismatch"):
            runner.main(["unseal-eval", *cli])
        snapshot.write_bytes(original)
        assert runner.main(["unseal-eval", *cli]) == 0
        with pytest.raises(FileExistsError, match="already_consumed"):
            runner.main(["unseal-eval", *cli])
        assert runner.main(["report", *cli]) == 0

    report_path = output_dir / (runner.REPORT + ".json")
    report = _read(report_path)
    assert set(report["per_seed"]) == {
        "cvrp_s1_sandbox_blind_120", "cvrp_ext_cvrplib_abp_74", "cvrp_ext_cvrplib_x_100",
    }
    assert len(report["per_seed"]["cvrp_s1_sandbox_blind_120"]) == 6
    assert {value["sandbox_success_count"] for value in report["sandbox_audit"].values()} == {0, 1}
    contrasts = [
        row for row in report["contrasts"]
        if row["suite_id"] == runner.BLIND_SUITE_ID
        and row["left"] == "arm_s1_2_sandbox_only" and row["right"] == "arm_s1_0_free_tool"
    ]
    assert {row["seed"] for row in contrasts} == set(seeds)
    for row in contrasts:
        assert row["free_fleet"]["common_completed"]["n_pairs"] == 90
        assert row["free_fleet"]["penalized_2x"]["n_pairs"] == 120
        assert row["exact_k"]["common_completed"]["n_pairs"] == 0
        assert row["exact_k"]["penalized_2x"]["n_pairs"] == 120
        assert isinstance(row["free_fleet"]["common_completed"]["wilcoxon_p_holm"], float)
    assert {seed for _, _, _, seed in bootstrap_calls} == set(seeds)
    assert all(left_n == right_n <= 120 and count == 10000 for left_n, right_n, count, _ in bootstrap_calls)
    assert report["cross_seed_std"][runner.BLIND_SUITE_ID]["DeepSeek-V4.1-Flash"][
        "arm_s1_2_sandbox_only"
    ]["free_fleet"]["completion_rate"] == {"n_seeds": 2, "sample_std": 0.0}
    public_text = (output_dir / runner.EVALUATION).read_text(encoding="utf-8")
    assert fixture_seed not in public_text
    for field in ("customer_coordinates", "demands", "routes", "sealed_seed_token", "seed_token"):
        assert f'"{field}"' not in public_text
