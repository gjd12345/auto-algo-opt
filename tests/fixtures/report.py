"""Deterministic run report from the journal. No model calls."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_run_report(output_dir: Path, summary: dict[str, Any]) -> Path:
    output_dir = Path(output_dir)
    events_path = output_dir / "run" / "events.jsonl"
    events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    attempts = [event["payload"] for event in events if event.get("kind") == "attempt_started"]
    results = {item["attempt_id"]: item for item in (event["payload"] for event in events if event.get("kind") == "attempt_result")}
    lines = [
        "# agent_skill_loop report",
        "",
        f"- problem: {summary.get('problem', 'cvrp_construct')}",
        f"- suite_hash: {summary.get('suite_hash')}",
        f"- model: {summary.get('model')}",
        f"- execution_mode: {summary.get('execution_mode')}",
        f"- candidate_attempts_limit: {summary.get('candidate_attempts_limit')}",
        f"- max_llm_requests: {summary.get('max_llm_requests')}",
        f"- wall_seconds_budget: {summary.get('wall_seconds_budget')}",
        f"- stop_reason: {summary.get('stop_reason')}",
        f"- status: {summary.get('status')}",
        f"- loop_completed: {summary.get('loop_completed')}",
        f"- generated_valid_candidates: {summary.get('generated_valid_candidates')}",
        f"- feedback_consumed_count: {summary.get('feedback_consumed_count')}",
        f"- feedback_then_regenerated: {summary.get('feedback_then_regenerated')}",
        f"- incumbent_version_id: {summary.get('incumbent_version_id')}",
        f"- incumbent_is_generated: {summary.get('incumbent_is_generated')}",
        f"- best_generated_version_id: {summary.get('best_generated_version_id')}",
        f"- llm_requests: {summary.get('llm_requests')}",
        f"- solver_calls: {summary.get('solver_calls')}",
        f"- wall_seconds: {summary.get('wall_seconds')}",
        "",
        "## attempts",
    ]
    for started in attempts:
        attempt_id = started["attempt_id"]
        result = results.get(attempt_id, {})
        evaluation = result.get("evaluation") or {}
        lines.extend(
            [
                "",
                f"### attempt {attempt_id}",
                f"- operator: {started.get('operator')}",
                f"- parent_version_id: {started.get('parent_version_id')}",
                f"- repair_of_attempt_id: {started.get('repair_of_attempt_id')}",
                f"- feedback_attempt_id: {started.get('feedback_attempt_id')}",
                f"- edit_target: {started.get('edit_target')}",
                f"- prompt_hash: {started.get('prompt_hash')}",
                f"- code_hash: {result.get('code_hash')}",
                f"- valid: {evaluation.get('valid')}",
                f"- mean_objective: {evaluation.get('objective')}",
                f"- instance_objectives: {evaluation.get('instance_objectives')}",
                f"- error_code: {evaluation.get('error_code')}",
                f"- error_detail: {evaluation.get('error_detail')}",
                f"- metrics: {evaluation.get('metrics')}",
                f"- accepted_as_incumbent: {result.get('accepted_as_incumbent')}",
                f"- accept_reason: {result.get('accept_reason')}",
                f"- model: {result.get('model')}",
                f"- input_tokens: {result.get('input_tokens')}",
                f"- output_tokens: {result.get('output_tokens')}",
                f"- request_elapsed_seconds: {result.get('request_elapsed_seconds')}",
            ]
        )
    lines.extend(
        [
            "",
            "## artifacts",
            f"- best generated skill: {summary.get('best_generated_path')}",
            f"- export reference: {summary.get('exported_skill')}",
            f"- run incumbent: {summary.get('incumbent_path')}",
        ]
    )
    path = output_dir / "report.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
