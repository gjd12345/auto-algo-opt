"""Run one tool-free gpt-5.5 decision and preserve its attributable cost."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent_skill_loop import session_actions as actions
from agent_skill_loop.client import ProviderFailure, http_post_with_deadline, load_local_env
from tools.memory_content_decision_prompt import BATCH, build as build_prompt
from tools.memory_content_study import _prereg


MODEL = "gpt-5.5"
MODEL_SNAPSHOT = "gpt-5.5-2026-04-23"
RESPONSES_URL = "https://api.openai.com/v1/responses"
MAX_INPUT_TOKENS = 30000
MAX_OUTPUT_TOKENS = 6000


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _post(url: str, api_key: str, payload: dict) -> dict:
    _, body = http_post_with_deadline(
        url, {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json.dumps(payload, ensure_ascii=False).encode("utf-8"), 900,
    )
    data = json.loads(body)
    if not isinstance(data, dict):
        raise ValueError("controller_response_invalid")
    return data


def _token_count(value) -> bool:
    return type(value) is int and value >= 0


def _dispatch(prompt: str, api_key: str, output: Path) -> tuple[dict, bool, str | None]:
    # Both requests carry the same complete model input and tool-free settings.
    # The output cap belongs on creation, which bounds reasoning tokens as well.
    request = {"model": MODEL_SNAPSHOT, "input": prompt, "tools": [], "tool_choice": "none", "truncation": "disabled"}
    try:
        counted = _post(f"{RESPONSES_URL}/input_tokens", api_key, request)
        count = counted.get("input_tokens")
        if counted.get("object") != "response.input_tokens" or not _token_count(count):
            raise ValueError("controller_input_token_count_invalid")
    except (ProviderFailure, OSError, ValueError) as exc:
        _write(output / "input_preflight.json", {"status": "unavailable", "error": getattr(exc, "error_code", None)})
        return {}, False, "controller_input_token_count_unavailable"
    allowed = count <= MAX_INPUT_TOKENS
    _write(output / "input_preflight.json", {"status": "allowed" if allowed else "rejected", "input_tokens": count})
    if not allowed:
        return {}, False, "controller_input_token_limit_exceeded"
    try:
        result = _post(RESPONSES_URL, api_key, {**request, "max_output_tokens": MAX_OUTPUT_TOKENS, "store": False})
    except (ProviderFailure, OSError, ValueError) as exc:
        error = getattr(exc, "error_code", "controller_response_invalid")
        return {}, True, error
    return result, True, None


def call(seed: int, arm: str, round_id: int, phase: str) -> dict:
    _prereg()
    prompt_receipt = build_prompt(seed, arm, round_id, phase)
    prompt = Path(prompt_receipt["prompt"])
    run = Path(prompt_receipt["run"])
    prompt_bytes = prompt.read_bytes()
    if hashlib.sha256(prompt_bytes).hexdigest() != prompt_receipt["prompt_sha256"]:
        raise ValueError("controller_prompt_identity_changed")
    prompt_text = prompt_bytes.decode("utf-8")
    stem = f"{arm}_{phase}_{round_id}"
    output = BATCH / "controller_outputs" / f"seed_{seed}" / stem
    if output.exists():
        raise ValueError("controller_turn_already_attempted")
    load_local_env()
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("controller_openai_api_key_missing")
    output.mkdir(parents=True)
    _write(output / "invocation.json", {
        "schema_version": "island605-controller-invocation/v2",
        "gateway": "openai_responses_api", "model_configured": MODEL, "model_requested": MODEL_SNAPSHOT,
        "phase": phase, "seed": seed, "arm": arm,
        "round_id": round_id, "prompt_ref": str(prompt),
        "prompt_sha256": prompt_receipt["prompt_sha256"],
        "brief": prompt_receipt["brief"], "delivery": prompt_receipt["delivery"],
        "store_response": False, "tools_allowed_by_study": False,
        "max_input_tokens": MAX_INPUT_TOKENS, "max_output_tokens": MAX_OUTPUT_TOKENS,
    })
    started = time.monotonic()
    result, generation_attempted, failure = _dispatch(prompt_text, api_key, output)
    elapsed = round(time.monotonic() - started, 6)
    if result:
        _write(output / "response.json", result)
    usage = result["usage"] if isinstance(result.get("usage"), dict) else {}
    input_tokens, output_tokens = usage.get("input_tokens"), usage.get("output_tokens")
    available = _token_count(input_tokens) and _token_count(output_tokens)
    config = json.loads((run / "config_frozen.json").read_text(encoding="utf-8"))
    treatment = config["experiment_manifest"]["document"]["extra"]["treatment"]
    usage_record = {
        "schema_version": "algorithm-optimization-controller-usage/v1",
        "event_id": f"{phase}-r{round_id}-attempt1",
        "round_id": round_id, "treatment": treatment, "activity": phase,
        "model": MODEL, "input_tokens": input_tokens if available else None,
        "output_tokens": output_tokens if available else None,
        "elapsed_seconds": elapsed, "availability": "complete" if available else "unavailable",
        "source": "openai_responses_api",
    }
    if not available:
        usage_record["unavailable_reason"] = failure or "The gateway did not report numeric token usage."
    usage_path = output / "controller_usage.json"
    _write(usage_path, usage_record)
    actions.record_controller_usage(run=run, file=usage_path)
    items = result["output"] if isinstance(result.get("output"), list) else []
    tools_used = [item for item in items if isinstance(item, dict) and item.get("type") not in {"message", "reasoning"}]
    if failure is None:
        if not available:
            failure = "controller_cost_unavailable"
        elif input_tokens > MAX_INPUT_TOKENS or output_tokens > MAX_OUTPUT_TOKENS:
            failure = "controller_cost_threshold_exceeded"
        elif tools_used:
            failure = "controller_tool_use_forbidden"
        elif result.get("model") != MODEL_SNAPSHOT:
            failure = "controller_model_identity_mismatch"
        elif result.get("status") != "completed":
            failure = "controller_response_incomplete"
        else:
            messages = [item.get("content") for item in items if isinstance(item, dict) and item.get("type") == "message"
                        and item.get("role") == "assistant" and item.get("status") == "completed"]
            try:
                if len(messages) != 1 or not isinstance(messages[0], list):
                    raise ValueError("controller_completion_count_invalid")
                text = "".join(part["text"] for part in messages[0] if part["type"] == "output_text")
                (output / "last_message.txt").write_text(text, encoding="utf-8")
                decision = json.loads(text)
                if not isinstance(decision, dict):
                    raise ValueError("decision_not_object")
            except (ValueError, TypeError, KeyError):
                failure = "controller_json_invalid"
    result_record = {
        "schema_version": "island605-controller-turn-result/v2",
        "status": "accepted" if failure is None else "failed",
        "failure": failure, "generation_attempted": generation_attempted,
        "provider_response_id": result.get("id"), "provider_status": result.get("status"), "served_model": result.get("model"),
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
