"""Deterministic round state machine for Plan → Execute → Evaluate → Memory.

This module is intentionally an orchestration shell.  It does not generate
algorithm code, select EoH parents, score candidates, or accept model facts.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import math
import hashlib
import difflib
from pathlib import Path
from typing import Any, Callable, Mapping

from agent_skill_loop.contracts import DEFAULT_COUNT, DEFAULT_SEED, DEFAULT_SIZE, DEFAULT_SOLVER_TIMEOUT
from agent_skill_loop.client import ProviderFailure
from agent_skill_loop.contracts_3plus1 import (
    EvaluateDocument,
    MAX_ROUND_CONTEXT_CHARS,
    PlanDocument,
    RoundState,
    compile_round_context,
)
from agent_skill_loop.memory import MemoryAPI, MemoryEntry
from agent_skill_loop.problems.base import get_problem
from agent_skill_loop.evaluator import evaluator_source_hash
from agent_skill_loop.roles.evaluate import EvaluatePrompt, EvaluateRole
from agent_skill_loop.roles.plan import PlanPrompt, PlanRole
from agent_skill_loop.request_budget import BudgetExhausted, RequestBudget
from agent_skill_loop.journal import Journal
from agent_skill_loop.skill_store import load_skill, validate_skill_for_suite


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
        os.replace(tmp, path)
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


class WorkflowRound:
    """One auditable round.  A new instance is required for each round."""

    def __init__(self, root: Path, state: RoundState, *, memory_enabled: bool = False) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=False)
        self.state = state
        self.memory_enabled = memory_enabled
        self.journal = Journal(self.root / "journal")
        self._write_state()

    def _write_state(self) -> None:
        _atomic_json(self.root / "manifest.json", self.state.as_dict())

    def _transition(self, target: str, *, reason: str | None = None) -> None:
        previous = self.state.status
        self.state.transition(target, reason=reason)
        self.journal.append("state_transition", {
            "round_id": self.state.round_id,
            "from": previous,
            "to": target,
            "reason": reason,
        })
        self._write_state()

    def record_plan(self, plan: PlanDocument) -> Path:
        if self.state.status != "created":
            raise ValueError("plan_recorded_in_wrong_state")
        if plan.round_id != self.state.round_id:
            raise ValueError("plan_round_id_mismatch")
        path = self.root / "plan.json"
        _atomic_json(path, plan.as_dict())
        self.state.plan_ref = path.relative_to(self.root).as_posix()
        self.state.memory_refs = plan.memory_basis
        self.state.feedback_consumed_count = 1 if plan.feedback_basis is not None else 0
        if plan.feedback_basis is not None:
            self.journal.append("feedback_consumed", {
                "round_id": self.state.round_id,
                "evaluation_ref": plan.feedback_basis.evaluation_ref,
                "feedback_round_id": plan.feedback_basis.round_id,
            })
        self._transition("planned")
        return path

    def begin_execute(self, *, round_context: str | None = None) -> None:
        if self.state.status != "planned":
            raise ValueError("execute_started_in_wrong_state")
        if round_context is not None:
            if len(round_context) > MAX_ROUND_CONTEXT_CHARS:
                raise ValueError("plan_context_too_large")
            (self.root / "round_context.txt").write_text(round_context, encoding="utf-8")
        self._transition("executing")

    def record_evaluation(self, facts: Mapping[str, Any]) -> Path:
        if self.state.status != "executing":
            raise ValueError("evaluation_recorded_in_wrong_state")
        path = self.root / "evaluation_facts.json"
        _atomic_json(path, dict(facts))
        self._transition("evaluated")
        return path

    def record_memory_decision(self, evaluation: EvaluateDocument) -> Path:
        if self.state.status != "evaluated":
            raise ValueError("memory_decision_in_wrong_state")
        if not self.memory_enabled and evaluation.memory_action.kind != "disabled":
            raise ValueError("memory_must_be_disabled")
        path = self.root / "evaluate.json"
        _atomic_json(path, evaluation.as_dict())
        self._transition("memory_decided")
        return path

    def finish(self) -> None:
        if self.state.status not in {"evaluated", "memory_decided"}:
            raise ValueError("round_finished_in_wrong_state")
        self._transition("round_finished")

    def stop(self, reason: str) -> None:
        if self.state.status in {"round_finished", "stopped", "failed"}:
            return
        self._transition("stopped", reason=reason)

    def update_remaining_requests(self, remaining: int | None) -> None:
        self.state.remaining_requests = remaining
        self._write_state()

    def fail(self, reason: str) -> None:
        if self.state.status in {"round_finished", "failed"}:
            raise ValueError("round_already_terminal")
        self._transition("failed", reason=reason)


class WorkflowRunner:
    """Run bounded 3+1 rounds around the official EoH CLI.

    The runner owns the global deadline and request ledger.  The supervised
    EoH child receives only the remaining budget and wall time, then its
    durable request count is reconciled into the parent ledger.  Parent
    selection and candidate acceptance remain inside EoH/deterministic export.
    """

    def __init__(
        self,
        root: Path,
        *,
        problem: str = "cvrp_construct",
        model: str = "deepseek-flash",
        endpoint: str = "https://api.deepseek.com/v1/chat/completions",
        api_key_env: str = "DEEPSEEK_API_KEY",
        max_rounds: int = 1,
        max_requests: int = 16,
        wall_seconds: float = 420.0,
        seed: int = DEFAULT_SEED,
        size: int = DEFAULT_SIZE,
        count: int = DEFAULT_COUNT,
        pop_size: int = 2,
        n_pop: int = 1,
        max_sample_nums: int = 2,
        solver_timeout: float = DEFAULT_SOLVER_TIMEOUT,
        request_timeout: float = 90.0,
        memory: MemoryAPI | None = None,
        plan_request: Callable[..., str] | None = None,
        evaluate_request: Callable[..., str] | None = None,
        execute: Callable[..., dict[str, Any]] | None = None,
        solution_min_relative_improvement: float | None = None,
        repair_mode: str = "off",
        max_repairs_per_candidate: int = 1,
        max_repair_requests_total: int | None = None,
    ) -> None:
        if max_rounds < 1 or max_requests < 0 or wall_seconds < 0:
            raise ValueError("workflow_budget_invalid")
        if not model and (plan_request is None or evaluate_request is None):
            raise ValueError("workflow_model_required")
        if solution_min_relative_improvement is not None and (not isinstance(solution_min_relative_improvement, (int, float)) or isinstance(solution_min_relative_improvement, bool) or not 0 <= solution_min_relative_improvement <= 1):
            raise ValueError("solution_threshold_invalid")
        if repair_mode not in {"off", "bounded"} or max_repairs_per_candidate not in {0, 1} or (max_repair_requests_total is not None and max_repair_requests_total < 0):
            raise ValueError("repair_config_invalid")
        self.root = Path(root).resolve()
        if self.root.exists():
            raise ValueError("workflow_output_exists")
        self.spec = get_problem(problem)
        self.problem = problem
        self.model = model
        self.endpoint = endpoint
        self.api_key_env = api_key_env
        self.max_rounds = max_rounds
        self.seed = seed
        self.size = size
        self.count = count
        self.pop_size = pop_size
        self.n_pop = n_pop
        self.max_sample_nums = max_sample_nums
        self.solver_timeout = solver_timeout
        self.request_timeout = request_timeout
        self.memory = memory
        self._injected_plan_request = plan_request
        self._injected_evaluate_request = evaluate_request
        self._execute = execute
        self.solution_min_relative_improvement = solution_min_relative_improvement
        self.repair_mode = repair_mode
        self.max_repairs_per_candidate = int(max_repairs_per_candidate)
        self.max_repair_requests_total = max_repair_requests_total
        self._repair_requests_used = 0
        self.budget = RequestBudget(max_requests)
        self.deadline = time.monotonic() + wall_seconds
        self.current_incumbent: Path | None = None
        self.current_objective: float | None = None
        self.round_summaries: list[dict[str, Any]] = []
        self.started_at = time.monotonic()
        self.suite = self.spec.build_suite(self.seed, count=self.count, size=self.size)

    def run(self) -> dict[str, Any]:
        self.root.mkdir(parents=True, exist_ok=False)
        (self.root / "rounds").mkdir()
        overall = {
            "problem": self.problem, "suite_hash": self.suite["content_hash"],
            "evaluator_hash": evaluator_source_hash(), "status": "running", "max_rounds": self.max_rounds,
            "max_requests": self.budget.max_requests, "wall_seconds": self.deadline - self.started_at,
            "memory_enabled": self.memory is not None, "rounds": [],
            "solution_min_relative_improvement": self.solution_min_relative_improvement,
            "solution_policy": {"enabled": self.solution_min_relative_improvement is not None,
                                "problem": self.problem, "suite_hash": self.suite["content_hash"],
                                "evaluator_hash": evaluator_source_hash(), "direction": self.spec.objective_direction,
                                "comparison": "positive_baseline_relative_improvement_v1",
                                "baseline_code_sha256": hashlib.sha256(self.spec.baseline_code.encode("utf-8")).hexdigest(),
                                "minimum": self.solution_min_relative_improvement},
            "repair_mode": self.repair_mode,
            "max_repairs_per_candidate": self.max_repairs_per_candidate,
            "max_repair_requests_total": self.max_repair_requests_total,
        }
        self._write_root(overall)
        for round_id in range(1, self.max_rounds + 1):
            if self._remaining_wall() <= 0:
                overall.update(status="stopped", stop_reason="wall_time_limit")
                break
            if self.budget.remaining is not None and self.budget.remaining <= 0:
                overall.update(status="stopped", stop_reason="request_limit")
                break
            summary = self._run_round(round_id)
            self.round_summaries.append(summary)
            overall["rounds"] = self.round_summaries
            if summary.get("status") != "round_finished":
                stop_reason = summary.get("stop_reason", "round_failed")
                provider_terminal = summary.get("eoh", {}).get("status") == "provider_failed" or str(stop_reason).startswith("provider_failed")
                overall.update(status="provider_failed" if provider_terminal else "stopped", stop_reason=stop_reason)
                break
            eoh_status = summary.get("eoh", {}).get("status")
            if eoh_status in {"provider_failed", "storage_failed", "invalid_input", "engine_failed", "export_failed"}:
                overall.update(status="stopped", stop_reason=f"eoh_{eoh_status}")
                break
        else:
            overall.update(status="completed", stop_reason="round_limit")
        if overall["status"] == "running":
            overall.update(status="completed", stop_reason="round_limit")
        overall.update(
            request_used=self.budget.used,
            request_rejected=self.budget.rejected,
            remaining_requests=self.budget.remaining,
            repair_requests_used=self._repair_requests_used,
            elapsed_seconds=max(0.0, time.monotonic() - self.started_at),
        )
        # Avoid using the derived elapsed expression as an authority; the
        # durable deadline remains the source of stop decisions.
        overall["budget_events"] = self.budget.events
        self._write_root(overall)
        return overall

    def _run_round(self, round_id: int) -> dict[str, Any]:
        round_root = self.root / "rounds" / f"round_{round_id:04d}"
        state = RoundState(
            round_id, self.problem, self.suite["content_hash"], evaluator_source_hash(),
            incumbent_ref=self._relative_incumbent(),
            previous_round_ref=f"rounds/round_{round_id - 1:04d}" if round_id > 1 else None,
            remaining_requests=self.budget.remaining, deadline=self.deadline,
        )
        controller = WorkflowRound(round_root, state, memory_enabled=self.memory is not None)
        prompt_response: dict[str, Any] = {"exchanges": []}
        try:
            previous = self.round_summaries[-1] if self.round_summaries else None
            memory_rows = self._read_memory(round_root)
            feedback_ref = f"rounds/round_{round_id - 1:04d}/evaluation_facts.json" if previous else None
            feedback_refs = {feedback_ref} if feedback_ref else None
            feedback_reference = None if feedback_ref is None else {
                "round_id": round_id - 1,
                "evaluation_ref": feedback_ref,
                "suite_hash": state.suite_hash,
            }
            skill_refs = {self._relative_incumbent()} if self._relative_incumbent() else set()
            prompt = PlanPrompt(
                problem=self.problem,
                suite_hash=state.suite_hash,
                round_id=round_id,
                incumbent=self._incumbent_fact(),
                feedback=previous,
                feedback_reference=feedback_reference,
                memory=tuple(memory_rows),
                problem_contract=self._problem_contract(),
                mode="select_memory" if memory_rows else "final",
            )
            plan_role = PlanRole(self._role_request(prompt_response, round_root))
            plan = plan_role.run(
                prompt,
                read_memory=self._read_memory_body,
                expected_round_id=round_id,
                suite_hash=state.suite_hash,
                available_feedback_refs=feedback_refs,
                available_memory_refs={row["reference"] for row in memory_rows},
                expected_feedback_round_id=round_id - 1 if previous else None,
                available_skill_refs=skill_refs,
            )
            self._save_role_response(round_root, prompt_response)
            controller.record_plan(plan)
            selected_memory = [dict(row) for row in plan_role.consumed_memory if row["reference"] in plan.memory_basis]
            if plan_role.memory_failures:
                _atomic_json(round_root / "memory_read_failed.json", {"errors": plan_role.memory_failures, "degraded": True})
            if selected_memory:
                _atomic_json(round_root / "memory_consumed.json", {
                    "references": [item.get("reference") for item in selected_memory],
                    "body_sha256": [item.get("body_sha256") for item in selected_memory],
                })
            context = compile_round_context(plan, memory_summaries=selected_memory)
            injected = json.loads(context.split("\n", 1)[1])
            _atomic_json(round_root / "context_manifest.json", {
                "context_sha256": hashlib.sha256(context.encode("utf-8")).hexdigest(),
                "memory_injected": [{"reference": row["reference"],
                                     "body_sha256": row.get("body_sha256"),
                                     "injected_sha256": hashlib.sha256(row["body"].encode("utf-8")).hexdigest()}
                                    for row in injected["memory"]],
                "omitted_memory_refs": injected.get("omitted_memory_refs", []),
                "advisory_truncated": injected.get("advisory_truncated", False),
                "advisory_omitted": injected.get("advisory_omitted", False),
            })
            controller.begin_execute(round_context=context)
            execute_summary = self._execute_round(round_root, state, plan)
            facts = self._trusted_facts(round_root, execute_summary)
            controller.record_evaluation(facts)
            # Incumbent acceptance is a deterministic EoH/evidence decision;
            # it must not depend on a later, optional Evaluate or Memory call.
            self._update_incumbent(round_root, execute_summary)
            controller.state.incumbent_ref = self._relative_incumbent()
            controller._write_state()
            if self._eoh_terminal(execute_summary) or self._remaining_wall() <= 0:
                reason = self._eoh_stop_reason(execute_summary) or "wall_time_limit"
                _atomic_json(round_root / "evaluate_skipped.json", {
                    "reason": reason,
                    "program_evaluation": "completed",
                    "agent_evaluate": "skipped",
                    "memory_decision": "not_run",
                })
                controller.update_remaining_requests(self.budget.remaining)
                controller.stop(reason)
                summary = {"round_id": round_id, "status": controller.state.status,
                           "stop_reason": reason, "eoh": execute_summary, "evaluation_facts": facts,
                           "state": controller.state.as_dict()}
                self._write_root({"rounds": [*self.round_summaries, summary], "request_used": self.budget.used,
                                  "remaining_requests": self.budget.remaining})
                _atomic_json(round_root / "round_summary.json", summary)
                return summary
            evaluation = self._evaluate(round_root, plan, facts, prompt_response)
            if evaluation is None:
                controller.update_remaining_requests(self.budget.remaining)
                controller.stop("evaluate_skipped_budget_or_deadline")
                summary = {"round_id": round_id, "status": controller.state.status,
                           "stop_reason": controller.state.stop_reason, "eoh": execute_summary,
                           "evaluation_facts": facts,
                           "state": controller.state.as_dict()}
                self._write_root({"rounds": [*self.round_summaries, summary], "request_used": self.budget.used,
                                  "remaining_requests": self.budget.remaining})
                _atomic_json(round_root / "round_summary.json", summary)
                return summary
            controller.record_memory_decision(evaluation)
            self._write_memory_action(round_root, evaluation, facts)
            controller.update_remaining_requests(self.budget.remaining)
            controller.finish()
            summary = {"round_id": round_id, "status": controller.state.status,
                       "eoh": execute_summary, "evaluation_facts": facts,
                       "state": controller.state.as_dict()}
        except (BudgetExhausted, ProviderFailure, ValueError, OSError, KeyError, TypeError, RuntimeError) as exc:
            reason = str(exc) or type(exc).__name__
            # A role request may have reserved a slot immediately before a
            # contract failure.  Persist the post-request remaining budget in
            # the round snapshot before closing the round.
            try:
                controller.update_remaining_requests(self.budget.remaining)
            except ValueError:
                pass
            if isinstance(exc, ProviderFailure):
                try:
                    controller.stop(f"provider_failed:{reason}")
                except ValueError:
                    pass
            elif isinstance(exc, BudgetExhausted):
                try:
                    controller.stop(reason)
                except ValueError:
                    pass
            else:
                try:
                    controller.fail(reason)
                except ValueError:
                    pass
            summary = {"round_id": round_id, "status": controller.state.status,
                       "stop_reason": reason, "state": controller.state.as_dict()}
        self._write_root({"rounds": [*self.round_summaries, summary], "request_used": self.budget.used,
                          "remaining_requests": self.budget.remaining})
        _atomic_json(round_root / "round_summary.json", summary)
        return summary

    def _role_request(self, capture: dict[str, Any], round_root: Path) -> Callable[..., str]:
        capture.setdefault("exchanges", [])

        def request(prompt: str, *, purpose: str, problem: str, timeout: float | None = None) -> str:
            if purpose == "plan" and self._injected_plan_request is not None:
                response = self._injected_plan_request(prompt, purpose=purpose, problem=problem, timeout=timeout)
            elif purpose == "evaluate" and self._injected_evaluate_request is not None:
                response = self._injected_evaluate_request(prompt, purpose=purpose, problem=problem, timeout=timeout)
            else:
                response = self._request_gateway()._forward(prompt, purpose=purpose)
            capture["exchanges"].append({"purpose": purpose, "prompt": prompt, "response": response})
            # Persist provider I/O before Plan/Evaluate contract validation so
            # malformed live responses remain diagnosable.
            self._save_role_response(round_root, capture)
            return response
        return request

    def _request_gateway(self):
        from eoh_frozen.llm_bridge import OpenAIPathBridge
        import secrets
        if not hasattr(self, "_gateway"):
            self._gateway = OpenAIPathBridge(
                self.endpoint, os.environ.get(self.api_key_env, ""), self.model,
                timeout=self.request_timeout, budget=self.budget,
                request_log=self.root / "gateway" / "requests.jsonl",
                wall_seconds=max(0, self._remaining_wall()), problem=self.problem,
                gateway_token=secrets.token_urlsafe(32))
            self._gateway.repair_limit = self.max_repair_requests_total
        return self._gateway

    def _save_role_response(self, round_root: Path, capture: Mapping[str, Any]) -> None:
        exchanges = list(capture.get("exchanges") or [])
        if not exchanges:
            return
        journal_dir = round_root / "journal"
        prompts = journal_dir / "prompts"
        responses = journal_dir / "responses"
        prompts.mkdir(parents=True, exist_ok=True)
        responses.mkdir(parents=True, exist_ok=True)
        index = len(list(prompts.glob("attempt_*.txt"))) + 1
        for exchange in exchanges:
            (prompts / f"attempt_{index}.txt").write_text(str(exchange.get("prompt", "")), encoding="utf-8")
            (responses / f"attempt_{index}.txt").write_text(str(exchange.get("response", "")), encoding="utf-8")
            index += 1
        if isinstance(capture, dict):
            capture["exchanges"] = []

    def _execute_round(self, round_root: Path, state: RoundState, plan: PlanDocument) -> dict[str, Any]:
        remaining_requests = self.budget.remaining
        if remaining_requests is None:
            remaining_requests = 10**9
        # Keep one actual outbound slot for Evaluate when it is not injected.
        # This is a cap reservation, not a ledger entry, so an EoH provider
        # failure does not consume an imaginary request.
        evaluate_reserve = 0 if self._injected_evaluate_request is not None else 1
        eoh_requests = remaining_requests - evaluate_reserve
        if self._execute is None and eoh_requests <= 0:
            raise BudgetExhausted("request_limit_evaluate_reserved")
        remaining_wall = self._remaining_wall()
        if remaining_wall <= 0:
            raise BudgetExhausted("wall_time_limit")
        if self._execute is not None:
            result = self._execute(round_root=round_root, plan=plan, max_requests=max(0, eoh_requests),
                                   wall_seconds=remaining_wall, parent_skill=self.current_incumbent)
        else:
            result = self._execute_subprocess(round_root, eoh_requests, remaining_wall)
        used = self._request_count(round_root / "eoh_run", fallback=result.get("http_requests", 0))
        result = dict(result)
        result["http_requests"] = used
        repair = result.get("repair")
        if not isinstance(repair, Mapping):
            repair_events = round_root / "eoh_run" / "results" / "repair_events.jsonl"
            attempted_events = 0
            if repair_events.is_file():
                for line in repair_events.read_text(encoding="utf-8").splitlines():
                    try:
                        event = json.loads(line)
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        continue
                    attempted_events += event.get("state") == "request_started"
            if attempted_events:
                repair = {"attempted": attempted_events}
        if isinstance(repair, Mapping):
            attempted = repair.get("attempted")
            if isinstance(attempted, int) and not isinstance(attempted, bool) and attempted >= 0:
                self._repair_requests_used += attempted
        records = self._request_records(round_root / "eoh_run")
        gateway_record = round_root / "request_gateway.json"
        if self._execute is None and gateway_record.is_file():
            used = json.loads(gateway_record.read_text(encoding="utf-8"))["http_requests"]
            result["http_requests"] = used
            self._repair_requests_used = self._request_gateway().repair_used
        if self._execute is not None:  # Explicit offline fixture boundary only.
            self.budget.consume_external(
                int(used), purpose="eoh", problem=self.problem, model=self.model,
                records=records if len(records) == used else None,
            )
        return result

    def _execute_subprocess(self, round_root: Path, max_requests: int, wall_seconds: float) -> dict[str, Any]:
        from agent_skill_loop.evaluator import kill_process_tree
        output = round_root / "eoh_run"
        context_file = round_root / "round_context.txt"
        gateway = self._request_gateway()
        gateway.eoh_reserve = 0 if self._injected_evaluate_request is not None else 1
        gateway.start()
        before_requests = self.budget.used
        command = [sys.executable, "-m", "agent_skill_loop", "run", "--problem", self.problem,
                   "--model", self.model, "--output", str(output), "--endpoint", gateway.local_url,
                   "--api-key-env", "WORKFLOW_GATEWAY_TOKEN", "--seed", str(self.seed), "--size", str(self.size),
                   "--count", str(self.count), "--pop-size", str(self.pop_size), "--n-pop", str(self.n_pop),
                   "--max-sample-nums", str(self.max_sample_nums), "--max-requests", str(max_requests),
                   "--solver-timeout", str(self.solver_timeout), "--request-timeout", str(self.request_timeout),
                   "--wall-seconds", str(max(0.1, wall_seconds)), "--round-context-file", str(context_file)]
        if self.repair_mode == "bounded":
            command.extend(["--repair-mode", "bounded", "--max-repairs-per-candidate", str(self.max_repairs_per_candidate)])
            if self.max_repair_requests_total is not None:
                remaining_repairs = max(0, self.max_repair_requests_total - self._repair_requests_used)
                command.extend(["--max-repair-requests-total", str(remaining_repairs)])
        if self.current_incumbent is not None:
            command.extend(["--parent-skill", str(self.current_incumbent)])
        env = {key: value for key, value in os.environ.items()
               if key != "PYTHONHOME" and key != self.api_key_env
               and not any(part in key.upper() for part in ("API_KEY", "TOKEN", "SECRET", "PASSWORD"))}
        env["WORKFLOW_GATEWAY_TOKEN"] = gateway.gateway_token
        env["AGENT_SKILL_SKIP_DOTENV"] = "1"
        env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
        log_file = (round_root / "eoh_process.log").open("w", encoding="utf-8")
        try:
            proc = subprocess.Popen(command, cwd=str(Path(__file__).resolve().parents[1]), env=env,
                                    stdout=log_file, stderr=subprocess.STDOUT, text=True)
        except OSError:
            log_file.close()
            gateway.stop()
            gateway.eoh_reserve = 0
            raise
        stopped_reason: str | None = None
        try:
            while proc.poll() is None:
                if self._remaining_wall() <= 0:
                    kill_process_tree(proc)
                    stopped_reason = "wall_time_limit"
                    break
                try:
                    proc.wait(timeout=min(0.1, self._remaining_wall()))
                except subprocess.TimeoutExpired:
                    pass
        finally:
            if proc.poll() is None:
                kill_process_tree(proc)
            gateway.stop()
            # Deadline transport closes the outstanding request before final
            # accounting; child cancellation never turns unknown usage into 0.
            with gateway._forward_lock:
                pass
            gateway.eoh_reserve = 0
            log_file.close()
            _atomic_json(round_root / "request_gateway.json", {
                "first_global_index": before_requests + 1, "last_global_index": self.budget.used,
                "http_requests": self.budget.used - before_requests,
                "terminal": gateway.terminal, "last_error": gateway.last_error})
        if gateway.terminal and stopped_reason is None:
            stopped_reason = "provider_failed:" + str(gateway.last_error)
        if stopped_reason is not None:
            try:
                proc.wait(timeout=1.0)
            except (subprocess.TimeoutExpired, OSError):
                pass
            return self._recover_partial_eoh(output, stopped_reason)
        if proc.returncode not in {0, 2}:
            return self._recover_partial_eoh(output, "eoh_process_failed")
        summary_path = output / "summary.json"
        if not summary_path.is_file():
            return self._recover_partial_eoh(output, "eoh_summary_missing")
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        summary["http_requests"] = self._request_count(output, fallback=summary.get("http_requests", 0))
        return summary

    def _evaluate(self, round_root: Path, plan: PlanDocument, facts: Mapping[str, Any], capture: dict[str, Any]) -> EvaluateDocument | None:
        if self._remaining_wall() <= 0 or (self.budget.remaining is not None and self.budget.remaining <= 0):
            _atomic_json(round_root / "evaluate_skipped.json", {
                "reason": "evaluate_skipped_budget_or_deadline",
                "program_evaluation": "completed",
                "agent_evaluate": "skipped",
                "memory_decision": "not_run",
            })
            return None
        prompt = EvaluatePrompt(
            self.problem,
            plan.feedback_basis.suite_hash if plan.feedback_basis else facts.get("suite_hash", ""),
            plan.as_dict(), dict(facts), self.memory is not None,
            self._problem_contract(),
        )
        role = EvaluateRole(self._role_request(capture, round_root))
        try:
            result = role.run(prompt)
        except Exception:
            # Preserve the raw provider response even when contract parsing
            # fails, so a live run remains fully diagnosable and replayable.
            self._save_role_response(round_root, capture)
            raise
        self._save_role_response(round_root, capture)
        return result

    def _write_memory_action(self, round_root: Path, evaluation: EvaluateDocument, facts: Mapping[str, Any]) -> None:
        action = evaluation.memory_action
        if self.memory is None or action.kind in {"disabled", "none"}:
            return
        if action.kind == "solution" and not self._solution_eligible(round_root, facts, action):
            _atomic_json(round_root / "memory_rejected.json", {"reason": "solution_gate_not_met", "action": action.as_dict()})
            return
        model_scene = action.scene or self.spec.entrypoint
        scope = (
            f"Memory scope: problem={self.problem}; entrypoint={self.spec.entrypoint}; "
            f"suite_hash={self.suite['content_hash']}; evaluator_hash={evaluator_source_hash()}."
        )
        if model_scene != self.spec.entrypoint:
            scope += f"\nModel-proposed scene label: {model_scene}."
        body = scope + "\n\n" + (action.body or "")
        entry = MemoryEntry(action.name or "unnamed", action.description or "", action.kind,
                            action.project or self.problem, self.spec.entrypoint, body)
        try:
            # A solution's ``based_on`` normally names the generated skill
            # that just passed the gate, not a previous Markdown version.  It
            # is provenance, so it must not be sent to the memory version
            # updater.  Insight updates may use a versioned memory reference.
            ref = action.based_on if isinstance(action.based_on, str) and "@v" in action.based_on else None
            same_entry = ref is not None and ref.rsplit("@v", 1)[0] == f"{entry.project}/{entry.type}_{entry.name}"
            result = self.memory.write(entry, based_on=ref if same_entry else None,
                                       related_refs=(ref,) if ref and not same_entry else ())
            _atomic_json(round_root / "memory_result.json", result)
        except (OSError, ValueError) as exc:
            _atomic_json(round_root / "memory_result.json", {"written": False, "error": str(exc)})

    def _solution_eligible(self, round_root: Path, facts: Mapping[str, Any], action: Any) -> bool:
        if self.solution_min_relative_improvement is None:
            return False
        generated = facts.get("generated_valid_candidates", 0)
        best = facts.get("best_generated_path")
        baseline = facts.get("baseline", {}).get("objective") if isinstance(facts.get("baseline"), dict) else None
        if not (generated and best and isinstance(baseline, (int, float)) and not isinstance(baseline, bool) and math.isfinite(baseline)):
            return False
        if not any(row.get("origin") == "baseline" and
                   row.get("code_sha256") == hashlib.sha256(self.spec.baseline_code.encode("utf-8")).hexdigest() and
                   row.get("evaluation", {}).get("valid") is True and
                   row.get("evaluation", {}).get("objective") == baseline and
                   row.get("evaluation", {}).get("suite_hash") == self.suite["content_hash"]
                   for row in facts.get("evaluations", [])):
            return False
        skill = round_root / "eoh_run" / str(best)
        if (round_root / "eoh_run").resolve() not in skill.resolve().parents:
            return False
        evidence = skill / "evidence.json"
        reference = action.evidence_ref or action.based_on or ""
        try:
            candidate = load_skill(skill)
            if validate_skill_for_suite(candidate, self.suite) or candidate.suite_hash != self.suite["content_hash"] or candidate.evaluator_hash != evaluator_source_hash() or not candidate.valid or candidate.mean_objective is None:
                return False
            objective = float(candidate.mean_objective)
            improvement = self.spec.solution_improvement(float(baseline), objective)
            if improvement is None or improvement <= 0 or improvement < self.solution_min_relative_improvement:
                return False
            if not evidence.is_file() or not isinstance(reference, str) or reference not in {str(best), f"eoh_run/{best}"}:
                return False
            evidence_payload = json.loads(evidence.read_text(encoding="utf-8"))
            line = evidence_payload.get("evaluation_line")
            if not isinstance(line, int) or evidence_payload.get("local_objective") != objective:
                return False
            evaluations = facts.get("evaluations") or []
            matching = [row for row in evaluations if row.get("evaluation_line") == line]
            return any(row.get("code_sha256") == candidate.code_sha256 and
                       row.get("problem") == self.problem and
                       row.get("entrypoint") == self.spec.entrypoint and
                       isinstance(row.get("evaluation"), dict) and
                       row["evaluation"].get("suite_hash") == self.suite["content_hash"] and
                       row["evaluation"].get("objective") == objective and
                       row["evaluation"].get("valid") is True and
                       bool(row.get("evaluation_id")) and evidence_payload.get("evaluation_id") == row.get("evaluation_id") and
                       evidence_payload.get("source_request_index") == row.get("source_request_index")
                       for row in matching)
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            return False

    def _read_memory(self, round_root: Path | None = None) -> list[dict[str, Any]]:
        if self.memory is None:
            return []
        try:
            result = self.memory.read_index(project=self.problem, scene=self.spec.entrypoint, limit=4)
        except (OSError, ValueError) as exc:
            if round_root is not None:
                _atomic_json(round_root / "memory_read_failed.json", {"error": str(exc), "degraded": True})
            return []
        return [{key: value for key, value in row.items() if key in {"reference", "name", "type", "description", "scene", "age_label", "cross_project", "version", "body_sha256"}}
                for row in result["memories"]]

    def _read_memory_body(self, reference: str) -> Mapping[str, Any]:
        if self.memory is None:
            raise ValueError("memory_disabled")
        result = self.memory.read_version(reference)
        return result

    def _trusted_facts(self, round_root: Path, summary: Mapping[str, Any]) -> dict[str, Any]:
        facts = dict(summary)
        facts["evaluations"] = []
        path = round_root / "eoh_run" / "results" / "evaluations.jsonl"
        if path.is_file():
            for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                facts["evaluations"].append({
                    key: row.get(key) for key in
                    ("code_sha256", "problem", "entrypoint", "origin", "source_request_index", "evaluation",
                     "evaluation_id", "candidate_id", "revision", "original_code_sha256",
                     "generation_request_ref", "repair_request_ref", "suite_hash", "evaluator_hash")
                    if key in row
                })
                facts["evaluations"][-1]["evaluation_line"] = line_number
        # Read actual code only from hash-validated evaluation evidence. Keep
        # full identity rows for publication gates; bound advisory source text.
        from eoh_frozen.export import read_evidence, _read_repair_records
        rows = read_evidence(round_root / "eoh_run", self.suite)
        valid = [row for row in rows if row["evaluation"]["valid"]]
        generated_rows = [row for row in valid if row.get("origin") in {"generated", "generated_repair"}]
        best = min(generated_rows, key=lambda row: row["evaluation"]["objective"]) if generated_rows else None
        original = next((row for row in rows if best and row.get("candidate_id") == best.get("candidate_id")
                         and row.get("revision") == "original"), None)
        if original is best or original is None:
            original = next((row for row in valid if row.get("origin") == "explicit_parent"),
                            next((row for row in valid if row.get("origin") == "baseline"), None))
        source_rows = [row for row in (original, best) if row]
        facts["code_evidence"] = [{"evaluation_id": row.get("evaluation_id"), "code_sha256": row["code_sha256"],
                                  "revision": row.get("revision"), "code": row["code"][:8000],
                                  "truncated": len(row["code"]) > 8000} for row in source_rows]
        facts["repair_lineage"] = [{key: row.get(key) for key in (
            "candidate_id", "state", "revision", "original_code_sha256", "evaluated_code_sha256",
            "generation_request_ref", "repair_request_ref", "repair_evaluation_id", "repair_summary")}
            for row in _read_repair_records(round_root / "eoh_run")[-8:]]
        if original and best and original is not best:
            diff = "\n".join(difflib.unified_diff(original["code"].splitlines(), best["code"].splitlines()))
            facts["code_diff"] = {"text": diff[:4000], "truncated": len(diff) > 4000}
        return facts

    def _incumbent_fact(self) -> dict[str, Any] | None:
        if self.current_incumbent is None:
            return None
        try:
            skill = load_skill(self.current_incumbent)
            payload = skill.metadata()
            payload["ref"] = self._relative_incumbent()
            return payload
        except (OSError, ValueError, json.JSONDecodeError):
            return {"ref": str(self.current_incumbent)}

    def _update_incumbent(self, round_root: Path, summary: Mapping[str, Any]) -> None:
        eoh_root = round_root / "eoh_run"
        generated = summary.get("best_generated_path")
        options: list[tuple[float, Path]] = []
        if self.current_incumbent is not None:
            loaded = self._load_suite_skill(self.current_incumbent)
            if loaded is not None and loaded.mean_objective is not None:
                options.append((float(loaded.mean_objective), self.current_incumbent))
        if generated:
            candidate = eoh_root / str(generated)
            loaded = self._load_suite_skill(candidate)
            if loaded is not None and loaded.mean_objective is not None:
                options.append((float(loaded.mean_objective), candidate))
        exported = summary.get("exported_skill")
        if exported:
            candidate = eoh_root / str(exported)
            loaded = self._load_suite_skill(candidate)
            if loaded is not None and loaded.mean_objective is not None:
                options.append((float(loaded.mean_objective), candidate))
        if options:
            objective, path = min(options, key=lambda item: (item[0], str(item[1])))
            self.current_incumbent, self.current_objective = path, objective

    def _load_suite_skill(self, path: Path):
        try:
            skill = load_skill(path)
            if not skill.valid or validate_skill_for_suite(skill, self.suite) or skill.suite_hash != self.suite["content_hash"] or skill.evaluator_hash != evaluator_source_hash():
                return None
            return skill
        except (OSError, ValueError, json.JSONDecodeError):
            return None

    def _request_count(self, output: Path, *, fallback: Any = 0) -> int:
        records = self._request_records(output)
        if records:
            return len(records)
        return int(fallback) if isinstance(fallback, int) and not isinstance(fallback, bool) and fallback >= 0 else 0

    def _request_records(self, output: Path) -> list[dict[str, Any]]:
        """Collapse child reserved/terminal events into one record per POST."""
        path = Path(output) / "results" / "requests.jsonl"
        grouped: dict[int, list[dict[str, Any]]] = {}
        if not path.is_file():
            return []
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                item = json.loads(line)
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            index = item.get("index")
            if isinstance(index, int) and not isinstance(index, bool):
                grouped.setdefault(index, []).append(item)
        records: list[dict[str, Any]] = []
        for index in sorted(grouped):
            events = grouped[index]
            terminal = next((event for event in reversed(events) if event.get("state") != "reserved"), events[-1])
            records.append({
                "purpose": terminal.get("purpose", "eoh"),
                "problem": terminal.get("problem", self.problem),
                "model": terminal.get("model", self.model),
                "status": terminal.get("status"),
                "error_code": terminal.get("error_code"),
                "elapsed_seconds": terminal.get("elapsed_seconds"),
                "input_tokens": terminal.get("input_tokens"),
                "output_tokens": terminal.get("output_tokens"),
                "finish_reason": terminal.get("finish_reason"),
                "selected_content_field": terminal.get("selected_content_field"),
            })
        return records

    def _recover_partial_eoh(self, output: Path, reason: str) -> dict[str, Any]:
        from eoh_frozen.export import export_run_evidence, finalize_evaluations
        output.mkdir(parents=True, exist_ok=True)
        (output / "results" / "evaluation_starts").mkdir(parents=True, exist_ok=True)
        summary: dict[str, Any] = {
            "problem": self.problem, "search": "official_eoh", "suite_hash": self.suite["content_hash"],
            "evaluator_hash": evaluator_source_hash(), "status": "stopped" if reason in {"wall_time_limit", "request_limit"} else "engine_failed",
            "stop_reason": reason, "loop_completed": False,
        }
        if reason.startswith("provider_failed:"):
            summary.update(status="provider_failed", provider_error_code=reason.split(":", 1)[1])
        try:
            summary.update(finalize_evaluations(output, self.suite, stop_reason=reason))
            summary.update(export_run_evidence(output, self.suite))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            summary.update(export_status="failed", export_error=type(exc).__name__)
        summary["http_requests"] = self._request_count(output)
        _atomic_json(output / "summary.json", summary)
        return summary

    @staticmethod
    def _eoh_terminal(summary: Mapping[str, Any]) -> bool:
        status = summary.get("status")
        reason = summary.get("stop_reason")
        return status in {"provider_failed", "storage_failed", "invalid_input", "engine_failed", "export_failed"} or reason in {"wall_time_limit", "wall_time_exhausted", "eoh_process_failed", "eoh_summary_missing"}

    @staticmethod
    def _eoh_stop_reason(summary: Mapping[str, Any]) -> str | None:
        if summary.get("status") == "provider_failed":
            return f"provider_failed:{summary.get('provider_error_code') or summary.get('stop_reason') or 'unknown'}"
        if summary.get("status") in {"storage_failed", "engine_failed", "export_failed", "invalid_input"}:
            return f"eoh_{summary.get('status')}"
        return summary.get("stop_reason")

    def _problem_contract(self) -> dict[str, Any]:
        return {
            "problem": self.spec.problem_id,
            "entrypoint": self.spec.entrypoint,
            "interface_version": self.spec.interface_version,
            "task_description": self.spec.task_description,
            "template_program": self.spec.template_program,
            "objective_direction": self.spec.objective_direction,
            "suite_hash": self.suite["content_hash"],
            "evaluator_hash": evaluator_source_hash(),
        }

    def _relative_incumbent(self) -> str | None:
        if self.current_incumbent is None:
            return None
        try:
            return self.current_incumbent.relative_to(self.root).as_posix()
        except ValueError:
            return str(self.current_incumbent)

    def _remaining_wall(self) -> float:
        return self.deadline - time.monotonic()

    @staticmethod
    def _disabled_action():
        from agent_skill_loop.contracts_3plus1 import MemoryAction
        return MemoryAction("disabled")

    def _write_root(self, payload: Mapping[str, Any]) -> None:
        if self.root.exists():
            path = self.root / "workflow.json"
            previous = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
            _atomic_json(path, {**previous, **dict(payload)})
