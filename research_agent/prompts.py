"""Declarative research charter and role prompts for the Milestone 3 Research Agent."""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

RESEARCH_POLICY_MD = """# Autonomous CO Research Charter (Milestone 3)

## Non-Negotiable Audit Rules
1. **Hard Budget Conservation**: Every outer planning/reflection call and every inner EoH generation/repair call deducts from ONE shared persistent `PersistentRequestBudget`.
2. **Evidence-Bound Hypotheses**: Never mark a hypothesis `supported`, `refuted`, or `abandoned` without citing at least one disk-persisted artifact path and exact SHA-256 checksum.
3. **Blind & Selection Isolation**: Work exclusively on `cvrp_dev_hetero_24` and synthetic fixtures during search. `cvrp_select_multiscale_64` and sealed blind suites (`cvrp_m2_blind_120`, `cvrp_m3_blind_120`, `cvrp_m32_blind_120`) are strictly forbidden in interactive tools and sandboxes.
4. **Five-Gate Interface Integrity**: Switch `(template_id, postprocess_mode)` only via registered templates that pass all 5 behavioral gates under the target per-instance time budget.
5. **Non-Destructive Archive**: Retain complementary stepping-stone solvers across regimes and time-quality Pareto trade-offs; target the highest-regret `weakest_regimes` in the next round.
"""

AGENT_TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "kb_search",
            "description": "Search the verified combinatorial optimization knowledge base release.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 10},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "kb_read",
            "description": "Read full details and artifact bindings of a specific KB entry by ID.",
            "parameters": {
                "type": "object",
                "properties": {"entry_id": {"type": "string"}},
                "required": ["entry_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "diagnose_suite",
            "description": "Evaluate a template+hook on cvrp_dev_hetero_24 across 5 orthogonal factors and outcome classes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "template_id": {"type": "string"},
                    "hook_code": {"type": "string"},
                    "postprocess_mode": {"type": "string"},
                    "time_budget_ms": {"type": "number"},
                },
                "required": ["template_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_math_sandbox",
            "description": "Run restricted AST-whitelisted Python/NumPy diagnostic code on dev_24 with 15s hard kill.",
            "parameters": {
                "type": "object",
                "properties": {"script": {"type": "string"}},
                "required": ["script"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_interfaces",
            "description": "List allowed registered solver templates, signatures, and source hashes.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_and_validate_interface",
            "description": "Run 5-gate InterfaceValidator on a proposed (template_id, postprocess_mode) under target time budget.",
            "parameters": {
                "type": "object",
                "properties": {
                    "template_id": {"type": "string"},
                    "postprocess_mode": {"type": "string"},
                    "time_budget_ms": {"type": "number"},
                    "rationale": {"type": "string"},
                },
                "required": ["template_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "archive_summary",
            "description": "Inspect stepping-stone archive Pareto frontier, SBS/VBS complementarity, weakest regimes, and novelty.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "hypothesis_propose",
            "description": "Record a new testable hypothesis in hypotheses.jsonl.",
            "parameters": {
                "type": "object",
                "properties": {
                    "hypothesis_id": {"type": "string"},
                    "statement": {"type": "string"},
                    "rationale": {"type": "string"},
                },
                "required": ["statement"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "hypothesis_update",
            "description": "Update hypothesis status; supported/refuted/abandoned requires evidence_artifacts with SHA-256.",
            "parameters": {
                "type": "object",
                "properties": {
                    "hypothesis_id": {"type": "string"},
                    "status": {"type": "string", "enum": ["testing", "supported", "refuted", "abandoned", "superseded"]},
                    "rationale": {"type": "string"},
                    "evidence_artifacts": {"type": "array", "items": {"type": "object"}},
                },
                "required": ["hypothesis_id", "status"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit_plan_and_evolve",
            "description": "Submit verified plan to Session Runtime and run inner EoH evolution for the current round.",
            "parameters": {
                "type": "object",
                "properties": {
                    "template_id": {"type": "string"},
                    "postprocess_mode": {"type": "string"},
                    "direction": {"type": "string"},
                    "hypothesis": {"type": "string"},
                    "cited_kb_ids": {"type": "array", "items": {"type": "string"}},
                    "rationale": {"type": "string"},
                },
                "required": ["template_id", "direction", "hypothesis"],
            },
        },
    },
]


def build_round_system_prompt(
    *,
    arm_id: str,
    problem_family: str,
    tools_enabled: bool,
    allowed_templates: Sequence[str],
    allowed_postprocess_modes: Sequence[str],
    instance_time_budget_ms: float,
) -> str:
    mode_desc = (
        "You have full access to deterministic diagnostic tools, KB search/read, AST-whitelisted NumPy math sandbox, "
        "5-gate interface validator, stepping-stone archive feedback, and the evidence-bound hypothesis ledger."
        if tools_enabled
        else "You are running in plain-text metacognitive reflection mode (NO external search, slicing, or Python sandbox tools). "
        "Reason strictly from the prior round summary, source code, and scalar scores."
    )
    return (
        f"You are an autonomous combinatorial optimization research scientist (`{arm_id}`) working on `{problem_family}` "
        f"under a strict per-instance time budget of {instance_time_budget_ms:.1f} ms.\n"
        f"{mode_desc}\n"
        f"Allowed templates: {list(allowed_templates)}. Allowed postprocess modes: {list(allowed_postprocess_modes)}.\n"
        "You MUST either issue valid tool calls OR respond with a single strict JSON object matching one of:\n"
        '1) {"action":"call_tool","tool":"<name>","arguments":{...}}\n'
        '2) {"action":"submit_plan","template_id":"...","postprocess_mode":"...","direction":"...","hypothesis":"...","cited_kb_ids":[...],"rationale":"..."}\n'
        '3) {"action":"finish_round","summary":"...","hypothesis_updates":[...]}'
    )


def build_round_observation_message(
    *,
    round_id: int,
    budget_remaining: int | None,
    active_template_id: str,
    active_postprocess_mode: str,
    archive_state: Mapping[str, Any] | None,
    previous_round_summary: Mapping[str, Any] | None,
    open_hypotheses: Sequence[Mapping[str, Any]],
) -> str:
    payload = {
        "round_id": round_id,
        "budget_remaining_total": budget_remaining,
        "active_template_id": active_template_id,
        "active_postprocess_mode": active_postprocess_mode,
        "archive_feedback": archive_state,
        "previous_round_summary": previous_round_summary,
        "open_hypotheses": list(open_hypotheses),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
