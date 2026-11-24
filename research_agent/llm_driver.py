"""Dual-protocol (Native Tools + Strict JSON-Action) & Mock LLM driver for Research Agent."""

from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any, Mapping, Protocol, Sequence
from urllib.parse import urlsplit

from agent_skill_loop.client import ProviderFailure, http_post_with_deadline, load_local_env
from agent_skill_loop.interface_design.model_routing import (
    ModelRoutingPolicy,
    compute_attempt_cost_usd,
    extract_provider_usage,
)
from agent_skill_loop.request_budget import PersistentRequestBudget
from agent_skill_loop.session_actions import record_controller_usage
from research_agent.contracts import AgentConfig, atomic_write_json
from research_agent.prompts import AGENT_DIAGNOSE_TOOL_SCHEMAS, AGENT_REFLECT_TOOL_SCHEMAS, build_round_system_prompt


class AgentDriver(Protocol):
    """Unified decision interface shared by Live HTTP and Offline Mock drivers."""

    def decide_step(
        self,
        *,
        round_id: int,
        phase: str,
        step_index: int,
        messages: Sequence[Mapping[str, Any]],
        last_tool_result: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        ...


def _record_usage_to_session(
    *,
    config: AgentConfig,
    session_dir: Any,
    round_id: int,
    activity: str,
    input_tokens: int | None,
    output_tokens: int | None,
    elapsed_seconds: float,
    source: str,
) -> None:
    sess_db = session_dir / "session.sqlite3"
    if not sess_db.is_file():
        return
    usage_dir = session_dir.parent / "agent_artifacts" / "controller_usage"
    usage_dir.mkdir(parents=True, exist_ok=True)
    ev_id = f"ctrl_{config.run_id}_r{round_id}_{uuid.uuid4().hex[:8]}"
    avail = "complete" if (input_tokens is not None and output_tokens is not None) else "unavailable"
    payload: dict[str, Any] = {
        "schema_version": "algorithm-optimization-controller-usage/v1",
        "event_id": ev_id,
        "round_id": int(round_id),
        "treatment": config.arm_id,
        "activity": activity,
        "model": config.planner_model,
        "input_tokens": int(input_tokens) if avail == "complete" else None,
        "output_tokens": int(output_tokens) if avail == "complete" else None,
        "elapsed_seconds": round(float(elapsed_seconds), 4),
        "availability": avail,
        "source": source,
    }
    if avail == "unavailable":
        payload["unavailable_reason"] = "mock_or_unreported"
    ev_path = usage_dir / f"{ev_id}.json"
    atomic_write_json(ev_path, payload)
    try:
        record_controller_usage(run=session_dir, file=ev_path)
    except Exception:
        # Never abort research execution if treatment metadata is absent on custom sessions
        pass


def parse_strict_action_text(content: str) -> dict[str, Any]:
    """Parse Strict JSON-Action text returned by a non-tool-calling LLM."""
    text = str(content).strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3:
            text = "\n".join(lines[1:-1]).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError(f"strict_json_action_missing_braces:{text[:120]}")
    obj = json.loads(text[start : end + 1])
    if not isinstance(obj, dict) or "action" not in obj:
        raise ValueError("strict_json_action_missing_action_field")
    return obj


class OpenAIAgentDriver:
    """Real OpenAI-compatible HTTP driver with Native Tool-Calling and Strict JSON fallback."""

    def __init__(self, *, config: AgentConfig, budget: PersistentRequestBudget, session_dir: Any) -> None:
        self.config = config
        self.budget = budget
        self.session_dir = session_dir
        self._attempt = 0
        self._opencode_session_id = str(uuid.uuid4())
        self._is_opencode = (urlsplit(config.endpoint).hostname or "").endswith("opencode.ai")

    def decide_step(
        self,
        *,
        round_id: int,
        phase: str,
        step_index: int,
        messages: Sequence[Mapping[str, Any]],
        last_tool_result: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        load_local_env()
        api_key = os.environ.get(self.config.api_key_env, "").strip()
        if not api_key:
            raise RuntimeError(f"missing_api_key:{self.config.api_key_env}")

        purpose = "planner" if phase == "diagnose" else "reflection"
        policy = ModelRoutingPolicy.from_dict(self.config.model_routing_policy)
        chosen_model = (
            (policy.planner_model or self.config.planner_model)
            if policy.enabled
            else self.config.planner_model
        )
        rate_card = self.config.rate_card if self.config.rate_card is not None else policy.rate_card
        rate_card_version = self.config.rate_card_version or policy.rate_card_version
        sys_prompt = build_round_system_prompt(
            arm_id=self.config.arm_id,
            problem_family=self.config.problem_family,
            tools_enabled=self.config.tools_enabled,
            allowed_templates=self.config.allowed_templates,
            allowed_postprocess_modes=self.config.allowed_postprocess_modes,
            instance_time_budget_ms=self.config.instance_time_budget_ms,
            enable_stagnation_diagnostic_gate=self.config.enable_stagnation_diagnostic_gate,
            early_stop_no_jump_requests=self.config.early_stop_no_jump_requests,
            basin_restart_on_stagnation=self.config.basin_restart_on_stagnation,
        )
        full_msgs = [{"role": "system", "content": sys_prompt}, *[dict(m) for m in messages]]
        if last_tool_result is not None:
            last_m = full_msgs[-1] if full_msgs else {}
            serialized_last = json.dumps(last_tool_result, ensure_ascii=False, sort_keys=True, default=str)
            already_present = (
                last_m.get("role") == "tool"
                or (isinstance(last_m.get("content"), str) and (last_tool_result.get("eval_artifact_sha256") or serialized_last[:120]) in last_m.get("content", ""))
            )
            if not already_present:
                full_msgs.append({
                    "role": "user",
                    "content": "[LATEST OBSERVATION / EVALUATION RESULT]\n" + json.dumps(last_tool_result, ensure_ascii=False, default=str),
                })
        payload: dict[str, Any] = {
            "model": chosen_model,
            "messages": full_msgs,
            "temperature": 0.2,
        }
        if self.config.tools_enabled:
            payload["tools"] = list(AGENT_DIAGNOSE_TOOL_SCHEMAS if phase == "diagnose" else AGENT_REFLECT_TOOL_SCHEMAS)
            payload["tool_choice"] = "auto"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "eoh-frozen-bridge/0908" if self._is_opencode else "research-agent/1.0",
        }
        if self._is_opencode:
            headers["x-opencode-session"] = self._opencode_session_id

        last_exc: Exception | None = None
        backoff_schedule = (5.0, 15.0, 30.0)
        for retry in range(len(backoff_schedule) + 1):
            self._attempt += 1
            slot = self.budget.reserve(
                purpose=purpose,
                problem=self.config.problem_family,
                attempt=self._attempt,
                model=chosen_model,
                requested_model=chosen_model,
            )
            if slot is None:
                return {
                    "action": "budget_exhausted",
                    "denial_reason": getattr(self.budget, "denial_reason", None),
                }

            t0 = time.monotonic()
            try:
                self.budget.mark_sent(slot)
                status, raw = http_post_with_deadline(
                    self.config.endpoint,
                    headers,
                    json.dumps(payload).encode("utf-8"),
                    timeout=float(self.config.request_timeout_s),
                )
                elapsed = time.monotonic() - t0
                parsed = json.loads(raw.decode("utf-8"))
                usage_fields = extract_provider_usage(parsed)
                in_tok = usage_fields["input_tokens"]
                out_tok = usage_fields["output_tokens"]
                cached_tok = usage_fields["cached_tokens"]
                served_model = usage_fields["served_model"]
                prov_req_id = usage_fields["provider_request_id"]
                cost_usd, priced, _ = compute_attempt_cost_usd(
                    model_alias=chosen_model,
                    input_tokens=in_tok,
                    output_tokens=out_tok,
                    cached_tokens=cached_tok,
                    rate_card=rate_card,
                )
                choices = parsed.get("choices") or []
                choice0 = choices[0] if choices else {}
                msg = choice0.get("message") or {}
                finish_reason = choice0.get("finish_reason")
                raw_text = raw.decode("utf-8", errors="replace")

                self.budget.finish(
                    slot,
                    "complete",
                    status=status,
                    elapsed_seconds=elapsed,
                    input_tokens=in_tok,
                    output_tokens=out_tok,
                    cached_tokens=cached_tok,
                    requested_model=chosen_model,
                    served_model=served_model,
                    provider_request_id=prov_req_id,
                    rate_card_version=rate_card_version,
                    estimated_cost_usd=cost_usd if priced else None,
                    finish_reason=finish_reason,
                    response_text=raw_text,
                )
                _record_usage_to_session(
                    config=self.config,
                    session_dir=self.session_dir,
                    round_id=round_id,
                    activity="plan" if phase == "diagnose" else "reflection",
                    input_tokens=in_tok,
                    output_tokens=out_tok,
                    elapsed_seconds=elapsed,
                    source="openai_agent_driver",
                )

                tool_calls = msg.get("tool_calls") or []
                if tool_calls and isinstance(tool_calls, list):
                    tc = tool_calls[0]
                    fn = tc.get("function") or {}
                    tname = str(fn.get("name") or "")
                    try:
                        targs = json.loads(str(fn.get("arguments") or "{}"))
                    except Exception as exc:
                        decision: dict[str, Any] = {"action": "invalid_response", "error": f"malformed_tool_arguments:{exc}", "raw": str(fn.get("arguments") or "")[:300]}
                    else:
                        if not isinstance(targs, dict):
                            decision = {"action": "invalid_response", "error": "tool_arguments_must_be_object", "raw": str(fn.get("arguments") or "")[:300]}
                        elif tname == "submit_plan_and_evolve":
                            decision = {**targs, "action": "submit_plan", "tool_call_id": tc.get("id")}
                        elif tname == "finish_round":
                            decision = {"action": "finish_round", **targs, "tool_call_id": tc.get("id")}
                        else:
                            decision = {"action": "call_tool", "tool": tname, "arguments": targs, "tool_call_id": tc.get("id")}
                else:
                    content = str(msg.get("content") or "")
                    try:
                        decision = parse_strict_action_text(content)
                    except Exception as exc:
                        decision = {"action": "invalid_response", "error": str(exc), "raw": content[:400]}

                turn_log = self.session_dir.parent / "agent_artifacts" / "agent_turns.jsonl"
                turn_log.parent.mkdir(parents=True, exist_ok=True)
                with turn_log.open("a", encoding="utf-8", newline="\n") as fh:
                    fh.write(json.dumps({
                        "round_id": round_id,
                        "phase": phase,
                        "step_index": step_index,
                        "request_id": slot.request_id,
                        "model": self.config.planner_model,
                        "input_tokens": in_tok,
                        "output_tokens": out_tok,
                        "elapsed_seconds": round(elapsed, 4),
                        "messages": full_msgs,
                        "decision": decision,
                    }, ensure_ascii=False, default=str) + "\n")
                return decision
            except ProviderFailure as exc:
                last_exc = exc
                self.budget.finish(
                    slot,
                    "killed_unknown" if exc.error_code == "request_deadline" else "http_error",
                    status=exc.status,
                    error_code=exc.error_code,
                    requested_model=chosen_model,
                    elapsed_seconds=time.monotonic() - t0,
                )
                transient = (
                    exc.error_code in {"provider_connectivity_or_protocol_error", "request_deadline"}
                    or exc.status == 429
                    or (isinstance(exc.status, int) and 500 <= exc.status < 600)
                )
                if transient and retry < len(backoff_schedule):
                    time.sleep(backoff_schedule[retry])
                    continue
                raise
            except Exception as exc:
                last_exc = exc
                self.budget.finish(
                    slot,
                    "failed",
                    error_code=type(exc).__name__,
                    requested_model=chosen_model,
                    elapsed_seconds=time.monotonic() - t0,
                )
                raise
        assert last_exc is not None
        raise last_exc


class ScriptedMockAgentDriver:
    """Deterministic offline driver exhausting real PersistentRequestBudget slots cleanly."""

    def __init__(self, *, config: AgentConfig, budget: PersistentRequestBudget, session_dir: Any) -> None:
        self.config = config
        self.budget = budget
        self.session_dir = session_dir
        self._attempt = 0

    def decide_step(
        self,
        *,
        round_id: int,
        phase: str,
        step_index: int,
        messages: Sequence[Mapping[str, Any]],
        last_tool_result: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        purpose = "planner" if phase == "diagnose" else "reflection"
        policy = ModelRoutingPolicy.from_dict(self.config.model_routing_policy)
        chosen_model = (
            (policy.planner_model or self.config.planner_model)
            if policy.enabled
            else self.config.planner_model
        )
        rate_card = self.config.rate_card if self.config.rate_card is not None else policy.rate_card
        rate_card_version = self.config.rate_card_version or policy.rate_card_version
        self._attempt += 1
        slot = self.budget.reserve(
            purpose=purpose,
            problem=self.config.problem_family,
            attempt=self._attempt,
            model=chosen_model,
            requested_model=chosen_model,
        )
        if slot is None:
            return {
                "action": "budget_exhausted",
                "denial_reason": getattr(self.budget, "denial_reason", None),
            }
        self.budget.mark_sent(slot)

        action_obj = self._next_scripted_action(
            round_id=round_id,
            phase=phase,
            step_index=step_index,
            last_tool_result=last_tool_result,
        )
        cost_usd, priced, _ = compute_attempt_cost_usd(
            model_alias=chosen_model,
            input_tokens=64,
            output_tokens=32,
            cached_tokens=0,
            rate_card=rate_card,
        )
        self.budget.finish(
            slot,
            "complete",
            status=200,
            elapsed_seconds=0.01,
            input_tokens=64,
            output_tokens=32,
            cached_tokens=0,
            requested_model=chosen_model,
            served_model=chosen_model,
            provider_request_id=f"mock-{slot.request_id}",
            rate_card_version=rate_card_version,
            estimated_cost_usd=cost_usd if priced else None,
            finish_reason="stop",
            response_text=json.dumps(action_obj, ensure_ascii=False, sort_keys=True),
        )
        return action_obj

    def _next_scripted_action(
        self,
        *,
        round_id: int,
        phase: str,
        step_index: int,
        last_tool_result: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        if not self.config.tools_enabled:
            if phase == "diagnose":
                return {
                    "action": "submit_plan",
                    "template_id": self.config.initial_template_id,
                    "postprocess_mode": self.config.initial_postprocess_mode,
                    "direction": f"Plain-text reflection round {round_id} within locked template.",
                    "hypothesis": f"Refine hook expression under {self.config.initial_template_id}.",
                    "cited_kb_ids": [],
                    "rationale": "Tools disabled (Arm M3-1 plain-text reflection baseline).",
                }
            return {"action": "finish_round", "summary": f"Plain-text reflection completed round {round_id}."}

        if phase == "reflect":
            if round_id == 1 and step_index == 0:
                return {
                    "action": "call_tool",
                    "tool": "hypothesis_update",
                    "arguments": {
                        "hypothesis_id": "H_scale_bad_r1",
                        "status": "refuted",
                        "rationale": "Sandbox scale_invariance_audit confirmed non-zero scale drift from additive constant 1.0.",
                        "evidence_artifacts": [{"kind": "sandbox", "use_latest_sandbox": True}],
                    },
                }
            return {"action": "finish_round", "summary": f"Completed evidenced reflection for round {round_id}."}

        # Diagnose & plan phase with full tool chain (<= 4 calls per round)
        target_seq = list(self.config.allowed_templates)
        l3b_allowed = "cvrp_ruin_recreate_dual" in target_seq
        l3_allowed = "cvrp_ruin_recreate" in target_seq
        tsp_l2_allowed = "tsp_guided_insertion_2opt" in target_seq
        preferred_tpl = (
            "cvrp_ruin_recreate_dual"
            if l3b_allowed
            else (
                "cvrp_ruin_recreate"
                if l3_allowed
                else ("tsp_guided_insertion_2opt" if tsp_l2_allowed else self.config.initial_template_id)
            )
        )
        if round_id == 1:
            if step_index == 0:
                return {"action": "call_tool", "tool": "kb_search", "arguments": {"query": f"{self.config.problem_family} heuristic scale", "limit": 3}}
            if step_index == 1:
                if self.config.problem_family == "tsp":
                    bad_script = (
                        "inst = load_dev_suite(max_instances=1)[0]\n"
                        "bad_code = 'def select_next_node(distance_matrix, current_node, unvisited_mask, partial_length):\\n"
                        "    cand = [i for i, u in enumerate(unvisited_mask) if u]\\n"
                        "    return min(cand, key=lambda idx: distance_matrix[current_node, idx] / (1.0 + distance_matrix[current_node, idx]))\\n'\n"
                        "RESULT = scale_invariance_audit(bad_code, 'tsp_constructive_step', inst)\n"
                    )
                elif self.config.problem_family == "obp":
                    bad_script = (
                        "inst = load_dev_suite(max_instances=1)[0]\n"
                        "bad_code = 'def score_bin(item_size, bin_load, bin_capacity, open_bin_count):\\n"
                        "    return -(bin_capacity - bin_load - item_size) / (1.0 + bin_capacity)\\n'\n"
                        "RESULT = scale_invariance_audit(bad_code, 'obp_online_priority', inst)\n"
                    )
                elif self.config.problem_family == "bpp":
                    bad_script = (
                        "inst = load_dev_suite(max_instances=1)[0]\n"
                        "bad_code = 'def score_item(item_size, bin_capacity, item_count):\\n"
                        "    return item_size / (1.0 + bin_capacity)\\n'\n"
                        "RESULT = scale_invariance_audit(bad_code, 'bpp_offline_reorder_repack', inst)\n"
                    )
                else:
                    bad_script = (
                        "inst = load_dev_suite(max_instances=1)[0]\n"
                        "bad_code = 'import numpy as np\\ndef score_merge_static(distance_matrix, demands, capacity, i_idx, j_idx):\\n    return (distance_matrix[0, i_idx] + distance_matrix[0, j_idx] - distance_matrix[i_idx, j_idx]) / (1.0 + distance_matrix[0, i_idx])\\n'\n"
                        "RESULT = scale_invariance_audit(bad_code, 'cvrp_parallel_merge_static', inst)\n"
                    )
                return {"action": "call_tool", "tool": "run_math_sandbox", "arguments": {"script": bad_script}}
            if step_index == 2:
                return {
                    "action": "call_tool",
                    "tool": "hypothesis_propose",
                    "arguments": {
                        "hypothesis_id": "H_scale_bad_r1",
                        "statement": "Adding an unnormalized additive constant 1.0 in denominator preserves coordinate/capacity scale invariance.",
                        "rationale": "Test scaling drift via math sandbox before EoH.",
                    },
                }
            return {
                "action": "submit_plan",
                "template_id": self.config.initial_template_id,
                "postprocess_mode": self.config.initial_postprocess_mode,
                "direction": "Evolve scale-invariant scoring after auditing inhomogeneous normalization in sandbox.",
                "hypothesis": "Dimensionless normalized scoring preserves 0% scale drift across scales.",
                "cited_kb_ids": [],
                "rationale": "Round 1 KB search + sandbox audit prior to Session EoH.",
            }

        if round_id == 2:
            if step_index == 0:
                return {"action": "call_tool", "tool": "archive_summary", "arguments": {}}
            if step_index == 1:
                return {
                    "action": "call_tool",
                    "tool": "propose_and_validate_interface",
                    "arguments": {
                        "template_id": preferred_tpl,
                        "postprocess_mode": self.config.initial_postprocess_mode,
                        "time_budget_ms": self.config.instance_time_budget_ms,
                        "rationale": f"5-gate behavioral check before switching to {preferred_tpl}.",
                    },
                }
            return {
                "action": "submit_plan",
                "template_id": preferred_tpl,
                "postprocess_mode": self.config.initial_postprocess_mode,
                "direction": f"Adopt verified {preferred_tpl} interface for Round 2 evolution.",
                "hypothesis": f"{preferred_tpl} improves dev quality within {self.config.instance_time_budget_ms}ms.",
                "cited_kb_ids": [],
                "rationale": "Interface passed all 5 behavioral gates.",
            }

        if step_index == 0:
            return {
                "action": "call_tool",
                "tool": "diagnose_suite",
                "arguments": {"template_id": preferred_tpl, "time_budget_ms": self.config.instance_time_budget_ms, "max_instances": 4},
            }
        return {
            "action": "submit_plan",
            "template_id": preferred_tpl,
            "postprocess_mode": self.config.initial_postprocess_mode,
            "direction": f"Continue refining evolved {preferred_tpl} hook on weakest regimes.",
            "hypothesis": "Continued intra-template evolution improves dev objective.",
            "cited_kb_ids": [],
            "rationale": "Round 3+ refinement backed by multi-factor slicing.",
        }
