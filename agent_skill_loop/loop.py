"""Fixed generate / repair / stop loop. No FME actions or analysis calls."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Callable

from agent_skill_loop.client import ProviderFailure
from agent_skill_loop.contracts import (
    DEFAULT_CANDIDATE_ATTEMPTS,
    DEFAULT_COUNT,
    DEFAULT_MAX_LLM_REQUESTS,
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_SEED,
    DEFAULT_SIZE,
    DEFAULT_SOLVER_TIMEOUT,
    DEFAULT_SPLIT,
    DEFAULT_WALL_SECONDS,
    ENTRYPOINT_CVRP,
    PROBLEM_CVRP,
    AttemptRecord,
    EvaluationResult,
    RunSummary,
    SkillVersion,
    better_objective,
    choose_operator,
)
from agent_skill_loop.evaluator import SubprocessEvaluator
from agent_skill_loop.generator import build_prompt, extract
from agent_skill_loop.journal import Journal, sha256_text
from agent_skill_loop.problems.cvrp import BASELINE_CODE, PROBLEM_NAME, build_suite
from agent_skill_loop.skill_store import load_skill, make_skill, save_skill


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
        wall_seconds: float = DEFAULT_WALL_SECONDS,
        monotonic: Callable[[], float] = time.monotonic,
        seed: int = DEFAULT_SEED,
        size: int = DEFAULT_SIZE,
        count: int = DEFAULT_COUNT,
        split: str = DEFAULT_SPLIT,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.transport = transport
        self.execution_mode = execution_mode
        self.candidate_attempts_limit = candidate_attempts
        self.max_llm_requests = max_llm_requests
        self.wall_seconds = wall_seconds
        self.monotonic = monotonic
        self.started = monotonic()
        self.solver_timeout = solver_timeout
        self.evaluator = SubprocessEvaluator(timeout=solver_timeout)
        self.journal = Journal(self.output_dir / "run")
        self.suite = suite or build_suite(seed, split=split, count=count, size=size)
        self.parent_skill = parent_skill
        self.llm_requests = 0
        self.solver_calls = 0
        self.generated_valid = 0
        self.feedback_consumed = 0
        self.attempts: list[AttemptRecord] = []
        self.incumbent: SkillVersion | None = None
        self.incumbent_is_generated = False
        self.exported: list[str] = []
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
            export = self.output_dir / "exported_skill"
            current = self.incumbent.mean_objective if self.incumbent and self.incumbent_is_generated else None
            if better_objective(skill.mean_objective, current) or not (export / "skill.json").exists():
                save_skill(export, skill)
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
            problem=PROBLEM_CVRP,
            entrypoint=ENTRYPOINT_CVRP,
        )

    def _install_incumbent(self, skill: SkillVersion, *, generated: bool) -> None:
        if not skill.valid:
            return
        if self.incumbent is None or better_objective(skill.mean_objective, self.incumbent.mean_objective):
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
            self._store(parent, "parent_reloaded", generated=False)
            if not parent.valid:
                raise ValueError("parent_skill_invalid_on_suite")
            self._install_incumbent(parent, generated=False)
            self.seen_code.add(sha256_text(parent.code))
            return
        evaluation = self._evaluate(BASELINE_CODE)
        baseline = self._bind_skill(
            version_id="baseline",
            code=BASELINE_CODE,
            evaluation=evaluation,
            parent_version_id=None,
            source_attempt_id=None,
            description="deterministic nearest-neighbor baseline",
        )
        self._store(baseline, "baseline", generated=False)
        if not baseline.valid:
            raise ValueError("baseline_invalid")
        self._install_incumbent(baseline, generated=False)
        self.seen_code.add(sha256_text(baseline.code))

    def _prompt_kwargs(self, operator: str, last: AttemptRecord | None) -> dict:
        if operator == "i1":
            return {}
        if operator == "e1":
            assert self.incumbent is not None
            return {
                "parent_code": self.incumbent.code,
                "parent_objective": self.incumbent.mean_objective,
            }
        assert last is not None
        kwargs = {"failed_code": last.code, "error_code": last.evaluation.error_code}
        if self.incumbent is not None:
            kwargs["incumbent_code"] = self.incumbent.code
            kwargs["incumbent_objective"] = self.incumbent.mean_objective
        return kwargs

    def run(self) -> RunSummary:
        (self.output_dir / "dev_suite.json").write_text(
            json.dumps(self.suite, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        try:
            self.seed_start()
        except ProviderFailure as exc:
            return self._finish(False, "provider_failed", "provider_error", provider_error_code=exc.error_code)
        last: AttemptRecord | None = None
        last_valid: bool | None = None
        try:
            while len(self.attempts) < self.candidate_attempts_limit:
                if self.remaining_wall() <= 0:
                    return self._finish(True, self._status(), "wall_time_limit")
                if self.llm_requests >= self.max_llm_requests:
                    return self._finish(True, self._status(), "request_limit")
                operator = choose_operator(
                    attempts_done=len(self.attempts),
                    has_explicit_parent=self.parent_skill is not None,
                    last_valid=last_valid,
                )
                attempt_id = len(self.attempts) + 1
                parent_id = self.incumbent.version_id if self.incumbent else None
                failed_hash = sha256_text(last.code) if operator == "m1" and last is not None else None
                prompt = build_prompt(operator, **self._prompt_kwargs(operator, last))
                prompt_path, prompt_hash = self.journal.save_prompt(attempt_id, prompt)
                self.journal.append("attempt_started", {
                    "attempt_id": attempt_id,
                    "operator": operator,
                    "parent_version_id": parent_id,
                    "failed_code_hash": failed_hash,
                    "prompt_hash": prompt_hash,
                    "prompt_path": prompt_path,
                })
                self.llm_requests += 1
                if operator in {"e1", "m1"}:
                    self.feedback_consumed += 1
                response = self.transport.request(prompt, purpose="generation", problem=PROBLEM_NAME)
                description, code = extract(response)
                if not code:
                    evaluation = EvaluationResult(False, None, (), self.suite["content_hash"], "generation_parse_error", 0.0)
                    code = ""
                else:
                    evaluation = self._evaluate(code)
                code_path, code_hash = self.journal.save_code(attempt_id, code or "# empty\n")
                duplicate = code_hash in self.seen_code and code
                self.seen_code.add(code_hash)
                accepted = False
                exported_id = None
                if evaluation.valid and not duplicate:
                    self.generated_valid += 1
                    skill = self._bind_skill(
                        version_id=f"generated_{attempt_id}",
                        code=code,
                        evaluation=evaluation,
                        parent_version_id=parent_id,
                        source_attempt_id=attempt_id,
                        description=description,
                    )
                    self._store(skill, skill.version_id, generated=True)
                    before = self.incumbent.version_id if self.incumbent else None
                    self._install_incumbent(skill, generated=True)
                    accepted = self.incumbent is not None and self.incumbent.version_id != before and self.incumbent.version_id == skill.version_id
                    exported_id = skill.version_id
                    if skill.valid:
                        self.exported.append(skill.version_id)
                self.journal.append("attempt_result", {
                    "attempt_id": attempt_id,
                    "operator": operator,
                    "code_hash": code_hash,
                    "code_path": code_path,
                    "duplicate": bool(duplicate),
                    "evaluation": evaluation.as_dict(),
                    "accepted_as_incumbent": accepted,
                    "llm_requests": self.llm_requests,
                    "solver_calls": self.solver_calls,
                })
                last = AttemptRecord(
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
                )
                self.attempts.append(last)
                last_valid = evaluation.valid
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
        summary = RunSummary(
            execution_mode=self.execution_mode,
            loop_completed=loop_completed,
            status=status,
            stop_reason=stop_reason,
            generated_valid_candidates=self.generated_valid,
            exported_skill_ids=list(dict.fromkeys(self.exported)),
            feedback_consumed_count=self.feedback_consumed,
            candidate_attempts=len(self.attempts),
            llm_requests=self.llm_requests,
            solver_calls=self.solver_calls,
            wall_seconds=self.monotonic() - self.started,
            incumbent_version_id=self.incumbent.version_id if self.incumbent else None,
            incumbent_is_generated=self.incumbent_is_generated,
        )
        payload = summary.as_dict()
        if provider_error_code:
            payload["provider_error_code"] = provider_error_code
        self.journal.append("run_finished", payload)
        (self.output_dir / "summary.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return summary


def prepare_output(path: Path, **suite_kwargs) -> dict:
    path = Path(path)
    path.mkdir(parents=True, exist_ok=False)
    suite = build_suite(**suite_kwargs)
    config = {
        "problem": PROBLEM_CVRP,
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
    }
    (path / "config_frozen.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    (path / "dev_suite.json").write_text(json.dumps(suite, indent=2) + "\n", encoding="utf-8")
    return config
