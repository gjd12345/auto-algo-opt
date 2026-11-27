"""Declarative research charter and role prompts for the Milestone 3 Research Agent."""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from research_agent.contracts import effective_stagnation_diagnostic_mode
from research_agent.tools.math_sandbox import SANDBOX_RESULT_EXAMPLE

RESEARCH_POLICY_MD = """# Autonomous CO Research Charter (Milestone 3)

## Non-Negotiable Audit Rules
1. **Hard Budget Conservation**: Every outer planning/reflection call and every inner EoH generation/repair call deducts from ONE shared persistent `PersistentRequestBudget`.
2. **Evidence-Bound Hypotheses**: Never mark a hypothesis `supported`, `refuted`, or `abandoned` without citing at least one disk-persisted artifact path and exact SHA-256 checksum.
3. **Blind & Selection Isolation**: Work exclusively on dev suites (`cvrp_dev_hetero_24`, `tsp_m31_dev_36`, `obp_m31_dev_36`, `bpp_m31_dev_36`) and synthetic fixtures during search. Selection suites and sealed blind suites (`cvrp_select_multiscale_64`, `tsp_m31_select_36`, `obp_m31_select_36`, `bpp_m31_select_36`, `cvrp_m2_blind_120`, `cvrp_m3_blind_120`, `cvrp_m32_blind_120`, `tsp_m31_blind_72`, `obp_m31_blind_72`, `bpp_m31_blind_72`) are strictly forbidden in interactive tools and sandboxes. Offline BPP must stay strictly separate from Online OBP (zero future lookahead in Online OBP).
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
            "description": "Run restricted Python/NumPy diagnostic code on dev_24 with a 15s hard timeout. Use pre-injected helpers and assign a dict of finite numbers to RESULT. A failed or nonnumeric result includes a repair_hint.",
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
            "description": "Update hypothesis status. Cite evidence_artifacts by path and SHA-256, or pass use_latest_sandbox=true in an evidence item to cite the latest verified sandbox result and script.",
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
                    "fresh_template": {"type": "boolean", "description": "Start with the template baseline when the round observation marks a fresh start available."},
                },
                "required": ["template_id", "direction", "hypothesis"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish_round",
            "description": "Conclude the reflection phase for the current round after any hypothesis ledger updates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "hypothesis_updates": {"type": "array", "items": {"type": "object"}},
                },
                "required": ["summary"],
            },
        },
    },
]

AGENT_DIAGNOSE_TOOL_SCHEMAS: list[dict[str, Any]] = [
    t for t in AGENT_TOOL_SCHEMAS if t["function"]["name"] not in {"hypothesis_update", "finish_round"}
]
AGENT_REFLECT_TOOL_SCHEMAS: list[dict[str, Any]] = [
    t for t in AGENT_TOOL_SCHEMAS if t["function"]["name"] in {"hypothesis_update", "archive_summary", "kb_read", "finish_round"}
]
AGENT_MEMORY_TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "memory_search",
            "description": "Search admissible memory cards for the current development plan.",
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
            "name": "memory_read",
            "description": "Read an admissible memory card using the reference returned by memory_search.",
            "parameters": {
                "type": "object",
                "properties": {"reference": {"type": "string"}},
                "required": ["reference"],
            },
        },
    },
]


_TEMPLATE_HINTS = {
    "cvrp_sequential_construct": "cvrp_sequential_construct(L1 pointwise `select_next_node`)",
    "cvrp_parallel_merge_static": "cvrp_parallel_merge_static(L2a static merge `score_merge_static`)",
    "cvrp_parallel_merge_dynamic": "cvrp_parallel_merge_dynamic(L2b dynamic route-state merge `score_merge_dynamic`)",
    "cvrp_ruin_recreate": "cvrp_ruin_recreate(L3 anytime LNS ruin-recreate `score_ruin_nodes`)",
    "cvrp_ruin_recreate_dual": "cvrp_ruin_recreate_dual(L3b dual-hook LNS ruin+recreate `score_ruin_nodes` + `score_recreate_action`)",
    "tsp_constructive_step": "tsp_constructive_step(L1 TSP constructive `select_next_node`)",
    "tsp_guided_insertion_2opt": "tsp_guided_insertion_2opt(L2 TSP insertion/2-opt move `score_insertion_move`)",
    "obp_online_priority": "obp_online_priority(Online OBP strict prefix-causal `score_bin`)",
    "bpp_offline_reorder_repack": "bpp_offline_reorder_repack(Offline BPP item priority `score_item`)",
}

_STAGNATION_GUIDANCE = {
    "off": "Stagnation diagnostics are optional.",
    "any": "If the round observation requires a diagnostic, call `diagnose_suite` or `run_math_sandbox` before submitting the plan.",
    "slice_only": "If the round observation requires a diagnostic, call `diagnose_suite` successfully before submitting the plan.",
    "sandbox_only": "If the round observation requires a diagnostic, call `run_math_sandbox` successfully and return finite numeric evidence in RESULT before submitting the plan.",
}
_SANDBOX_GUIDANCE = (
    "Sandbox helpers are pre-injected. No import is needed. Only numpy and math imports are allowed.\n"
    'Use `np`, `math`, `load_dev_suite(suite_id="cvrp_dev_hetero_24", max_instances=None)`, '
    '`eval_hook(code, template_id, inst, postprocess_mode="none", time_budget_ms=500.0)`, '
    '`eval_baseline(algorithm_id, inst, time_budget_ms=500.0)`, `slice_stats(records)`, '
    '`scale_invariance_audit(code, template_id, inst)`, and `radial_share_stats(routes, inst)`. '
    "Pass `inst` positionally and use keywords for optional evaluation settings.\n"
    "Never call `dir()`, `globals()`, `locals()`, `eval()`, `exec()`, or `open()`. Never import "
    "`os`, `sys`, or `pathlib`, or access `.__version__` or other dunder attributes. "
    "Assign a dict of finite `int` or `float` statistics directly to `RESULT` without wrapping it in `repr`. "
    "`load_dev_suite` instances contain ONLY keys: `instance_id`, `size`, `capacity`, `depot`, `customer_coordinates`, `demands`, `spatial`, `demand_dist`, `depot_style`, `reference_objective` (NO `distance_matrix` or `dimension` key — compute distances from `[depot] + customer_coordinates` if needed). "
    "`eval_hook`/`eval_baseline` return keys: `valid`, `tour_length`, `reference_objective`, `rel_gap`, `route_count`, `routes`, `route_loads`, `route_distances`, `solve_ms`, `status`, `error_code`.\n"
    "Inside evolved `hook` strings passed to `eval_hook`, only whitelisted NumPy helpers are allowed (`np.zeros`, `np.ones`, `np.full`, `np.arange`, `np.asarray`, `np.where`, `np.clip`, `np.argsort`, `np.sqrt`, `np.exp`, `np.power`); NEVER use `np.empty`, `np.linspace`, `np.ix_`, or `np.fill_diagonal` inside `hook` code.\n"
    "Use `repair_hint` to repair and rerun a failed script. Runnable CVRP example:\n"
    "# Compare dev baseline tour lengths to their references.\n"
    f"{SANDBOX_RESULT_EXAMPLE}\n"
)


def build_round_system_prompt(
    *,
    arm_id: str,
    problem_family: str,
    tools_enabled: bool,
    allowed_templates: Sequence[str],
    allowed_postprocess_modes: Sequence[str],
    instance_time_budget_ms: float,
    enable_stagnation_diagnostic_gate: bool = False,
    stagnation_diagnostic_mode: str = "any",
    early_stop_no_jump_requests: int | None = None,
    basin_restart_on_stagnation: bool = False,
    strict_diagnostic_gate: bool = False,
    memory_tools_enabled: bool = False,
) -> str:
    mode_desc = (
        "You have full access to deterministic diagnostic tools, KB search/read, AST-whitelisted NumPy math sandbox, "
        "5-gate interface validator, stepping-stone archive feedback, and the evidence-bound hypothesis ledger. "
        "Avoid redundant `list_interfaces` calls; inspect `dev_24` via `diagnose_suite` or `run_math_sandbox`, log a testable claim via `hypothesis_propose`, and validate switches via `propose_and_validate_interface` before calling `submit_plan_and_evolve`."
        if tools_enabled
        else "You are running in plain-text metacognitive reflection mode (NO external search, slicing, or Python sandbox tools). "
        "Reason strictly from the prior round summary, source code, and scalar scores."
    )
    tpl_desc = [_TEMPLATE_HINTS.get(t, t) for t in allowed_templates]
    protocol_desc = (
        "Prefer native OpenAI tool calls (`diagnose_suite`, `run_math_sandbox`, `kb_search`, `kb_read`, "
        "`propose_and_validate_interface`, `archive_summary`, `hypothesis_propose`, `submit_plan_and_evolve` in diagnose; "
        "`hypothesis_update`, `finish_round` in reflect). Or respond with one strict JSON object."
        if tools_enabled
        else "Respond with ONE strict JSON object only (`submit_plan` during diagnose phase, `finish_round` during reflect phase)."
    )
    diagnostic_mode = effective_stagnation_diagnostic_mode(
        stagnation_diagnostic_mode, enable_stagnation_diagnostic_gate
    )
    stagnation_line = _STAGNATION_GUIDANCE[diagnostic_mode] + "\n" if tools_enabled else ""
    if tools_enabled and strict_diagnostic_gate and diagnostic_mode != "off":
        stagnation_line += "A required diagnostic must succeed before the plan can proceed. Repair failed diagnostics and retry within the available outer steps.\n"
    memory_desc = ""
    if tools_enabled and (memory_tools_enabled or arm_id.startswith("arm_b3_")):
        memory_desc = (
            "During planning, call `kb_search` for a relevant entry, then `kb_read` with its entry ID. "
            "Include IDs of any KB entries used in `cited_kb_ids`.\n"
        )
        if memory_tools_enabled:
            memory_desc += (
                "Also call `memory_search` for the active template and `memory_read` with a matching returned reference before submitting your plan.\n"
            )
    trajectory_guidance = []
    if early_stop_no_jump_requests:
        trajectory_guidance.append(
            f"Inner evolution may stop after {early_stop_no_jump_requests} generated evaluations without a strict development objective improvement."
        )
    if basin_restart_on_stagnation:
        trajectory_guidance.append(
            'When `fresh_template_available` is true, include `"fresh_template": true` in the plan to start with the template baseline.'
        )
    trajectory_desc = " ".join(trajectory_guidance) + "\n" if trajectory_guidance else ""
    prompt_arm = "s1" if arm_id.startswith("arm_s1_") else arm_id
    return (
        f"You are an autonomous combinatorial optimization research scientist (`{prompt_arm}`) working on `{problem_family}` "
        f"under a strict per-instance time budget of {instance_time_budget_ms:.1f} ms.\n"
        f"{mode_desc}\n"
        f"Allowed templates: {tpl_desc}. Allowed postprocess modes: {list(allowed_postprocess_modes)}.\n"
        f"{protocol_desc}\n"
        f"{_SANDBOX_GUIDANCE if tools_enabled else ''}"
        f"{stagnation_line}"
        f"{memory_desc}"
        f"{trajectory_desc}"
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
    trajectory_control: Mapping[str, Any] | None = None,
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
    if trajectory_control is not None:
        payload["trajectory_control"] = dict(trajectory_control)
    return json.dumps(payload, ensure_ascii=False, indent=2)
