"""Evaluate role: interpret trusted facts and propose memory action only."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from typing import Any, Callable, Mapping

from agent_skill_loop.contracts_3plus1 import EvaluateDocument, strict_json_object


@dataclass(frozen=True)
class EvaluatePrompt:
    problem: str
    suite_hash: str
    plan: Mapping[str, Any]
    facts: Mapping[str, Any]
    memory_enabled: bool
    problem_contract: Mapping[str, Any] | None = None

    def render(self) -> str:
        return json.dumps({
            "role": "evaluate",
            "instruction": "You are the post-execution Evaluate role, not the Plan role. Treat plan and trusted_facts as read-only inputs. Return exactly one compact JSON object whose top-level keys are plan_alignment, observations, causal_claim, and memory_action, in that order. Do not copy or repeat the plan object. Do not emit direction, operations, hypothesis, code, objective, validity, identity, incumbent, budget, or stop fields. Do not modify objective, validity, identity, incumbent, budget, or stop state.",
            "output_schema": {
                "plan_alignment": "aligned|deviated|unknown",
                "observations": ["short evidence-grounded strings"],
                "causal_claim": "string; use unknown/unproven when not established",
                "memory_action": {
                    "kind": "disabled|none|insight|solution",
                    "name": "required for insight/solution",
                    "description": "required for insight/solution",
                    "project": "required for insight/solution",
                    "scene": "required for insight/solution",
                    "body": "required; insight must contain **Why:** and **How to apply:**; solution must contain **Reusable Experience:**",
                    "based_on": "optional exact versioned memory/skill reference",
                    "evidence_ref": "optional exact generated-skill evidence reference for a solution",
                },
            },
            "top_level_keys_exactly": ["plan_alignment", "observations", "causal_claim", "memory_action"],
            "nesting_rule": "based_on and evidence_ref belong inside memory_action only; they are forbidden at the top level.",
            "evidence_rule": "Infer mechanisms only from code_evidence and exact revision references, never from objectives or the Plan alone. If relevant code is absent, truncated, or insufficient, plan_alignment must be unknown and causal_claim unproven. Repairs restore execution, not necessarily optimization. Memory body maximum 8000 characters; based_on updates the same memory name, or attributes a different new entry.",
            "problem": self.problem,
            "suite_hash": self.suite_hash,
            "problem_contract": self.problem_contract,
            "plan": self.plan,
            "trusted_facts": self.facts,
            "memory_enabled": self.memory_enabled,
            "required_shape_example": {
                "plan_alignment": "unknown",
                "observations": ["one evidence-grounded observation"],
                "causal_claim": "unproven",
                "memory_action": {"kind": "none"},
            },
            "valid_insight_shape_example": {
                "plan_alignment": "deviated",
                "observations": ["one trusted observation"],
                "causal_claim": "unproven",
                "memory_action": {
                    "kind": "insight",
                    "name": "short-name",
                    "description": "retrieval description",
                    "project": "cvrp_construct",
                    "scene": "select_next_node",
                    "body": "**Why:** evidence.\n\n**How to apply:** bounded guidance.",
                    "based_on": "optional-reference",
                    "evidence_ref": "optional-evidence",
                },
            },
        }, ensure_ascii=False, separators=(",", ":"))


class EvaluateRole:
    def __init__(self, request: Callable[..., str]) -> None:
        self._request = request

    def run(self, prompt: EvaluatePrompt) -> EvaluateDocument:
        response = self._request(prompt.render(), purpose="evaluate", problem=prompt.problem)
        result = EvaluateDocument.from_dict(strict_json_object(response), memory_enabled=prompt.memory_enabled)
        sources = prompt.facts.get("code_evidence") or []
        if not sources or any(item.get("truncated") or not item.get("code") for item in sources):
            result = replace(result, plan_alignment="unknown", causal_claim="unproven")
        return result
