"""Injectable fixture loop for offline contract tests.

Production CLI runs use the pinned official EoH adapter.  This harness remains
useful for deterministic evaluator and persistence tests and is intentionally
not presented as a second production search engine.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Mapping

from agent_skill_loop.client import ProviderFailure
from tests.fixtures.client import LiveTransport
from agent_skill_loop.contracts import (
    DEFAULT_COUNT,
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_SEED,
    DEFAULT_SIZE,
    DEFAULT_SOLVER_TIMEOUT,
    DEFAULT_SPLIT,
    DEFAULT_WALL_SECONDS,
    PROBLEM_CVRP,
    EvaluationResult,
    SkillVersion,
)
from agent_skill_loop.evaluator import SubprocessEvaluator, evaluator_source_hash
from agent_skill_loop.journal import Journal, sha256_text
from tests.fixtures.generator import PromptFeedback, build_prompt, extract
from tests.fixtures.policy import FixedSearchPolicy, fixture_policy_identity
from agent_skill_loop.problems.base import ProblemSpec, get_problem
from tests.fixtures.report import write_run_report
from tests.fixtures.contracts import DEFAULT_CANDIDATE_ATTEMPTS, DEFAULT_MAX_LLM_REQUESTS, AttemptRecord, RunSummary
from agent_skill_loop.skill_store import make_skill, publish_export_ref, save_skill


def source_version() -> str | None:
    """Best-effort git HEAD of the package repo; None when unavailable."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(Path(__file__).resolve().parents[1]), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if proc.returncode == 0:
            return proc.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        pass
    return None


class AgentLoop:
    def __init__(
        self,
        output_dir: Path,
        *,
        transport,
        suite: dict | None = None,
        parent_skill: SkillVersion | None = None,
        execution_mode: str = "fixture",
        candidate_attempts: int = DEFAULT_CANDIDATE_ATTEMPTS,
        max_llm_requests: int = DEFAULT_MAX_LLM_REQUESTS,
        solver_timeout: float = DEFAULT_SOLVER_TIMEOUT,
        request_timeout: float = DEFAULT_REQUEST_TIMEOUT,
        wall_seconds: float = DEFAULT_WALL_SECONDS,
        monotonic: Callable[[], float] = time.monotonic,
        seed: int = DEFAULT_SEED,
        size: int = DEFAULT_SIZE,
        count: int = DEFAULT_COUNT,
        split: str = DEFAULT_SPLIT,
        model: str | None = None,
        problem_spec: ProblemSpec | None = None,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.transport = transport
        if execution_mode != "fixture":
            raise ValueError(f"agent_loop_is_fixture_only:{execution_mode}")
        self.execution_mode = "fixture"
        if isinstance(transport, LiveTransport):
            raise ValueError("live_transport_not_allowed_in_fixture_loop")
        self.problem_spec = problem_spec if problem_spec is not None else get_problem(PROBLEM_CVRP)
        if suite is not None:
            suite_problem = suite.get("problem") if isinstance(suite, Mapping) else None
            if suite_problem != self.problem_spec.problem_id:
                raise ValueError(
                    f"suite_problem_mismatch:{suite_problem}->{self.problem_spec.problem_id}"
                )
        if parent_skill is not None:
            if parent_skill.problem != self.problem_spec.problem_id:
                raise ValueError(
                    f"parent_problem_mismatch:{parent_skill.problem}->{self.problem_spec.problem_id}"
                )
            if parent_skill.entrypoint != self.problem_spec.entrypoint:
                raise ValueError(
                    f"parent_entrypoint_mismatch:{parent_skill.entrypoint}->{self.problem_spec.entrypoint}"
                )
        self.policy = FixedSearchPolicy()
        self.candidate_attempts_limit = candidate_attempts
        self.max_llm_requests = max_llm_requests
        self.request_timeout = request_timeout
        self.wall_seconds = wall_seconds
        self.monotonic = monotonic
        self.started = monotonic()
        self.solver_timeout = solver_timeout
        self.evaluator = SubprocessEvaluator(timeout=solver_timeout)
        self.journal = Journal(self.output_dir / "run")
        self.seed = seed
        self.size = size
        self.count = count
        self.split = split
        self.suite = suite or self.problem_spec.build_suite(seed, split=split, count=count, size=size)
        self.parent_skill = parent_skill
        self.model = model if model is not None else getattr(transport, "model", None)
        self.request_budget = getattr(transport, "budget", None)
        self.llm_requests = 0
        self.solver_calls = 0
        self.generated_valid = 0
        self.feedback_consumed = 0
        self.attempts: list[AttemptRecord] = []
        self.incumbent: SkillVersion | None = None
        self.incumbent_is_generated = False
        self.best_generated: SkillVersion | None = None
        self.non_improving_e1 = 0
        self.seen_code: set[str] = set()

    def remaining_wall(self) -> float:
        return self.wall_seconds - (self.monotonic() - self.started)

    def _evaluate(self, code: str) -> EvaluationResult:
        timeout = min(self.solver_timeout, max(0.05, self.remaining_wall()))
        self.solver_calls += 1
        return SubprocessEvaluator(timeout=timeout).evaluate(code, self.suite)

    def _store(self, skill: SkillVersion, folder: str, *, generated: bool) -> Path:
        path = self.output_dir / "skills" / folder
        save_skill(path, skill)
        if generated and skill.valid:
            if self.best_generated is None or self.policy.accept(skill.mean_objective, self.best_generated.mean_objective):
                self.best_generated = skill
                publish_export_ref(self.output_dir, path)
        return path

    def _bind_skill(
        self,
        *,
        version_id: str,
        code: str,
        evaluation: EvaluationResult,
        parent_version_id: str | None,
        source_attempt_id: int | None,
        description: str,
        repair_of_attempt_id: int | None = None,
    ) -> SkillVersion:
        return make_skill(
            version_id=version_id,
            code=code,
            suite_hash=str(self.suite["content_hash"]),
            valid=evaluation.valid,
            mean_objective=evaluation.objective,
            instance_objectives=evaluation.instance_objectives,
            parent_version_id=parent_version_id,
            source_attempt_id=source_attempt_id,
            description=description,
            problem=self.problem_spec.problem_id,
            entrypoint=self.problem_spec.entrypoint,
            repair_of_attempt_id=repair_of_attempt_id,
            search_policy_id=self.policy.policy_id,
            search_policy_version=self.policy.policy_version,
            search_policy_fixture_only=True,
        )

    def _install_incumbent(self, skill: SkillVersion, *, generated: bool) -> None:
        if not skill.valid:
            return
        incumbent_objective = None if self.incumbent is None else self.incumbent.mean_objective
        if self.policy.accept(skill.mean_objective, incumbent_objective):
            self.incumbent = skill
            self.incumbent_is_generated = generated

    def seed_start(self) -> None:
        if self.parent_skill is not None:
            evaluation = self._evaluate(self.parent_skill.code)
            parent = self._bind_skill(
                version_id="parent_reloaded",
                code=self.parent_skill.code,
                evaluation=evaluation,
                parent_version_id=self.parent_skill.version_id,
                source_attempt_id=None,
                description="explicit parent re-evaluated on frozen suite",
            )
            if not parent.valid:
                raise ValueError("parent_skill_invalid_on_suite")
            # Do not place an invalid re-evaluation in the reusable skill store.
            # The caller still receives the explicit parent_invalid terminal
            # state and can inspect the original asset and journal.
            self._store(parent, "parent_reloaded", generated=False)
            self._install_incumbent(parent, generated=False)
            self.seen_code.add(sha256_text(parent.code))
            return
        evaluation = self._evaluate(self.problem_spec.baseline_code)
        baseline = self._bind_skill(
            version_id="baseline",
            code=self.problem_spec.baseline_code,
            evaluation=evaluation,
            parent_version_id=None,
            source_attempt_id=None,
            description=self.problem_spec.baseline_description or "deterministic nearest-neighbor baseline",
        )
        self._store(baseline, "baseline", generated=False)
        if not baseline.valid:
            raise ValueError("baseline_invalid")
        self._install_incumbent(baseline, generated=False)
        self.seen_code.add(sha256_text(baseline.code))

    def _write_frozen_config(self) -> None:
        config = {
            "problem": self.problem_spec.problem_id,
            "interface_version": self.problem_spec.interface_version,
            "entrypoint": self.problem_spec.entrypoint,
            "seed": self.seed,
            "size": self.size,
            "count": self.count,
            "split": self.split,
            "candidate_attempts": self.candidate_attempts_limit,
            "max_llm_requests": self.max_llm_requests,
            "solver_timeout": self.solver_timeout,
            "request_timeout": self.request_timeout,
            "wall_seconds": self.wall_seconds,
            "suite_hash": self.suite["content_hash"],
            "evaluator_hash": evaluator_source_hash(),
            "execution_mode": self.execution_mode,
            "model": self.model,
            "provider_endpoint": getattr(self.transport, "endpoint", None),
            "request_budget": None if self.request_budget is None else self.request_budget.max_requests,
            "parent_skill_id": None if self.parent_skill is None else self.parent_skill.version_id,
            "search_policy": fixture_policy_identity(),
            "fixture_only": True,
            "source_version": source_version(),
        }
        (self.output_dir / "config_frozen.json").write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    def _feedback(
        self,
        operator: str,
        last: AttemptRecord | None,
        *,
        structural_explore: bool,
    ) -> PromptFeedback | None:
        if operator == "i1":
            return None
        assert self.incumbent is not None
        feedback = PromptFeedback(
            incumbent_id=self.incumbent.version_id,
            incumbent_code=self.incumbent.code,
            incumbent_objective=self.incumbent.mean_objective,
            incumbent_instances=self.incumbent.instance_objectives,
            structural_explore=structural_explore and operator == "e1",
            edit_target=self.policy.edit_target(operator=operator, last=last),
        )
        if last is None:
            return feedback
        delta = None
        if last.evaluation.objective is not None and self.incumbent.mean_objective is not None:
            delta = last.evaluation.objective - self.incumbent.mean_objective
        feedback.last_attempt_id = last.attempt_id
        feedback.last_code = last.code or None
        feedback.last_code_hash = last.code_hash
        feedback.last_valid = last.evaluation.valid
        feedback.last_objective = last.evaluation.objective
        feedback.last_instances = last.evaluation.instance_objectives
        feedback.delta_vs_incumbent = delta
        feedback.accepted = last.accepted_as_incumbent
        feedback.accept_reason = last.accept_reason
        if operator == "m1":
            feedback.error_code = last.evaluation.error_code
            feedback.error_detail = last.evaluation.error_detail
            feedback.raw_reply = last.raw_response or None
            feedback.failed_code = last.code or None
            feedback.structural_explore = False
        return feedback

    def _usage_snapshot(self) -> dict[str, Any]:
        receipts = getattr(self.transport, "usage", None)
        if not receipts:
            return {
                "model": self.model,
                "input_tokens": None,
                "output_tokens": None,
                "request_elapsed_seconds": None,
            }
        last = receipts[-1]
        elapsed = getattr(last, "elapsed_seconds", None)
        tokens_in = last.input_tokens
        tokens_out = last.output_tokens
        if last.error_code == "request_deadline":
            tokens_in = None
            tokens_out = None
        return {
            "model": getattr(last, "model", None) or self.model,
            "input_tokens": tokens_in,
            "output_tokens": tokens_out,
            "request_elapsed_seconds": None if elapsed is None else round(float(elapsed), 4),
        }

    def _accept_reason(
        self,
        *,
        code: str,
        evaluation: EvaluationResult,
        duplicate: bool,
        accepted: bool,
    ) -> str:
        if evaluation.error_code == "wall_time_limit":
            return "rejected_wall_time"
        if not code:
            return "rejected_parse_error"
        if duplicate:
            return "rejected_duplicate"
        if not evaluation.valid:
            return "rejected_invalid"
        if accepted:
            return "accepted_better"
        return "rejected_not_better"

    def _record_attempt(
        self,
        *,
        attempt_id: int,
        operator: str,
        parent_id: str | None,
        failed_hash: str | None,
        prompt_hash: str,
        prompt_path: str,
        code: str,
        evaluation: EvaluationResult,
        raw_response: str,
        description: str = "",
        repair_of_attempt_id: int | None = None,
        feedback_attempt_id: int | None = None,
        edit_target: str | None = None,
    ) -> AttemptRecord:
        stored = code if code else f"# no code extracted\n{raw_response}"
        code_path, code_hash = self.journal.save_code(attempt_id, stored or "# empty\n")
        duplicate = bool(code) and code_hash in self.seen_code
        self.seen_code.add(code_hash)
        accepted = False
        if evaluation.valid and not duplicate:
            self.generated_valid += 1
            skill = self._bind_skill(
                version_id=f"generated_{attempt_id}",
                code=code,
                evaluation=evaluation,
                parent_version_id=parent_id,
                source_attempt_id=attempt_id,
                description=description,
                repair_of_attempt_id=repair_of_attempt_id,
            )
            self._store(skill, skill.version_id, generated=True)
            before = self.incumbent.version_id if self.incumbent else None
            self._install_incumbent(skill, generated=True)
            accepted = (
                self.incumbent is not None
                and self.incumbent.version_id != before
                and self.incumbent.version_id == skill.version_id
            )
        reason = self._accept_reason(code=code, evaluation=evaluation, duplicate=bool(duplicate), accepted=accepted)
        usage = self._usage_snapshot()
        self.journal.append("attempt_result", {
            "attempt_id": attempt_id,
            "operator": operator,
            "code_hash": code_hash,
            "code_path": code_path,
            "duplicate": bool(duplicate),
            "evaluation": evaluation.as_dict(),
            "accepted_as_incumbent": accepted,
            "accept_reason": reason,
            "parent_version_id": parent_id,
            "repair_of_attempt_id": repair_of_attempt_id,
            "feedback_attempt_id": feedback_attempt_id,
            "edit_target": edit_target,
            "llm_requests": self.llm_requests,
            "solver_calls": self.solver_calls,
            "model": usage["model"],
            "input_tokens": usage["input_tokens"],
            "output_tokens": usage["output_tokens"],
            "request_elapsed_seconds": usage["request_elapsed_seconds"],
        })
        record = AttemptRecord(
            attempt_id=attempt_id,
            operator=operator,
            parent_version_id=parent_id,
            failed_code_hash=failed_hash,
            prompt_hash=prompt_hash,
            prompt_path=prompt_path,
            code=code,
            code_hash=code_hash,
            evaluation=evaluation,
            accepted_as_incumbent=accepted,
            llm_requests=self.llm_requests,
            solver_calls=self.solver_calls,
            raw_response=raw_response,
            repair_of_attempt_id=repair_of_attempt_id,
            feedback_attempt_id=feedback_attempt_id,
            accept_reason=reason,
            edit_target=edit_target,
        )
        self.attempts.append(record)
        if operator == "e1":
            if evaluation.valid and not accepted:
                self.non_improving_e1 += 1
            else:
                self.non_improving_e1 = 0
        return record

    def run(self) -> RunSummary:
        (self.output_dir / "dev_suite.json").write_text(
            json.dumps(self.suite, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        self._write_frozen_config()
        try:
            self.seed_start()
        except ProviderFailure as exc:
            return self._finish(False, "provider_failed", "provider_error", provider_error_code=exc.error_code)
        except ValueError as exc:
            if str(exc) == "parent_skill_invalid_on_suite":
                return self._finish(False, "parent_invalid", "invalid_parent")
            raise
        last: AttemptRecord | None = None
        last_valid: bool | None = None
        try:
            while len(self.attempts) < self.candidate_attempts_limit:
                if self.remaining_wall() <= 0:
                    return self._finish(True, self._status(), "wall_time_limit")
                if self.llm_requests >= self.max_llm_requests:
                    return self._finish(True, self._status(), "request_limit")
                operator = self.policy.choose_operator(
                    attempts_done=len(self.attempts),
                    has_explicit_parent=self.parent_skill is not None,
                    last_valid=last_valid,
                )
                attempt_id = len(self.attempts) + 1
                parent_id = self.policy.select_parent(operator=operator, incumbent=self.incumbent, last=last)
                repair_of = last.attempt_id if operator == "m1" and last is not None else None
                failed_hash = sha256_text(last.code or last.raw_response) if operator == "m1" and last is not None else None
                structural = self.policy.structural_explore(operator=operator, non_improving_e1=self.non_improving_e1)
                feedback = self._feedback(operator, last, structural_explore=structural)
                prompt = build_prompt(operator, feedback, self.problem_spec)
                prompt_path, prompt_hash = self.journal.save_prompt(attempt_id, prompt)
                feedback_attempt_id = None if last is None or operator == "i1" else last.attempt_id
                edit_target = None if feedback is None else feedback.edit_target
                self.journal.append("attempt_started", {
                    "attempt_id": attempt_id,
                    "operator": operator,
                    "parent_version_id": parent_id,
                    "repair_of_attempt_id": repair_of,
                    "failed_code_hash": failed_hash,
                    "feedback_attempt_id": feedback_attempt_id,
                    "edit_target": edit_target,
                    "structural_explore": structural,
                    "prompt_hash": prompt_hash,
                    "prompt_path": prompt_path,
                })
                self.llm_requests += 1
                remaining_before = max(0.0, self.remaining_wall())
                request_timeout = min(self.request_timeout, remaining_before)
                deadline_is_wall = remaining_before <= self.request_timeout
                try:
                    response = self.transport.request(
                        prompt,
                        purpose="generation",
                        problem=self.problem_spec.problem_id,
                        timeout=request_timeout,
                    )
                except ProviderFailure as exc:
                    if exc.error_code == "request_deadline" and deadline_is_wall:
                        last = self._record_attempt(
                            attempt_id=attempt_id,
                            operator=operator,
                            parent_id=parent_id,
                            failed_hash=failed_hash,
                            prompt_hash=prompt_hash,
                            prompt_path=prompt_path,
                            code="",
                            evaluation=EvaluationResult(
                                False, None, (), self.suite["content_hash"], "wall_time_limit", 0.0
                            ),
                            raw_response="",
                            repair_of_attempt_id=repair_of,
                            feedback_attempt_id=feedback_attempt_id,
                            edit_target=edit_target,
                        )
                        last_valid = False
                        return self._finish(True, self._status(), "wall_time_limit")
                    raise
                wall_exhausted = self.remaining_wall() <= 0
                description, code = extract(response)
                if feedback is not None:
                    self.feedback_consumed += 1
                if wall_exhausted:
                    evaluation = EvaluationResult(
                        False, None, (), self.suite["content_hash"], "wall_time_limit", 0.0
                    )
                    code = code or ""
                elif not code:
                    evaluation = EvaluationResult(
                        False, None, (), self.suite["content_hash"], "generation_parse_error", 0.0
                    )
                    code = ""
                else:
                    evaluation = self._evaluate(code)
                last = self._record_attempt(
                    attempt_id=attempt_id,
                    operator=operator,
                    parent_id=parent_id,
                    failed_hash=failed_hash,
                    prompt_hash=prompt_hash,
                    prompt_path=prompt_path,
                    code=code,
                    evaluation=evaluation,
                    raw_response=response,
                    description=description,
                    repair_of_attempt_id=repair_of,
                    feedback_attempt_id=feedback_attempt_id,
                    edit_target=edit_target,
                )
                last_valid = evaluation.valid
                if wall_exhausted:
                    return self._finish(True, self._status(), "wall_time_limit")
            return self._finish(True, self._status(), "candidate_limit")
        except ProviderFailure as exc:
            return self._finish(False, "provider_failed", "provider_error", provider_error_code=exc.error_code)

    def _status(self) -> str:
        if self.generated_valid > 0:
            return "completed_with_valid_candidate"
        return "no_valid_candidate"

    def _finish(
        self,
        loop_completed: bool,
        status: str,
        stop_reason: str,
        *,
        provider_error_code: str | None = None,
    ) -> RunSummary:
        exported = [self.best_generated.version_id] if self.best_generated is not None else []
        summary = RunSummary(
            execution_mode=self.execution_mode,
            loop_completed=loop_completed,
            status=status,
            stop_reason=stop_reason,
            generated_valid_candidates=self.generated_valid,
            exported_skill_ids=exported,
            feedback_consumed_count=self.feedback_consumed,
            candidate_attempts=len(self.attempts),
            llm_requests=self.llm_requests,
            solver_calls=self.solver_calls,
            wall_seconds=self.monotonic() - self.started,
            incumbent_version_id=self.incumbent.version_id if self.incumbent else None,
            incumbent_is_generated=self.incumbent_is_generated,
            best_generated_version_id=None if self.best_generated is None else self.best_generated.version_id,
            feedback_then_regenerated=self.feedback_consumed >= 1 and any(
                record.operator in {"e1", "m1"} for record in self.attempts
            ),
        )
        payload = summary.as_dict()
        if provider_error_code:
            payload["provider_error_code"] = provider_error_code
        payload.update({
            "problem": self.problem_spec.problem_id,
            "suite_hash": self.suite["content_hash"],
            "model": self.model,
            "candidate_attempts_limit": self.candidate_attempts_limit,
            "max_llm_requests": self.max_llm_requests,
            "wall_seconds_budget": self.wall_seconds,
            "best_generated_path": None if self.best_generated is None else f"skills/{self.best_generated.version_id}",
            "exported_skill": None if self.best_generated is None else "exported_skill",
            "incumbent_path": None if self.incumbent is None else f"skills/{self.incumbent.version_id}",
        })
        if self.request_budget is not None:
            payload["http_requests"] = self.request_budget.used
            payload["request_rejected"] = self.request_budget.rejected
        self.journal.append("run_finished", payload)
        (self.output_dir / "summary.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        write_run_report(self.output_dir, payload)
        return summary


def prepare_output(path: Path, *, problem_id: str = PROBLEM_CVRP, **suite_kwargs) -> dict:
    path = Path(path)
    path.mkdir(parents=True, exist_ok=False)
    spec = get_problem(problem_id)
    suite = spec.build_suite(**suite_kwargs)
    config = {
        "problem": spec.problem_id,
        "interface_version": spec.interface_version,
        "entrypoint": spec.entrypoint,
        "seed": suite_kwargs.get("seed", DEFAULT_SEED),
        "size": suite_kwargs.get("size", DEFAULT_SIZE),
        "count": suite_kwargs.get("count", DEFAULT_COUNT),
        "split": suite_kwargs.get("split", DEFAULT_SPLIT),
        "candidate_attempts": DEFAULT_CANDIDATE_ATTEMPTS,
        "max_llm_requests": DEFAULT_MAX_LLM_REQUESTS,
        "solver_timeout": DEFAULT_SOLVER_TIMEOUT,
        "request_timeout": DEFAULT_REQUEST_TIMEOUT,
        "wall_seconds": DEFAULT_WALL_SECONDS,
        "suite_hash": suite["content_hash"],
        "evaluator_hash": evaluator_source_hash(),
        "provider_endpoint": None,
        "request_budget": None,
        "search_policy": fixture_policy_identity(),
        "source_version": source_version(),
    }
    (path / "config_frozen.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    (path / "dev_suite.json").write_text(json.dumps(suite, indent=2) + "\n", encoding="utf-8")
    return config
