"""Local acceptance tests for the Phase A trajectory controls."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pytest
from eoh import BaseProblem, LLMConfig
from eoh.config import EoHConfig
from eoh.eoh.eoh import EOH

from agent_skill_loop.interface_design import eval_worker, session_bridge
from agent_skill_loop.interface_design.dynamic_eoh import DynamicInterfaceProblem, MockEoHLLMServer
from agent_skill_loop.interface_design.planner import build_design_for_template
from agent_skill_loop.interface_design.runtime import (
    DynamicSubprocessEvaluator,
    capability_contract_dict,
    validate_hook_ast,
)
from agent_skill_loop.interface_design.templates import get_template_spec
from agent_skill_loop.interface_design.validator import InterfaceValidator, build_gate4_dual_action_instance
from agent_skill_loop.request_budget import PersistentRequestBudget
from research_agent import AgentConfig, run_research_agent
from research_agent.contracts import sha256_file
from research_agent.tools.ledger_tools import HypothesisLedgerTool
from research_agent.tools.session_tools import SessionRunnerTool


STATIC_TEMPLATE = "cvrp_parallel_merge_static"
STATIC_SIGNATURE = ("distance_matrix", "demands", "capacity", "i_idx", "j_idx")


def _score(expression: str) -> str:
    return f"def score_merge_static({', '.join(STATIC_SIGNATURE)}):\n    return {expression}\n"


def _worker_request(hook: str, **options: Any) -> dict[str, Any]:
    return {
        "template_id": STATIC_TEMPLATE,
        "template_version": "v1",
        "hook_code": hook,
        "instances": [build_gate4_dual_action_instance()],
        **options,
    }


def test_numpy_policy_matches_contract_and_worker() -> None:
    contract_args = {
        "template_id": STATIC_TEMPLATE, "template_version": "v1",
        "hook_name": "score_merge_static", "hook_signature": STATIC_SIGNATURE,
    }
    extended = capability_contract_dict(**contract_args)
    legacy = capability_contract_dict(**contract_args, allow_extended_numpy_whitelist=False)
    assert set(extended["allowed_numpy_attributes"]) - set(legacy["allowed_numpy_attributes"]) == {
        "tanh", "sinh", "cosh", "sign", "mod", "fmod", "remainder",
        "stack", "vstack", "dstack", "nan_to_num", "fill_diagonal", "bincount", "lexsort", "ix_",
        "argpartition", "triu", "tril", "flatnonzero", "searchsorted", "percentile", "quantile", "prod",
    }
    code = (
        f"def score_merge_static({', '.join(STATIC_SIGNATURE)}):\n"
        "    local = distance_matrix[np.ix_(i_idx, j_idx)]\n"
        "    np.fill_diagonal(local, 0.0)\n"
        "    return np.tanh(np.sum(local, axis=1))\n"
    )
    assert eval_worker._handle_request(_worker_request(code))["valid"] is True
    blocked = eval_worker._handle_request(_worker_request(code, allow_extended_numpy_whitelist=False))
    assert blocked["error_code"] == "forbidden_attribute"
    kwargs = {"hook_name": "score_merge_static", "expected_args": STATIC_SIGNATURE,
              "allow_extended_numpy_whitelist": False}
    assert validate_hook_ast(_score("math.fmod(2, 3)"), **kwargs) == ([], [])
    assert validate_hook_ast(_score("np.fmod(2, 3)"), **kwargs)[0]
    alias = _score("numeric.fmod(2, 3)").replace("    return", "    numeric = np\n    return")
    assert validate_hook_ast(alias, **kwargs)[0]

    mutate = code.replace("np.fill_diagonal(local,", "np.fill_diagonal(distance_matrix,")
    assert eval_worker._handle_request(_worker_request(mutate))["valid"] is False


@pytest.mark.parametrize("allow_extended", [False, True])
def test_numpy_policy_keeps_unsafe_identifiers_forbidden(allow_extended: bool) -> None:
    references = [f"np.{name}" for name in (
        "load", "save", "savetxt", "loadtxt", "genfromtxt", "fromfile", "tofile", "memmap",
        "ctypes", "ctypeslib", "testing", "distutils", "f2py", "lib", "random", "__dict__",
    )]
    references += ["distance_matrix.tofile", "getattr", "open", "exec", "eval", "__import__"]
    for reference in references:
        failures, _ = validate_hook_ast(
            _score(reference), hook_name="score_merge_static", expected_args=STATIC_SIGNATURE,
            allow_extended_numpy_whitelist=allow_extended,
        )
        assert failures, reference


def test_constant_screen_rejects_clamp_but_keeps_normal_scoring() -> None:
    clamp = _score("np.maximum(-np.ones_like(i_idx), 0.0)")
    result = eval_worker._handle_request(_worker_request(clamp, enable_degenerate_constant_screen=True))
    assert result["valid"] is False
    assert result["error_code"] == "degenerate_constant_output"
    assert result["records"] == []
    assert eval_worker._handle_request(_worker_request(clamp))["valid"] is True
    varied = _score("np.arange(len(i_idx), dtype=np.float64)")
    assert eval_worker._handle_request(_worker_request(varied, enable_degenerate_constant_screen=True))["valid"] is True


def test_constant_screen_tracks_bundle_hooks_independently(monkeypatch: pytest.MonkeyPatch) -> None:
    tpl = get_template_spec("cvrp_ruin_recreate_dual", "v1")
    specs = tpl.effective_hook_specs

    def unit(index: int, expression: str) -> str:
        spec = specs[index]
        return f"def {spec.name}({', '.join(spec.signature)}):\n    return {expression}\n"

    def evaluate_instance(**kwargs: Any) -> dict[str, Any]:
        hooks = kwargs["hook_fn"]
        for index, spec in enumerate(specs):
            # The ruin hook sees ties followed by a varying vector. Recreate
            # has zero or one action and must be ignored by the range test.
            sizes = (2, 3) if index == 0 else (0, 1)
            for size in sizes:
                args = [np.arange(size) if name == spec.output_shape_arg else 0 for name in spec.signature]
                hooks[spec.name](*args)
        return {"valid": True, "completed": True, "objective": 1.0}

    monkeypatch.setattr(eval_worker, "evaluate_hook_on_instance_inprocess", evaluate_instance)
    request = {
        "template_id": tpl.template_id, "template_version": "v1",
        "instances": [build_gate4_dual_action_instance()], "enable_degenerate_constant_screen": True,
        "hook_implementations": {
            specs[0].name: unit(0, "np.zeros(len(route_ids)) if len(route_ids) == 2 else np.arange(len(route_ids))"),
            specs[1].name: unit(1, "np.zeros(len(customer_idx))"),
        },
    }
    assert eval_worker._handle_request(request)["valid"] is True
    request["hook_implementations"][specs[0].name] = unit(0, "1e-13 * np.arange(len(route_ids))")
    rejected = eval_worker._handle_request(request)
    assert rejected["error_code"] == "degenerate_constant_output"
    assert specs[0].name in rejected["error_detail"]


def test_constant_screen_does_not_apply_to_scalar_hooks() -> None:
    tpl = get_template_spec("cvrp_sequential_construct", "v1")
    assert eval_worker._handle_request(_worker_request(
        tpl.default_baseline_hook_code, template_id=tpl.template_id, enable_degenerate_constant_screen=True,
    ))["valid"] is True


def test_n200_precedes_dev_and_skips_seed_origins(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, float]] = []
    gate = {"passed": True, "timeout_count": 0, "error_code": None}

    def latency(self: InterfaceValidator, _design: object, **kwargs: Any) -> dict[str, Any]:
        calls.append(("n200", self.instance_time_budget_ms))
        assert kwargs["hook_code_override"] == code
        return dict(gate)

    def dev(self: DynamicSubprocessEvaluator, **kwargs: Any) -> dict[str, Any]:
        calls.append(("dev", kwargs["solve_deadline_ms"]))
        return {"valid": True, "completed": True, "objective": 0.0}

    monkeypatch.setattr(InterfaceValidator, "validate_evolved_hook_n200_latency", latency)
    monkeypatch.setattr(DynamicSubprocessEvaluator, "evaluate", dev)
    design = build_design_for_template(STATIC_TEMPLATE, "v1")
    code = design.baseline_hook_code + "\n# Generated scoring hook.\n"
    problem = DynamicInterfaceProblem(
        design=design, instances=[build_gate4_dual_action_instance()], suite_id="test_dev",
        instance_time_budget_ms=240.0, n200_latency_multiplier=1.5, enable_n200_latency_screen=True,
    )
    assert problem.evaluate_detailed(code)["objective"] == 0.0
    assert calls == [("n200", 360.0), ("dev", 240.0)]
    gate.update(passed=False, timeout_count=1, error_code="candidate_timeout")
    calls.clear()
    failed = problem.evaluate_detailed(code)
    assert calls == [("n200", 360.0)]
    assert failed["valid"] is False and failed["completed"] is False
    assert failed["error_code"] == "n200_latency_exceeded"
    assert failed["n200_latency_diagnostics"]["error_code"] == "candidate_timeout"
    calls.clear()
    for origin in ("baseline", "explicit_parent", "population_seed"):
        assert problem.evaluate_detailed(code, origin=origin)["valid"]
    assert calls == [("dev", 240.0)] * 3
    calls.clear()
    for template_id, enabled in ((STATIC_TEMPLATE, False), ("tsp_constructive_step", True)):
        selected = build_design_for_template(template_id, "v1")
        problem = DynamicInterfaceProblem(
            design=selected, instances=[], suite_id="test_dev", enable_n200_latency_screen=enabled,
            instance_time_budget_ms=240.0,
        )
        assert problem.evaluate_detailed(selected.baseline_hook_code)["valid"]
    assert calls == [("dev", 240.0)] * 2


def test_session_behavior_evidence_is_comparable_only_for_complete_records(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    events = []
    monkeypatch.setattr(session_bridge, "solver_event", lambda _session, payload: events.append(payload))
    record = {
        "instance_id": "local-dev-1", "outcome_class": "completed", "valid": True, "completed": True,
        "exact_vehicle_count": True, "route_count": 2, "objective": 15.980135999,
    }

    def evaluate(_self: DynamicInterfaceProblem, _code: str, **_kwargs: object) -> dict:
        return {"valid": True, "objective": record["objective"], "records": [dict(record)]}

    monkeypatch.setattr(DynamicInterfaceProblem, "evaluate_detailed", evaluate)
    design = build_design_for_template(STATIC_TEMPLATE, "v1")
    log = tmp_path / "evaluations.jsonl"
    problem = session_bridge._SessionTrackedDynamicProblem(
        session={}, problem_id="cvrp_construct", suite_hash="suite-fingerprint", evaluator_hash="evaluator",
        design=design, instances=[build_gate4_dual_action_instance()], suite_id="test_dev", evaluation_log=log,
        instance_time_budget_ms=420,
    )

    def evidence() -> dict:
        problem.evaluate_detailed(design.baseline_hook_code)
        return events[-1]["evaluation"]["metrics"]["behavior_evidence"]

    first = evidence()
    record.update(solve_ms=123.0, objective=15.98013609)
    second = evidence()
    assert first["comparable"] is second["comparable"] is True
    assert first["behavior_signature"] == second["behavior_signature"]
    assert first["behavior_contract"] == {
        "mode": "dynamic_interface_instance_profile/v1", "template_id": STATIC_TEMPLATE,
        "template_version": "v1", "postprocess_mode": "none", "solve_deadline_ms": 420.0,
    }
    assert first["instances"][0]["sample_first"][0] == {
        "outcome_class": "completed", "feasible": True, "completed": True,
        "exact_k_feasible": True, "route_count": 2, "objective_r6": 15.980136,
    }
    record["completed"] = False
    partial = evidence()
    assert partial["status"] == "partial" and partial["comparable"] is False
    assert partial["behavior_signature"] is None
    assert json.loads(log.read_text(encoding="utf-8").splitlines()[-1])["evaluation"]["metrics"]["behavior_evidence"] == partial


def test_seed_source_reappearing_after_initialization_is_generated(monkeypatch: pytest.MonkeyPatch) -> None:
    origins: list[str] = []
    monkeypatch.setattr(session_bridge, "solver_event", lambda *_args: None)

    def evaluate(_self: DynamicInterfaceProblem, _code: str, *, origin: str) -> dict:
        origins.append(origin)
        return {"valid": True, "objective": 10.0}

    monkeypatch.setattr(DynamicInterfaceProblem, "evaluate_detailed", evaluate)
    design = build_design_for_template(STATIC_TEMPLATE, "v1")
    code = design.baseline_hook_code
    problem = session_bridge._SessionTrackedDynamicProblem(
        session={}, problem_id="cvrp_construct", suite_hash="local-dev", evaluator_hash="evaluator",
        design=design, instances=[], suite_id="test_dev",
    )
    problem.seed_origins[design.baseline_hook_sha256] = "baseline"

    def init_population(engine: EOH, _t0: float) -> tuple[list, int]:
        engine.problem.evaluate_detailed(code)
        return [], 0

    monkeypatch.setattr(EOH, "_init_population", init_population)
    engine = object.__new__(session_bridge._DynamicCandidateEoH)
    engine.problem = problem
    engine._init_population(0.0)
    problem.evaluate_detailed(code)
    assert origins == ["baseline", "generated"]


class _JournaledProblem(BaseProblem):
    template_program = "def score():\n    return 10.0\n"
    task_description = "Return a scalar objective."

    def __init__(self, journal: Path) -> None:
        super().__init__(timeout=15, n_processes=1)
        self.journal = journal

    def evaluate_program(self, program_str: str, callable_func: Callable[[], float]) -> float:
        objective = callable_func()
        row = {
            "evaluation_id": str(os.getpid()), "pid": os.getpid(),
            "origin": "baseline" if program_str == self.template_program else "generated",
            "evaluation": {"valid": True, "objective": objective},
        }
        with self.journal.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row) + "\n")
        return objective


def test_early_stop_uses_spawned_evaluations_and_stops_claiming_samples(tmp_path: Path) -> None:
    journal = tmp_path / "evaluations.jsonl"
    seed_path = tmp_path / "seeds.json"
    for name in ("samples", "pops", "pops_best"):
        (tmp_path / "results" / name).mkdir(parents=True)
    problem = _JournaledProblem(journal)
    seed_path.write_text(json.dumps([{"algorithm": "seed", "code": problem.template_program}]), encoding="utf-8")
    # Tie, improvement, tie, worse. The improvement resets the streak, and
    # the unused fifth response demonstrates that sampling actually stopped.
    scores = (10.0, 9.0, 9.0, 11.0, 1.0)
    mock_provider = MockEoHLLMServer([
        f"{{Candidate {index}.}}\n```python\ndef score():\n    value = {objective}\n    return value + {index} * 0\n```"
        for index, objective in enumerate(scores)
    ])
    logger = logging.getLogger("eoh")
    prior_handlers, prior_level = logger.handlers[:], logger.level
    try:
        config = EoHConfig(
            llm=LLMConfig(use_local=True, local_url=mock_provider.start(), timeout=3),
            pop_size=2, n_pop=1, operators=["m1"], max_sample_nums=8,
            use_seed=True, seed_path=str(seed_path), output_dir=str(tmp_path),
        )
        engine = session_bridge._StagnationAwareEoH(config, problem, evaluation_log=journal, no_jump_limit=2)
        with pytest.raises(session_bridge.StagnationEarlyStop):
            engine.run()
    finally:
        mock_provider.stop()
        for handler in list(logger.handlers):
            if handler not in prior_handlers:
                logger.removeHandler(handler)
                handler.close()
        logger.handlers[:] = prior_handlers
        logger.setLevel(prior_level)
    rows = [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines()]
    generated = [row for row in rows if row["origin"] == "generated"]
    assert [row["evaluation"]["objective"] for row in generated] == list(scores[:4])
    assert all(row["pid"] != os.getpid() for row in generated)
    assert mock_provider.call_count == 1 + len(generated)  # connection probe plus generations
    assert (tmp_path / "results/pops/population_generation_2.json").is_file()


def test_early_stop_collects_behavior_and_keeps_budget_open_for_fresh_round(tmp_path: Path) -> None:
    cfg = AgentConfig(
        run_id="m5-session", output_dir=str(tmp_path), max_rounds=2, total_request_cap=12,
        dev_instance_count=1, dev_instance_size=1, eoh_n_pop=1, eoh_max_sample_nums=4,
        early_stop_no_jump_requests=1, basin_restart_on_stagnation=True,
        model_routing_policy={"enabled": True},
    )
    budget = PersistentRequestBudget(tmp_path / "agent_budget.sqlite3", cfg.total_request_cap, run_id=cfg.run_id)
    runner = SessionRunnerTool(run_dir=tmp_path, config=cfg, budget=budget)
    plan = {
        "template_id": STATIC_TEMPLATE, "postprocess_mode": "none", "direction": "Check deterministic ties",
        "hypothesis": "A one-customer route has a fixed objective", "eval_dev_suite": False,
    }

    first = runner.run_round(round_id=1, **plan)
    assert first["stop_reason"] == "stagnation_early_stop"
    assert first["evaluation_facts"]["terminal_reason"] == "SUCCEEDED"
    candidates = [row for row in first["evaluation_facts"]["candidates"] if row["origin"] == "generated"]
    assert len(candidates) == 1 and candidates[0]["metrics"]["behavior_evidence"]["comparable"] is True
    assert budget.remaining > 0

    second = runner.run_round(round_id=2, is_final_round=True, fresh_template=True, **plan)
    assert second["stop_reason"] == "stagnation_early_stop"
    round_dir = runner.session_dir / "rounds/round_0002"
    selection = json.loads((round_dir / "plan.json").read_text(encoding="utf-8"))["interface_selection"]
    assert selection["fresh_template"] is True
    receipt = round_dir / "eoh_run/interface_seed_receipt.json"
    seed_receipt = json.loads(receipt.read_text(encoding="utf-8"))
    assert seed_receipt["reason"] == "fresh_template"
    assert seed_receipt["requested_inherited_seeds"] == seed_receipt["used_inherited_seeds"] == 0
    requests = budget.request_records()
    assert [row["purpose"] for row in requests] == ["eoh_probe", "eoh_generation"] * 2
    assert not any(row["state"] in {"reserved", "sent", "unknown"} for row in requests)


def test_outer_gate_resumes_and_caps_native_and_json_blocks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    plans: dict[int, dict[str, Any]] = {}

    def run_round(_self: SessionRunnerTool, **plan: Any) -> dict[str, Any]:
        round_id = plan["round_id"]
        assert round_id not in plans
        plans[round_id] = plan
        return {
            "session_status": "RUNNING", "stop_reason": "stagnation_early_stop" if round_id == 1 else None,
            "frozen_solver": {"solver_id": f"solver-{round_id}"},
            "dev_eval": {"penalized_mean_objective": 5.0, "valid_count": 1, "completion_rate": 1.0,
                         "all_feasible": True, "records": []},
        }

    monkeypatch.setattr(SessionRunnerTool, "run_round", run_round)
    cfg = AgentConfig(
        run_id="m5-trajectory", output_dir=str(tmp_path), max_rounds=2, outer_requests_per_round_cap=4,
        archive_feedback_enabled=False, enable_stagnation_diagnostic_gate=True, basin_restart_on_stagnation=True,
    )

    class Driver:
        def __init__(self, *, crash: bool) -> None:
            self.crash = crash

        def decide_step(self, *, round_id: int, phase: str, step_index: int, messages: list, last_tool_result: dict) -> dict:
            if phase == "reflect":
                return {"action": "finish_round"}
            if round_id == 2 and step_index == 1 and self.crash:
                assert last_tool_result["error_code"] == "stagnation_diagnostic_required"
                assert messages[-1]["role"] == "tool" and messages[-1]["tool_call_id"] == "native-plan"
                raise RuntimeError("simulated diagnose interruption")
            if round_id == 2 and step_index == 2:
                assert last_tool_result["error_code"] == "stagnation_diagnostic_required"
            plan = {"direction": "local check", "hypothesis": "A fixed hypothesis"}
            if round_id == 2:
                plan["fresh_template"] = True
                if step_index == 0:
                    return {"action": "call_tool", "tool": "submit_plan_and_evolve", "arguments": plan,
                            "tool_call_id": "native-plan"}
            return {"action": "submit_plan", **plan}

    with pytest.raises(RuntimeError, match="simulated diagnose interruption"):
        run_research_agent(cfg, driver=Driver(crash=True))
    checkpoint = json.loads((tmp_path / "agent_checkpoint.json").read_text(encoding="utf-8"))
    assert checkpoint["completed_rounds"] == [1]
    assert checkpoint["round_diagnostic_blocks"] == 1
    summary = run_research_agent(cfg, driver=Driver(crash=False), resume=True)
    assert summary["completed_rounds"] == [1, 2]
    assert plans[2]["fresh_template"] is True
    assert not plans[1].get("fresh_template", False)
    events = [event["event"] for event in summary["trajectory_control_events"]]
    assert events.count("stagnation_diagnostic_required") == 2
    assert "stagnation_early_stop" in events and "basin_restart" in events


def test_hypothesis_ledger_auto_registration_deduplicates_and_retains_evidence(tmp_path: Path) -> None:
    ledger = HypothesisLedgerTool(tmp_path)
    with pytest.raises(ValueError, match="hypothesis_evidence_required"):
        ledger.update(hypothesis_id="H_auto", status="refuted")
    assert ledger.list_records() == []
    artifact = tmp_path / "observed.json"
    artifact.write_text("{}\n", encoding="utf-8")
    arguments = {
        "hypothesis_id": "H_auto", "status": "refuted", "rationale": "Observed a tie.",
        "evidence_artifacts": [{"path": artifact.name, "sha256": sha256_file(artifact)}],
    }
    entry = ledger.update(**arguments)
    assert entry["auto_registered"] is True and entry["status"] == "refuted"
    initial = ledger.ledger_path.read_bytes()
    reopened = HypothesisLedgerTool(tmp_path)
    assert reopened.update(**arguments) == entry
    assert reopened.ledger_path.read_bytes() == initial


def test_m4_part2_erratum_records_both_verified_jumps() -> None:
    path = Path(__file__).resolve().parents[1] / "experiments" / "milestone4" / "m4_math_closure_part2.md"
    erratum = path.read_text(encoding="utf-8")
    for expected in (
        "ord=173", "cd8aaa033dd5", "15.980136", "np.zeros(n)", "ord=242", "ckpt_cand_8c4dfb41aa",
        "np.maximum(negative_score, 0.0)", "78–79", "score = logit + noise", "noise_amp", "rload", "rdist",
    ):
        assert expected in erratum


def _mock_m5_research_run(config: AgentConfig, *, resume: bool) -> dict[str, Any]:
    from agent_skill_loop.milestone_checkpoint import (
        export_sealed_checkpoints,
        initialize_milestone_schedule,
        register_attempt_provenance,
        set_run_wall_offset_seconds,
        settle_attempt_provenance,
        try_seal_draining_checkpoints,
    )
    from research_agent.contracts import atomic_write_json
    from research_agent.loop import _build_initial_baseline_solver

    assert config.mode == "mock" and not resume
    assert config.total_request_cap == 100 and config.checkpoint_budgets == (100,)
    run_dir = Path(config.output_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(run_dir / "agent_config.json", config.to_dict())
    ledger = run_dir / "agent_budget.sqlite3"
    solver = _build_initial_baseline_solver(config).to_dict()
    solver["solver_id"] = config.run_id
    dev_metrics = {
        "all_feasible": True,
        "completion_rate": 1.0,
        "penalized_mean_tour_length": 10.0,
        "valid_only_mean_tour_length": 10.0,
    }
    budget = PersistentRequestBudget(
        ledger, max_requests=100, run_id=config.run_id,
        checkpoint_budgets=(100,), strict_checkpoint_barriers=True,
    )
    initialize_milestone_schedule(
        ledger, run_id=config.run_id, checkpoint_budgets=(100,), baseline_solver=solver,
        baseline_dev_eval={**dev_metrics, "penalized_mean_tour_length": 11.0},
        dev_suite_hash="mock_m5_dev_suite", solve_budget_ms=500.0,
    )
    reaches_cap = config.arm_id == "legacy_baseline_500ms" and config.search_seed == 20261124
    for ordinal in range(1, (100 if reaches_cap else 2) + 1):
        purpose = "eoh_generation" if ordinal <= 2 else "planner"
        slot = budget.reserve(purpose=purpose, problem="cvrp", model=config.eoh_model)
        assert slot is not None
        if ordinal <= 2:
            assert slot.attempt_token is not None
            register_attempt_provenance(
                ledger, attempt_token=slot.attempt_token, run_id=config.run_id,
                logical_call_id=None, physical_request_id=slot.request_id,
                global_ordinal=ordinal, purpose=purpose,
            )
        budget.mark_sent(slot)
        budget.finish(slot, "complete", status=200, input_tokens=10, output_tokens=5, cached_tokens=0)
        if ordinal == 1:
            settle_attempt_provenance(
                ledger, attempt_token=slot.attempt_token, generation_status="valid_candidate",
                eval_id="candidate_1", solver_manifest=solver, code_sha256=solver["hook_code_sha256"],
                validation_passed=True, dev_eval=dev_metrics,
                dev_suite_hash="mock_m5_dev_suite", solve_budget_ms=500.0,
            )
        elif ordinal == 2:
            settle_attempt_provenance(
                ledger, attempt_token=slot.attempt_token, generation_status="invalid_candidate",
                eval_id="candidate_2", validation_passed=False,
            )
    set_run_wall_offset_seconds(ledger, config.run_id, 2.0)
    assert try_seal_draining_checkpoints(ledger, config.run_id, wall_elapsed_seconds=2.0) == (
        [100] if reaches_cap else []
    )
    checkpoints = export_sealed_checkpoints(ledger, config.run_id, run_dir / "checkpoints")
    best_ref = "agent_artifacts/round_0001_frozen_solver.json"
    atomic_write_json(run_dir / best_ref, solver)

    round_dir = run_dir / "session_run" / "rounds" / "round_0001"
    atomic_write_json(round_dir / "evaluation_facts.json", {"search_progress": {"cumulative": {
        "behavior_comparable_count": 1,
        "behavior_generated_denominator": 2,
        "behavior_duplicate_count": 0,
        "behavior_comparable_coverage": 0.5,
        "behavior_duplicate_rate": 0.0,
    }}})
    eval_log = round_dir / "eoh_run" / "results" / "evaluations.jsonl"
    eval_log.parent.mkdir(parents=True, exist_ok=True)
    eval_log.write_text(json.dumps({
        "evaluation_id": "candidate_2", "origin": "generated", "revision": "original",
        "evaluation": {"valid": False, "error_code": "forbidden_attribute"},
    }) + "\n", encoding="utf-8")
    hypotheses = HypothesisLedgerTool(run_dir)
    hypotheses.propose(round_id=1, statement="Mock hypothesis", hypothesis_id="H_mock")
    summary = {
        "run_id": config.run_id, "arm_id": config.arm_id, "problem_family": "cvrp",
        "final_phase": "budget_stopped" if reaches_cap else "completed",
        "best_solver_manifest_ref": best_ref, "best_dev_objective": 10.0,
        "budget_summary": budget.summary(), "frozen_checkpoints": checkpoints,
        "token_summary": {"input_tokens": 10 * budget.used, "output_tokens": 5 * budget.used},
        "cost_summary": {"priced_cost_usd": 0.0}, "trajectory_control_events": [],
    }
    atomic_write_json(run_dir / "research_summary.json", summary)
    return summary


def test_b4_pruned_m32_champion_parity() -> None:
    from agent_skill_loop.interface_design.runtime import evaluate_frozen_interface_solver
    from agent_skill_loop.interface_design.validator import build_gate4_l3_6cust_instance
    from tools.run_b4_intron_ablation import (
        build_pruned_m32_champion,
        load_m32_champion_solver,
        load_raw_m32_champion,
    )

    raw = load_raw_m32_champion()
    original = raw["hook_code"].splitlines(keepends=True)
    pruned = build_pruned_m32_champion(raw)
    assert raw["solver_id"] == "ckpt_cand_8c4dfb41aa"
    assert raw["hook_code"] == "".join(original)
    assert pruned["solver_id"] == "ckpt_cand_8c4dfb41aa_pruned"
    assert pruned["hook_code"] == "".join(
        line for number, line in enumerate(original, start=1) if number not in {7, 8, 78, 79}
    )
    assert pruned["hook_code_sha256"] != raw["hook_code_sha256"]
    assert len(pruned["bundle_hash"]) == 64

    instance = build_gate4_l3_6cust_instance()
    outcomes = [
        evaluate_frozen_interface_solver(
            load_m32_champion_solver(solver), instance,
            solve_deadline_ms=2000.0, enforce_wall_deadline=True,
        )
        for solver in (raw, pruned)
    ]
    assert all(row["valid"] and row["completed"] for row in outcomes)
    assert outcomes[0]["tour_length"] == outcomes[1]["tour_length"]
    assert outcomes[0]["routes"] == outcomes[1]["routes"]


def test_m5_trajectory_control_runner_mock_e2e(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import tempfile

    from agent_skill_loop.interface_design import blind_eval_m5
    from tools import run_m5_trajectory_control as runner

    output_dir = tmp_path / "m5"
    commitment = tmp_path / "commitment.json"
    arm_seeds = {
        "legacy_baseline_500ms": [20261124, 20261125],
        "whitelist_latency_500ms": [20261124, 20261125],
        "model2_ctrl_full_500ms": [20261124],
    }
    cells = [f"{arm}:{seed}" for arm, seeds in arm_seeds.items() for seed in seeds]
    arm_seeds_file = tmp_path / "arm_seeds.json"
    arm_seeds_file.write_text(json.dumps(arm_seeds), encoding="utf-8")
    fake_seed = "a1" * 32
    original_builtin_evaluator = blind_eval_m5.evaluate_algorithm_on_instance
    observed_models: dict[str, tuple[str, str]] = {}

    def mock_run(config: AgentConfig, *, resume: bool) -> dict[str, Any]:
        observed_models[config.arm_id] = (config.planner_model, config.eoh_model)
        return _mock_m5_research_run(config, resume=resume)

    def mock_outcome(solver_id: str, instance: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        assert kwargs["enforce_wall_deadline"] is True
        assert kwargs.get("solve_deadline_ms", kwargs.get("time_budget_ms")) == 500.0
        reference = float(instance["reference_objective"])
        whitelist = "whitelist_latency" in solver_id
        timed_out = whitelist and instance["size"] == 200
        return {
            "valid": True, "completed": not timed_out, "status": "ok",
            "budget_exhausted": timed_out, "exact_vehicle_count": not whitelist,
            "tour_length": reference * (0.95 if whitelist else 1.0),
            "solve_ms": 500.0 if timed_out else 5.0, "hook_ms": 1.0,
            "routes": [[0, 1, 0]], "demands": [4], "items": [9],
        }

    def mock_frozen(solver: Any, instance: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        return mock_outcome(solver.solver_id, instance, **kwargs)

    def mock_public_frozen(
        solver: Any, instance: dict[str, Any], suite: dict[str, Any], *, solve_deadline_ms: float,
    ) -> dict[str, Any]:
        return mock_frozen(solver, instance, solve_deadline_ms=solve_deadline_ms, enforce_wall_deadline=True)

    def mock_builtin(algorithm: str, instance: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        if algorithm == "nn":
            return original_builtin_evaluator(algorithm, instance, **kwargs)
        return mock_outcome(algorithm, instance, **kwargs)

    bootstrap_calls: list[tuple[int, int, int, int]] = []
    original_bootstrap = runner.paired_bootstrap_comparison

    def capture_bootstrap(left: list[float], right: list[float], *, n_boot: int, seed: int) -> dict[str, Any]:
        bootstrap_calls.append((len(left), len(right), n_boot, seed))
        return original_bootstrap(left, right, n_boot=n_boot, seed=seed)

    monkeypatch.setattr(runner, "run_research_agent", mock_run)
    monkeypatch.setattr(blind_eval_m5, "evaluate_frozen_interface_solver", mock_frozen)
    monkeypatch.setattr(blind_eval_m5, "evaluate_algorithm_on_instance", mock_builtin)
    monkeypatch.setattr(runner, "evaluate_public_frozen_solver", mock_public_frozen)
    monkeypatch.setattr(runner, "evaluate_algorithm_on_instance", mock_builtin)
    monkeypatch.setattr(runner, "paired_bootstrap_comparison", capture_bootstrap)

    def read_json(path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    with tempfile.TemporaryDirectory(prefix="m5-mock-") as external_dir:
        custody_dir = Path(external_dir) / "custody"
        cli = [
            "--output-dir", str(output_dir), "--custody-dir", str(custody_dir),
            "--commitment-path", str(commitment),
        ]
        with monkeypatch.context() as seal_patches:
            seal_patches.setattr(blind_eval_m5.secrets, "token_hex", lambda count: fake_seed)
            assert runner.main([
                *cli, "seal-blind", "--arm-seeds-json", str(arm_seeds_file), "--model2", "kimi-k2.7-code",
            ]) == 0
        assert read_json(commitment)["instance_count"] == 120

        assert runner.main([*cli, "emit-mux", "--mode", "mock"]) == 0
        panes = read_json(output_dir / "mux_m5.json")["panes"]
        assert len({pane["id"] for pane in panes}) == len(cells)
        for pane in panes:
            assert runner.main(pane["command"][2:]) == 0
        assert observed_models["legacy_baseline_500ms"] == ("deepseek-v4.1-flash", "deepseek-v4.1-flash")
        assert observed_models["model2_ctrl_full_500ms"] == ("kimi-k2.7-code", "kimi-k2.7-code")

        arm, seed = cells[-1].split(":")
        config_path = output_dir / "runs" / f"{arm}_s{seed}" / "agent_config.json"
        config_bytes = config_path.read_bytes()
        config_path.write_text(json.dumps({**json.loads(config_bytes), "mode": "live"}), encoding="utf-8")
        with pytest.raises(ValueError, match="m5_roster_mixes_mock_and_live_runs"):
            runner.main([*cli, "lock-roster"])
        config_path.write_bytes(config_bytes)
        assert runner.main([*cli, "lock-roster"]) == 0
        lock = read_json(output_dir / "m5_roster_lock_bundle.json")
        assert set(lock["snapshot_paths"]) == set(cells)
        winner_sources = {cell: meta["winner_source"] for cell, meta in lock["snapshot_metadata"].items()}
        assert winner_sources == {
            cell: "sealed_checkpoint_100" if cell == cells[0] else "agent_best_solver" for cell in cells
        }

        assert not Path(lock["roster_lock_path"]).is_absolute()
        snapshot = output_dir / lock["snapshot_paths"][cells[0]]
        snapshot_bytes = snapshot.read_bytes()
        snapshot.write_bytes(snapshot_bytes + b"\n")
        with pytest.raises(ValueError, match="snapshot.*mismatch"):
            runner.main([*cli, "unseal-blind"])
        snapshot.write_bytes(snapshot_bytes)
        assert runner.main([*cli, "unseal-blind"]) == 0
        with pytest.raises(FileExistsError, match="^blind_attempt_already_consumed$"):
            runner.main([*cli, "unseal-blind"])
        assert runner.main([*cli, "eval-external"]) == 0
        assert runner.main([*cli, "report"]) == 0

    blind = read_json(output_dir / "blind_120_eval" / "m5_blind_evaluation.json")
    assert len(blind["records"]) == 120 * len(cells)
    assert {row["size"] for row in blind["records"]} == {50, 100, 150, 200}
    assert set(blind["baseline_records"]) == {
        "l3_ctrl@500ms", "m32_champion_raw@500ms", "m32_champion_pruned@500ms",
        "cw_parallel_merge@500ms", "cw_relocate_2opt@500ms",
    }
    assert sum(row["budget_exhausted"] for row in blind["records"]) == 60
    external = read_json(output_dir / "m5_external_evaluation.json")["suites"]
    assert all(row["exact_k_feasible"] is not None
               for row in external["cvrp_ext_cvrplib_abp_74"]["records"][cells[0]])
    assert all(row["exact_k_feasible"] is None
               for row in external["cvrp_ext_cvrplib_x_100"]["records"][cells[0]])
    assert bootstrap_calls
    assert set(bootstrap_calls) == {
        (120, 120, 10000, 20261124), (120, 120, 10000, 20261125),
    }
    report = read_json(output_dir / "m5_trajectory_control_report.json")
    assert set(report["per_cell"]) == set(cells)
    assert set(report["trajectory_by_cell"]) == set(cells)
    first_trajectory = report["trajectory_by_cell"][cells[0]]
    assert first_trajectory["total_requests"] == 100
    assert first_trajectory["forbidden_attribute_count"] == 1
    assert first_trajectory["behavior_comparable_coverage"] == 0.5
    assert first_trajectory["behavior_duplicate_rate"] == 0.0
    assert first_trajectory["hypothesis_ledger_distinct_ids"] == 1
    assert any(
        {row["seed"] for row in results} == {20261124, 20261125}
        for results in report["contrasts"].values()
    )
    for artifact in (
        commitment,
        output_dir / "blind_120_eval" / "m5_blind_evaluation.json",
        output_dir / "m5_external_evaluation.json",
        output_dir / "m5_trajectory_control_report.json",
    ):
        text = artifact.read_text(encoding="utf-8")
        assert fake_seed not in text
        for private_key in ("customer_coordinates", "demands", "items", "routes", "sealed_seed_token", "seed_token"):
            assert f'"{private_key}"' not in text


def test_redteam_fixes_security_screens_and_deadlines(tmp_path: Path) -> None:
    from agent_skill_loop.interface_design.blind_eval_m5 import build_m5_public_record
    from research_agent.sandbox_worker import validate_sandbox_ast
    from research_agent.tools.diagnostic_tools import DiagnosticTool
    from research_agent.tools.math_sandbox import MathSandboxTool

    for allow_ext in (False, True):
        for expr in ("np.empty(len(i_idx))", "np.empty_like(i_idx)"):
            failures, _ = validate_hook_ast(
                _score(expr), hook_name="score_merge_static", expected_args=STATIC_SIGNATURE,
                allow_extended_numpy_whitelist=allow_ext,
            )
            assert any(f.error_code == "forbidden_attribute" for f in failures), (allow_ext, expr)

    for bad_script in (
        "import numpy as np\nx = np.load('foo.npy')",
        "import numpy as np\nnp.savetxt('out.txt', [1])",
        "import numpy as np\nx = np.memmap('foo', mode='r')",
        "name = 'cvrp_m5_control_blind_120'",
        "path = '.agent_skill_custody_m5/x'",
    ):
        with pytest.raises(ValueError):
            validate_sandbox_ast(bad_script)

    run_dir = tmp_path / "resume_seq"
    (run_dir / "agent_artifacts" / "diagnostics").mkdir(parents=True)
    (run_dir / "agent_artifacts" / "sandbox").mkdir(parents=True)
    diag1 = run_dir / "agent_artifacts" / "diagnostics" / "diag_0001.json"
    sand1 = run_dir / "agent_artifacts" / "sandbox" / "run_0001.json"
    diag1.write_text('{"keep": 1}\n', encoding="utf-8")
    sand1.write_text('{"keep": 1}\n', encoding="utf-8")
    diag_tool = DiagnosticTool(run_dir)
    sand_tool = MathSandboxTool(run_dir)
    assert diag_tool._seq == 1
    assert sand_tool._seq == 1
    assert sand_tool.run(script="x = 1 + 1\nresult = x")["artifact_ref"].endswith("run_0002.json")
    assert json.loads(sand1.read_text(encoding="utf-8")) == {"keep": 1}

    thresholded = _score("np.zeros(len(i_idx), dtype=np.float64) if len(i_idx) > 10 else np.arange(len(i_idx), dtype=np.float64)")
    threshold_res = eval_worker._handle_request(_worker_request(thresholded, enable_degenerate_constant_screen=True))
    assert threshold_res["error_code"] == "degenerate_constant_output"

    design = build_design_for_template(STATIC_TEMPLATE, "v1")
    problem = DynamicInterfaceProblem(
        design=design,
        instances=[build_gate4_dual_action_instance()],
        suite_id="test_dev",
        enable_n200_latency_screen=True,
    )
    assert problem.evaluate_detailed(_score("np.load(i_idx)"), origin="generated")["error_code"] == "forbidden_attribute"

    pub = build_m5_public_record(
        {"instance_id": "x1", "size": 200, "reference_tour_length": 1000.0},
        {"valid": True, "completed": True, "budget_exhausted": False, "feasible": True,
         "objective": 900.0, "solve_ms": 505.0, "exact_vehicle_count": True},
        solve_deadline_ms=500.0,
    )
    assert pub["completed"] is False and pub["budget_exhausted"] is True


def test_redteam_failed_diagnostic_does_not_clear_gate_and_grants_headroom(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    plans: dict[int, dict[str, Any]] = {}

    def run_round(_self: SessionRunnerTool, **plan: Any) -> dict[str, Any]:
        plans[plan["round_id"]] = plan
        return {
            "session_status": "RUNNING",
            "stop_reason": "stagnation_early_stop" if plan["round_id"] == 1 else None,
            "frozen_solver": {"solver_id": f"solver-{plan['round_id']}"},
            "dev_eval": {"penalized_mean_objective": 5.0, "valid_count": 1, "completion_rate": 1.0,
                         "all_feasible": True, "records": []},
        }

    monkeypatch.setattr(SessionRunnerTool, "run_round", run_round)
    cfg = AgentConfig(
        run_id="m5-diag-headroom", output_dir=str(tmp_path), max_rounds=2, outer_requests_per_round_cap=3,
        archive_feedback_enabled=False, enable_stagnation_diagnostic_gate=True, basin_restart_on_stagnation=True,
    )

    class Driver:
        def decide_step(self, *, round_id: int, phase: str, step_index: int, messages: list, last_tool_result: dict) -> dict:
            if phase == "reflect":
                return {"action": "finish_round"}
            if round_id == 2:
                if step_index == 0:
                    return {"action": "call_tool", "tool": "run_math_sandbox", "arguments": {"script": "import os\nresult = 1"}}
                if step_index == 1:
                    assert last_tool_result.get("ok") is False
                    return {"action": "submit_plan", "direction": "try plan", "hypothesis": "failed diag should still block"}
                if step_index == 2:
                    assert last_tool_result.get("error_code") == "stagnation_diagnostic_required"
                    return {"action": "call_tool", "tool": "run_math_sandbox", "arguments": {"script": "result = 42"}}
                assert last_tool_result.get("ok") is True
            return {"action": "submit_plan", "direction": "verified diag plan", "hypothesis": "H_diag"}

    summary = run_research_agent(cfg, driver=Driver())
    assert summary["completed_rounds"] == [1, 2]
    assert plans[2]["direction"] == "verified diag plan"


def test_codex_review_closure_guards(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import tempfile
    from types import SimpleNamespace
    from agent_skill_loop.interface_design import blind_eval_m5
    from research_agent.tools.diagnostic_tools import DiagnosticTool
    import tools.run_m5_trajectory_control as runner

    diag_tool = DiagnosticTool(tmp_path / "diag_ok")
    diag_res = diag_tool.diagnose_suite(template_id=STATIC_TEMPLATE, max_instances=2)
    assert diag_res["artifact_ref"].endswith("diag_0001.json") and diag_res.get("error") is None
    assert len(json.loads((tmp_path / "diag_ok" / diag_res["artifact_ref"]).read_text(encoding="utf-8"))["per_instance_records"]) == 2

    design = build_design_for_template(STATIC_TEMPLATE, "v1")
    problem = DynamicInterfaceProblem(
        design=design, instances=[build_gate4_dual_action_instance()], suite_id="test_dev",
        enable_n200_latency_screen=True,
    )
    monkeypatch.setattr(InterfaceValidator, "validate_evolved_hook_n200_latency", lambda *a, **kw: {
        "passed": False, "budget_ms": 500.0, "error_code": "hook_runtime_error",
        "error_detail": "ZeroDivisionError", "max_solve_ms": 1.2, "timeout_kind": None,
    })
    assert problem.evaluate_detailed(_score("1.0 / 0.0"), origin="generated")["error_code"] == "hook_runtime_error"

    monkeypatch.setattr(blind_eval_m5, "load_locked_m5_roster", lambda **_kw: ({}, {}, {}))
    monkeypatch.setattr(blind_eval_m5, "read_m5_protocol", lambda *_a, **_kw: {
        "blind_commitment": {"suite_content_sha256": "deadbeef", "commitment_file_sha256": "cafebabe", "instance_count": 120},
    })
    with tempfile.TemporaryDirectory(prefix="m5-guard-") as ext_dir:
        with pytest.raises(ValueError, match="invalid_m5_comparator_labels"):
            blind_eval_m5.unseal_and_evaluate_m5(
                protocol_path=tmp_path / "p.json", expected_protocol_sha256="p",
                roster_lock_path=tmp_path / "r.json", expected_roster_lock_sha256="r",
                snapshot_paths={}, output_dir=tmp_path / "blind_out", custody_dir=Path(ext_dir) / "custody",
                comparator_solvers=(),
            )

    out_dir = tmp_path / "mock_guard"
    out_dir.mkdir()
    (out_dir / runner.LOCK_BUNDLE).write_text(json.dumps({
        "run_mode": "mock", "protocol_path": "p.json", "protocol_sha256": "a",
        "roster_lock_path": "r.json", "roster_lock_sha256": "b", "snapshot_paths": {},
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="mock_roster_cannot_consume_production_m5_blind_attempt"):
        runner.cmd_unseal_blind(SimpleNamespace(
            output_dir=out_dir,
            commitment_path=blind_eval_m5.M5_BLIND_COMMITMENT_PATH,
            custody_dir=None,
        ))
