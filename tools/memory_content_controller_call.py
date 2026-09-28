"""Run one tool-free gpt-5.5 decision and preserve its attributable cost."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent_skill_loop import session_actions as actions
from tools.memory_content_decision_prompt import BATCH, build as build_prompt
from tools.memory_content_study import _prereg


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def call(seed: int, arm: str, round_id: int, phase: str) -> dict:
    _prereg()
    prompt_receipt = build_prompt(seed, arm, round_id, phase)
    prompt = Path(prompt_receipt["prompt"])
    run = Path(prompt_receipt["run"])
    stem = f"{arm}_{phase}_{round_id}"
    output = BATCH / "controller_outputs" / f"seed_{seed}" / stem
    if output.exists():
        raise ValueError("controller_turn_already_attempted")
    output.mkdir(parents=True)
    context = BATCH / "controller_contexts" / f"seed_{seed}" / arm / stem
    context.mkdir(parents=True, exist_ok=True)
    executable = shutil.which("codex.exe")
    if not executable:
        raise ValueError("codex_cli_executable_missing")
    command = [
        executable, "exec", "-m", "gpt-5.5", "--json", "--ephemeral",
        "-s", "read-only", "--skip-git-repo-check", "-C", str(context),
        "-o", str(output / "last_message.txt"), "-",
    ]
    _write(output / "invocation.json", {
        "schema_version": "island605-controller-invocation/v1",
        "model_configured": "gpt-5.5", "phase": phase, "seed": seed, "arm": arm,
        "round_id": round_id, "prompt_ref": str(prompt),
        "prompt_sha256": prompt_receipt["prompt_sha256"],
        "brief": prompt_receipt["brief"], "delivery": prompt_receipt["delivery"],
        "sandbox": "read-only", "ephemeral": True, "tools_allowed_by_study": False,
    })
    started = time.monotonic()
    try:
        result = subprocess.run(
            command, input=prompt.read_text(encoding="utf-8"), text=True,
            capture_output=True, encoding="utf-8", errors="replace", timeout=900,
            cwd=context,
        )
        returncode, stdout, stderr = result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired as exc:
        returncode = -1
        stdout = exc.stdout.decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode("utf-8", "replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
    elapsed = round(time.monotonic() - started, 6)
    (output / "events.jsonl").write_text(stdout, encoding="utf-8")
    (output / "stderr.txt").write_text(stderr, encoding="utf-8")
    events = []
    try:
        events = [json.loads(line) for line in stdout.splitlines() if line.strip()]
    except json.JSONDecodeError:
        pass
    completions = [item for item in events if item.get("type") == "turn.completed"]
    usage = completions[-1].get("usage", {}) if completions else {}
    input_tokens, output_tokens = usage.get("input_tokens"), usage.get("output_tokens")
    available = isinstance(input_tokens, int) and isinstance(output_tokens, int)
    config = json.loads((run / "config_frozen.json").read_text(encoding="utf-8"))
    treatment = config["experiment_manifest"]["document"]["extra"]["treatment"]
    usage_record = {
        "schema_version": "algorithm-optimization-controller-usage/v1",
        "event_id": f"{phase}-r{round_id}-attempt1",
        "round_id": round_id, "treatment": treatment, "activity": phase,
        "model": "gpt-5.5", "input_tokens": input_tokens if available else None,
        "output_tokens": output_tokens if available else None,
        "elapsed_seconds": elapsed, "availability": "complete" if available else "unavailable",
        "source": "codex_exec_jsonl",
    }
    if not available:
        usage_record["unavailable_reason"] = "CLI did not return a completed turn with numeric token usage."
    usage_path = output / "controller_usage.json"
    _write(usage_path, usage_record)
    actions.record_controller_usage(run=run, file=usage_path)
    tools_used = [
        item for item in events
        if item.get("type") == "item.started" and (item.get("item") or {}).get("type")
        in {"command_execution", "file_change", "web_search", "mcp_tool_call"}
    ]
    failure = None
    if returncode != 0:
        failure = f"controller_exit:{returncode}"
    elif tools_used:
        failure = "controller_tool_use_forbidden"
    elif not available:
        failure = "controller_cost_unavailable"
    elif input_tokens > 30000 or output_tokens > 6000:
        failure = "controller_cost_threshold_exceeded"
    elif len(completions) != 1:
        failure = "controller_completion_count_invalid"
    last = output / "last_message.txt"
    if failure is None:
        try:
            decision = json.loads(last.read_text(encoding="utf-8"))
            if not isinstance(decision, dict):
                raise ValueError("decision_not_object")
        except (OSError, ValueError, json.JSONDecodeError):
            failure = "controller_json_invalid"
    result_record = {
        "schema_version": "island605-controller-turn-result/v1",
        "status": "accepted" if failure is None else "failed",
        "failure": failure, "exit_code": returncode,
        "input_tokens": input_tokens if available else None,
        "output_tokens": output_tokens if available else None,
        "elapsed_seconds": elapsed, "tool_call_count": len(tools_used),
    }
    if failure is None:
        decision_path = output / "decision.json"
        _write(decision_path, decision)
        result_record["decision_path"] = str(decision_path)
    _write(output / "result.json", result_record)
    if failure:
        raise ValueError(failure)
    return result_record


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--arm", required=True, choices=("R", "F", "M"))
    parser.add_argument("--round-id", required=True, type=int)
    parser.add_argument("--phase", required=True, choices=("reflection", "plan"))
    args = parser.parse_args()
    print(json.dumps(call(args.seed, args.arm, args.round_id, args.phase), ensure_ascii=False))
