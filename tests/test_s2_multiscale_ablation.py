from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from typing import Any

import pytest

from agent_skill_loop.interface_design.blind_eval_m32 import assert_milestone_suite_not_blind
from agent_skill_loop.interface_design.dynamic_eoh import DynamicInterfaceProblem
from agent_skill_loop.interface_design.multiscale import probe_timeout_s
from agent_skill_loop.interface_design.planner import build_design_for_template
from agent_skill_loop.interface_design.session_bridge import _DynamicCandidateEoH, _StagnationAwareEoH
from agent_skill_loop.interface_design.validator import InterfaceValidator
from agent_skill_loop.milestone_checkpoint import ensure_milestone_tables
from research_agent.contracts import AgentConfig, atomic_write_json, atomic_write_text
from research_agent.loop import _build_initial_baseline_solver, run_research_agent
from research_agent.tools.session_tools import SessionRunnerTool
from tools import run_s2_multiscale_ablation as runner


def test_four_probe_policy_boundaries_and_nested_watchdogs() -> None:
    design = build_design_for_template("cvrp_parallel_merge_static", "v1")
    lock = runner._read_screen_lock()
    assert lock["lock_sha256"] == runner.THRESHOLD_LOCK_SHA256
    worker_timeout = probe_timeout_s(500.0, constant_screen=False)
    assert worker_timeout == 5.5
    task = DynamicInterfaceProblem(
        design=design, instances=[{}] * 24, suite_id=runner.DEV_SUITE_ID,
        enable_multiscale_latency_ratio_screen=True, enable_degenerate_constant_screen=True,
        multiscale_n200_abs_cap_ms=runner.POLICY["n200_abs_cap_ms"], checkpoint_validation_workers=7,
    )
    assert task.multiscale_probe_timeout_s == worker_timeout
    assert task.candidate_timeout_s == 28.0
    assert task.enclosing_candidate_timeout_s == 219
    calls = []

    class Evaluator:
        times = (1.25, 10.0, 20.0, runner.POLICY["n200_abs_cap_ms"])
        censor_200 = False

        def evaluate(self, **kwargs: Any) -> dict[str, Any]:
            calls.append(kwargs)
            return {
                "valid": True, "outer_timeout_s": worker_timeout,
                "records": [
                    {
                        "instance_id": instance["instance_id"], "valid": True, "solve_ms": solve_ms,
                        "budget_exhausted": self.censor_200 and index == 3,
                    }
                    for index, (instance, solve_ms) in enumerate(zip(kwargs["instances"], self.times, strict=True))
                ],
            }

    evaluator = Evaluator()
    validator = InterfaceValidator(
        evaluator=evaluator, candidate_timeout_s=worker_timeout, outer_timeout_s=worker_timeout,
        instance_time_budget_ms=500.0, enable_degenerate_constant_screen=True,
    )

    def run() -> dict[str, Any]:
        return validator.validate_evolved_hook_multiscale_latency(
            design, multiscale_n200_abs_cap_ms=runner.POLICY["n200_abs_cap_ms"],
        )

    passed = run()
    assert passed["passed"] is True
    assert passed["pairs"][0]["ratio_200_100"] == 8.0
    assert [row["instance_id"] for row in calls[0]["instances"]] == [
        "s2_synthetic_n100_r0", "s2_synthetic_n200_r0", "s2_synthetic_n100_r1", "s2_synthetic_n200_r1",
    ]
    assert calls[0]["outer_timeout_s"] == worker_timeout
    assert calls[0]["fresh_hooks_per_instance"] and calls[0]["enable_degenerate_constant_screen"]
    evaluator.times = (0.0, 9.99, 20.0, runner.POLICY["n200_abs_cap_ms"])
    tiny = run()
    assert tiny["passed"] and tiny["pairs"][0]["ratio_200_100"] == 9.99
    evaluator.times = (0.0, 10.0, 20.0, runner.POLICY["n200_abs_cap_ms"])
    assert run()["error_code"] == "multiscale_latency_exceeded"
    evaluator.times = (5.0, 10.0, 20.0, runner.POLICY["n200_abs_cap_ms"] + 0.001)
    assert run()["pairs"][1]["rejected"] is True
    evaluator.times = (5.0, 10.0, 20.0, 20.0)
    evaluator.censor_200 = True
    censored = run()
    assert censored["pairs"][1]["n200_deadline_miss"] is True
    assert censored["pairs"][1]["ratio_200_100"] is None
    assert censored["passed"] is False


def test_early_stop_consumes_durable_generation_ordinals_without_evaluations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def init(self: Any, *_args: Any) -> None:
        self.num_samplers = self.num_evaluators = 1

    monkeypatch.setattr(_DynamicCandidateEoH, "__init__", init)
    journal = tmp_path / "evaluations.jsonl"
    journal.write_text(json.dumps({
        "evaluation_id": "base", "origin": "baseline", "evaluation": {"valid": True, "objective": 10.0},
    }) + "\n", encoding="utf-8")
    attempts = [(ordinal, f"token-{ordinal}") for ordinal in range(5, 28)]
    early_stop = _StagnationAwareEoH(
        None, None, evaluation_log=journal, no_jump_limit=24, generation_attempts=lambda: attempts,
    )
    assert early_stop.reached_stagnation() is False
    assert early_stop.no_jump_count == 23
    attempts.extend([(30, "malformed"), (31, "later")])
    assert early_stop.reached_stagnation() is True
    assert early_stop.trigger_ordinal == 30
    assert early_stop.no_jump_count == 24
    assert early_stop.reached_stagnation() and early_stop.trigger_ordinal == 30


def test_restart_uses_final_slot_once_across_resume(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = AgentConfig(
        run_id="exp2c-one-slot", output_dir=str(tmp_path), max_rounds=12, total_request_cap=100,
        eoh_max_sample_nums=32, early_stop_no_jump_requests=24, basin_restart_on_stagnation=True,
        stagnation_diagnostic_mode="off", archive_feedback_enabled=False, kb_enabled=False,
    )
    calls: list[tuple[int, bool]] = []

    def run_round(self: SessionRunnerTool, **plan: Any) -> dict[str, Any]:
        round_id, fresh = plan["round_id"], plan["fresh_template"]
        calls.append((round_id, fresh))
        if round_id == 2 and len(calls) == 2:
            raise RuntimeError("interrupt before final slot")
        for _ in range(99 if round_id == 1 else 1):
            request = self.budget.reserve(purpose="eoh_generation", problem="cvrp", model=config.eoh_model)
            assert request is not None
            self.budget.mark_sent(request)
            self.budget.finish(request, "complete", status=200)
        return {
            "session_status": "RUNNING" if round_id == 1 else "COMPLETED",
            "stop_reason": "stagnation_early_stop" if round_id == 1 else "request_budget_exhausted",
            **({"stagnation_trigger_ordinal": 99} if round_id == 1 else {"fresh_template_applied": True}),
            "frozen_solver": {"solver_id": f"round-{round_id}"},
            "dev_eval": {"penalized_mean_objective": 1.0, "valid_count": 1, "completion_rate": 1.0, "all_feasible": True},
        }

    class Driver:
        def decide_step(self, *, round_id: int, phase: str, **_kwargs: Any) -> dict[str, str]:
            assert (round_id, phase) == (1, "diagnose")
            return {"action": "submit_plan", "direction": "test"}

    monkeypatch.setattr(SessionRunnerTool, "run_round", run_round)
    with pytest.raises(RuntimeError, match="interrupt before final slot"):
        run_research_agent(config, driver=Driver())
    summary = run_research_agent(config, driver=Driver(), resume=True)
    assert calls == [(1, False), (2, True), (2, True)]
    assert summary["realized_request_spend"] == 100
    assert summary["restart_count"] == 1
    assert [row["attempted_request_delta"] for row in summary["round_summaries"]] == [99, 1]
    assert {
        "event": "basin_restart", "round_id": 2, "trigger_round_id": 1, "stagnation_trigger_ordinal": 99,
    } in summary["trajectory_control_events"]


def _mock_settled_cell(config: AgentConfig, *, resume: bool) -> dict[str, Any]:
    assert config.mode == "mock" and not resume
    directory = Path(config.output_dir)
    atomic_write_json(directory / "agent_config.json", config.to_dict())
    snapshot = _build_initial_baseline_solver(config).to_dict()
    snapshot_digest = runner._sha256_payload(snapshot)
    payload = {
        "schema_version": "m32-frozen-checkpoint/v1", "run_id": config.run_id,
        "checkpoint_budget": 100, "settled_through_ordinal": 100, "eligibility_status": "eligible_champion",
        "winner_source_ordinal": 0, "winner_solver_sha256": snapshot_digest, "frozen_solver": snapshot,
    }
    path = directory / "checkpoints" / "frozen_checkpoint_100.json"
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    with closing(sqlite3.connect(directory / "agent_budget.sqlite3")) as ledger, ledger:
        ledger.execute("CREATE TABLE budget_requests (run_id TEXT, idx INTEGER, state TEXT)")
        ledger.executemany(
            "INSERT INTO budget_requests VALUES (?, ?, 'complete')",
            [(config.run_id, index) for index in range(1, 101)],
        )
        ensure_milestone_tables(ledger)
        ledger.execute(
            """
            INSERT INTO milestone_checkpoints (
                run_id, ckpt_budget, state, settled_through_ordinal, winner_source_ordinal,
                winner_solver_sha256, payload_sha256, canonical_payload_json,
                created_at_utc, updated_at_utc
            ) VALUES (?, 100, 'sealed', 100, 0, ?, ?, ?, 'test', 'test')
            """,
            (config.run_id, snapshot_digest, runner._sha256(path.read_bytes()), path.read_text(encoding="utf-8")),
        )
    summary = {
        "run_id": config.run_id, "final_phase": "budget_stopped", "stop_reason": "request_budget_exhausted",
        "restart_count": 0, "realized_request_spend": 100, "trajectory_control_events": [],
        "budget_summary": {"attempted_requests": 100},
    }
    atomic_write_json(directory / "research_summary.json", summary)
    return summary


def test_mock_protocol_through_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seeds = runner.SEEDS
    assert len(runner._cells()) == 24
    monkeypatch.setattr(runner, "SEEDS", seeds[:1])
    configs: dict[str, AgentConfig] = {}

    def run(config: AgentConfig, *, resume: bool) -> dict[str, Any]:
        assert config.planner_model in runner.MODELS and config.planner_model == config.eoh_model
        configs[runner._id(config.planner_model, config.arm_id, config.search_seed)] = config
        return _mock_settled_cell(config, resume=resume)

    def score(solver: Any, instance: dict[str, Any], **opts: Any) -> dict[str, Any]:
        assert opts["capture_timed_incumbents"] and opts["solve_deadline_ms"] == 500.0
        code = next(arm for arm in runner.ARMS if arm in solver.solver_id)
        index = list(runner.ARMS).index(code)
        late = index == 3 and instance["size"] == 200
        objective = 100.0 + (0, -2, -3, -4)[index]
        return {
            "solve_ms": 502.0 if late else 5.0, "solve_censored": late,
            "feasible_before_deadline": True, "feasible_before_deadline_objective": objective,
            "returned_before_deadline": not late, "returned_before_deadline_objective": objective if not late else None,
            "feasible_before_deadline_exact_k": index != 3, "feasible_before_deadline_exact_k_objective": objective,
            "returned_before_deadline_exact_k": index != 3, "returned_before_deadline_exact_k_objective": objective,
            "routes": [[0, 1, 0]], "demands": [2], "customer_coordinates": [[0, 0]],
        }

    monkeypatch.setattr(runner, "run_research_agent", run)
    monkeypatch.setattr(runner, "evaluate_frozen_interface_solver", score)
    output_dir = tmp_path / "s2"
    base = ["--out-dir", str(output_dir)]
    with TemporaryDirectory(prefix="s2-test-custody-") as temp_dir:
        custody = Path(temp_dir) / "independent"
        custody_args = ["--custody-dir", str(custody)]
        assert runner.main(["seal-blind", *base, *custody_args, "--mock"]) == 0
        with pytest.raises(ValueError, match="existing_receipt_mismatch"):
            runner.main(["seal-blind", "--out-dir", str(tmp_path / "other"), *custody_args, "--mock"])
        with pytest.raises(ValueError, match="blind_suite_forbidden_in_dev_pipeline"):
            assert_milestone_suite_not_blind(runner.BLIND_SUITE_ID)
        assert runner.main(["emit-mux", *base]) == 0
        panes = runner._json(output_dir / "mux_s2_multiscale.json")["panes"]
        assert len({pane["id"] for pane in panes}) == 8
        for pane in panes:
            command = pane["command"][2:]
            model_index = command.index("--model") + 1
            command[model_index] = command[model_index].swapcase()
            assert runner.main(command) == 0
        assert set(configs) == set(runner._cells())
        for model in runner.MODELS:
            config_rows = [configs[runner._id(model, arm, seeds[0])].to_dict() for arm in runner.ARMS]
            ignored = set(runner.FACTORS) | {"run_id", "arm_id", "output_dir"}
            shared = [{key: value for key, value in config.items() if key not in ignored} for config in config_rows]
            assert shared == [shared[0]] * 4
        assert runner.main(["lock-roster", *base]) == 0
        lock = runner._json(output_dir / runner.LOCK)
        assert {row["winner_source_ordinal"] for row in lock["roster"]} == {0}
        assert {row["realized_request_spend"] for row in lock["roster"]} == {100}
        snapshot = output_dir / lock["roster"][0]["snapshot_ref"]
        original = snapshot.read_bytes()
        snapshot.write_bytes(original + b"\n")
        with pytest.raises(ValueError, match="snapshot_sha256_mismatch"):
            runner.main(["unseal-eval", *base, *custody_args])
        assert not list(custody.glob("*.consumed"))
        snapshot.write_bytes(original)
        assert runner.main(["unseal-eval", *base, *custody_args]) == 0
        with pytest.raises(FileExistsError, match="already_consumed"):
            runner.main(["unseal-eval", *base, *custody_args])
    assert runner.main(["report", *base]) == 0
    results = runner._json(output_dir / f"{runner.REPORT}.json")
    common_blind = {
        (row["timing_view"], row["contrast"]): row
        for row in results["contrasts"] if row["model"] == runner.MODELS[0] and row["suite_id"] == runner.BLIND_SUITE_ID
        and row["fleet"] == "free_fleet" and row["denominator"] == "common_completed"
    }
    feasible = "feasible_before_deadline"
    returned = "returned_before_deadline"
    for effect, mean in {"multiscale_main": -1.5, "early_stop_main": -2.5, "interaction": 1.0}.items():
        assert common_blind[feasible, effect]["n_pairs"] == 120
        assert common_blind[returned, effect]["n_pairs"] == 90
        assert common_blind[feasible, effect]["mean_contrast"] == mean
        assert common_blind[feasible, effect]["bootstrap"]["replicates"] == 10_000
    combined = runner._id(runner.MODELS[0], list(runner.ARMS)[3], seeds[0])
    combined_blind = results["per_seed"][runner.BLIND_SUITE_ID][combined]
    assert combined_blind["solve_latency_by_size"][-1]["solve_ms_p95_is_lower_bound"]
    assert results["per_seed"]["cvrp_ext_cvrplib_x_100"][combined]["timing_views"]["exact_k"] is None
    public_text = (output_dir / runner.EVALUATION).read_text(encoding="utf-8")
    assert all(f'"{field}"' not in public_text for field in ("customer_coordinates", "demands", "routes", "sealed_seed_token"))


def test_restart_receipts_multi_epoch_chronological_and_tamper_guards(tmp_path: Path) -> None:
    config = AgentConfig(
        run_id="exp2c-multi-epoch", output_dir=str(tmp_path), max_rounds=12, total_request_cap=100,
        eoh_max_sample_nums=32, early_stop_no_jump_requests=24, basin_restart_on_stagnation=True,
        stagnation_diagnostic_mode="off", archive_feedback_enabled=False, kb_enabled=False,
        allow_extended_numpy_whitelist=True, enable_degenerate_constant_screen=True,
        enable_multiscale_latency_ratio_screen=False,
    )

    def write_epoch_round(
        root: Path, local_round_id: int, facts_payload: dict[str, Any], receipt_payload: dict[str, Any] | None = None,
    ) -> None:
        round_dir = root / "rounds" / f"round_{local_round_id:04d}"
        eoh_dir = round_dir / "eoh_run"
        eoh_dir.mkdir(parents=True, exist_ok=True)
        facts_path = round_dir / "evaluation_facts.json"
        atomic_write_json(facts_path, {"round_id": local_round_id, **facts_payload})
        facts_sha = runner._sha256(facts_path.read_bytes())
        if receipt_payload is not None:
            atomic_write_json(eoh_dir / "interface_seed_receipt.json", receipt_payload)
        db_path = root / "session.sqlite3"
        with closing(sqlite3.connect(str(db_path))) as con:
            con.execute(
                "CREATE TABLE IF NOT EXISTS rounds (run_id TEXT, round_id INTEGER, task_id TEXT, state TEXT, evaluation_facts_ref TEXT, evaluation_facts_sha256 TEXT)"
            )
            con.execute(
                "CREATE TABLE IF NOT EXISTS tasks (task_id TEXT, run_id TEXT, round_id INTEGER, state TEXT)"
            )
            task_id = f"task_{root.name}_{local_round_id}"
            rel_facts = facts_path.relative_to(root).as_posix()
            con.execute(
                "INSERT INTO tasks VALUES (?, ?, ?, 'COLLECTED')",
                (task_id, config.run_id, local_round_id),
            )
            con.execute(
                "INSERT INTO rounds VALUES (?, ?, ?, 'ROUND_COMPLETED', ?, ?)",
                (config.run_id, local_round_id, task_id, rel_facts, facts_sha),
            )
            con.commit()

    interrupted = tmp_path / "session_run_interrupted_1795608529410"
    write_epoch_round(interrupted, 1, {"stop_reason": "stagnation_early_stop", "stagnation_trigger_ordinal": 29})
    write_epoch_round(
        interrupted, 2, {"stop_reason": "request_deadline", "fresh_template_applied": True},
        {"reason": "fresh_template", "requested_inherited_seeds": 0, "used_inherited_seeds": 0},
    )
    active = tmp_path / "session_run"
    write_epoch_round(
        active, 1, {"stop_reason": "stagnation_early_stop", "stagnation_trigger_ordinal": 100, "fresh_template_applied": True},
        {"reason": "fresh_template", "requested_inherited_seeds": 0, "used_inherited_seeds": 0},
    )
    summary = {
        "restart_count": 1,
        "trajectory_control_events": [
            {"round_id": 1, "event": "stagnation_early_stop", "stagnation_trigger_ordinal": 29},
            {"round_id": 2, "event": "basin_restart", "trigger_round_id": 1, "stagnation_trigger_ordinal": 29},
            {"round_id": 2, "event": "stagnation_early_stop", "stagnation_trigger_ordinal": 100},
        ],
    }
    receipts = runner._restart_receipts(tmp_path, config, summary)
    assert len(receipts) == 1
    assert receipts[0]["receipt_ref"] == "session_run/rounds/round_0001/eoh_run/interface_seed_receipt.json"

    bad_summary = {
        "restart_count": 1,
        "trajectory_control_events": [
            {"round_id": 1, "event": "stagnation_early_stop", "stagnation_trigger_ordinal": 30},
            {"round_id": 2, "event": "basin_restart", "trigger_round_id": 1, "stagnation_trigger_ordinal": 30},
        ],
    }
    with pytest.raises(ValueError, match="s2_early_stop_evidence_mismatch"):
        runner._restart_receipts(tmp_path, config, bad_summary)

    for receipt_file in (
        interrupted / "rounds/round_0002/eoh_run/interface_seed_receipt.json",
        active / "rounds/round_0001/eoh_run/interface_seed_receipt.json",
    ):
        atomic_write_json(receipt_file, {"reason": "fresh_template", "requested_inherited_seeds": 0, "used_inherited_seeds": 1})
    with pytest.raises(ValueError, match="s2_restart_receipt_mismatch"):
        runner._restart_receipts(tmp_path, config, summary)


def test_restart_receipts_stop_window_isolation_and_bool_timestamp_guards(tmp_path: Path) -> None:
    config = AgentConfig(
        run_id="m5_s2_test_restart_window", output_dir=str(tmp_path), max_rounds=12, total_request_cap=100,
        eoh_max_sample_nums=32, early_stop_no_jump_requests=24, basin_restart_on_stagnation=True,
        stagnation_diagnostic_mode="off", archive_feedback_enabled=False, kb_enabled=False,
        allow_extended_numpy_whitelist=True, enable_degenerate_constant_screen=True,
        enable_multiscale_latency_ratio_screen=False,
    )

    def write_round(root: Path, local_round_id: int, facts_payload: dict[str, Any], receipt_payload: dict[str, Any] | None = None) -> None:
        rdir = root / "rounds" / f"round_{local_round_id:04d}"
        eoh_dir = rdir / "eoh_run"
        eoh_dir.mkdir(parents=True, exist_ok=True)
        facts_path = rdir / "evaluation_facts.json"
        atomic_write_json(facts_path, {"round_id": local_round_id, **facts_payload})
        facts_sha = runner._sha256(facts_path.read_bytes())
        if receipt_payload is not None:
            atomic_write_json(eoh_dir / "interface_seed_receipt.json", receipt_payload)
        db = root / "session.sqlite3"
        with closing(sqlite3.connect(str(db))) as con:
            con.execute(
                "CREATE TABLE IF NOT EXISTS rounds (run_id TEXT, round_id INTEGER, task_id TEXT, state TEXT, evaluation_facts_ref TEXT, evaluation_facts_sha256 TEXT)"
            )
            con.execute(
                "CREATE TABLE IF NOT EXISTS tasks (task_id TEXT, run_id TEXT, round_id INTEGER, state TEXT)"
            )
            tid = f"task_{root.name}_{local_round_id}"
            con.execute("INSERT INTO tasks VALUES (?, ?, ?, 'COLLECTED')", (tid, config.run_id, local_round_id))
            con.execute(
                "INSERT INTO rounds VALUES (?, ?, ?, 'ROUND_COMPLETED', ?, ?)",
                (config.run_id, local_round_id, tid, facts_path.relative_to(root).as_posix(), facts_sha),
            )
            con.commit()

    # Multi-epoch counterexample: two stops each followed by a deadline receipt, plus final recovery.
    ep1 = tmp_path / "session_run_interrupted_1000"
    write_round(ep1, 1, {"stop_reason": "stagnation_early_stop", "stagnation_trigger_ordinal": 29})
    write_round(
        ep1, 2, {"stop_reason": "request_deadline", "fresh_template_applied": True},
        {"reason": "fresh_template", "requested_inherited_seeds": 0, "used_inherited_seeds": 0},
    )
    ep2 = tmp_path / "session_run_interrupted_2000"
    write_round(ep2, 1, {"stop_reason": "stagnation_early_stop", "stagnation_trigger_ordinal": 60})
    write_round(
        ep2, 2, {"stop_reason": "request_deadline", "fresh_template_applied": True},
        {"reason": "fresh_template", "requested_inherited_seeds": 0, "used_inherited_seeds": 0},
    )
    active = tmp_path / "session_run"
    write_round(
        active, 1, {"stop_reason": "budget_stopped", "fresh_template_applied": True},
        {"reason": "fresh_template", "requested_inherited_seeds": 0, "used_inherited_seeds": 0},
    )
    two_stop_summary = {
        "restart_count": 2,
        "trajectory_control_events": [
            {"round_id": 1, "event": "stagnation_early_stop", "stagnation_trigger_ordinal": 29},
            {"round_id": 2, "event": "basin_restart", "trigger_round_id": 1, "stagnation_trigger_ordinal": 29},
            {"round_id": 3, "event": "stagnation_early_stop", "stagnation_trigger_ordinal": 60},
            {"round_id": 4, "event": "basin_restart", "trigger_round_id": 3, "stagnation_trigger_ordinal": 60},
        ],
    }
    receipts = runner._restart_receipts(tmp_path, config, two_stop_summary)
    assert [r["receipt_ref"] for r in receipts] == [
        "session_run_interrupted_1000/rounds/round_0002/eoh_run/interface_seed_receipt.json",
        "session_run/rounds/round_0001/eoh_run/interface_seed_receipt.json",
    ]

    bad_ts = {
        "restart_count": 1,
        "trajectory_control_events": [
            {"round_id": 1, "event": "stagnation_early_stop", "stagnation_trigger_ordinal": 29},
            {"round_id": 2, "event": "basin_restart", "trigger_round_id": 1, "stagnation_trigger_ordinal": 29, "requested_at": 20, "restarted_at": 10},
        ],
    }
    with pytest.raises(ValueError, match="s2_restart_timestamp_mismatch"):
        runner._restart_receipts(tmp_path, config, bad_ts)

    atomic_write_json(
        ep1 / "rounds/round_0002/eoh_run/interface_seed_receipt.json",
        {"reason": "fresh_template", "requested_inherited_seeds": False, "used_inherited_seeds": 0},
    )
    with pytest.raises(ValueError, match="s2_restart_receipt_mismatch"):
        runner._restart_receipts(tmp_path, config, two_stop_summary)


