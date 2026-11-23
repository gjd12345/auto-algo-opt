"""Plan-time interface selection strategies for Milestone 2 (Phase 2B).

Implements all 4+1 fair-budget experimental arms:
- Arm 1: Fixed Pointwise (``cvrp_sequential_construct/v1``)
- Arm 2: Dev-Determined Fixed Strong Baseline (``cvrp_parallel_merge_static/v1`` or ``dynamic/v1``)
- Arm 3: Short-Pilot Racing (explicit pre-declared pilot quota, winner criterion, tie-break & seed resume)
- Arm 4a: Deterministic Diagnostic-Driven Policy (0 LLM tokens: reads 2x3 diagnostic + target-budget timing probe)
- Arm 4b: LLM Diagnostic Planner (1 planning LLM request counted in total budget; reads exact same diagnostic & KB clues)
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from agent_skill_loop.benchmark.catalog import load_profile_suite
from agent_skill_loop.client import http_post_with_deadline, load_local_env
from agent_skill_loop.cvrp_workbench.suites import BENCHMARK_ID
from agent_skill_loop.request_budget import BudgetExhausted, RequestBudget
from eoh_frozen.generation_contract import generation_parameters

from .blind_commitment import assert_suite_not_blind
from .contracts import (
    OUTCOME_BUDGET_EXHAUSTED_INCUMBENT,
    OUTCOME_COMPLETED,
    OUTCOME_TIMEOUT_OR_INFEASIBLE,
    InterfaceDesign,
)
from .runtime import compile_hook_function, evaluate_hook_on_instance_inprocess
from .templates import (
    build_classic_cw_static_design,
    build_parallel_merge_dynamic_design,
    build_ruin_recreate_design,
    build_sequential_construct_design,
    get_template_spec,
)

CANDIDATE_TEMPLATE_ORDER: tuple[tuple[str, str], ...] = (
    ("cvrp_sequential_construct", "v1"),
    ("cvrp_parallel_merge_static", "v1"),
    ("cvrp_parallel_merge_dynamic", "v1"),
)

M3_CANDIDATE_TEMPLATE_ORDER: tuple[tuple[str, str], ...] = (
    ("cvrp_sequential_construct", "v1"),
    ("cvrp_parallel_merge_static", "v1"),
    ("cvrp_parallel_merge_dynamic", "v1"),
    ("cvrp_ruin_recreate", "v1"),
)

# Balanced KB-derived domain clues (from M1.5 knowledge_workspace cards) passed symmetrically
# via DynamicInterfaceProblem.round_context so every paradigm avoids trivial scale pitfalls.
KB_ROUND_CONTEXT_BY_TEMPLATE: dict[str, str] = {
    "cvrp_sequential_construct": (
        "KB DOMAIN CLUES (from M1.5 cards method-cvrp-i605-tworegime-savings, method-cvrp-s2-r5-spiral):\n"
        "- Normalize distances by a GLOBAL instance scale such as `np.mean(distance_matrix[0, 1:])` so scores are coordinate-scale invariant.\n"
        "- Strong pointwise CVRP rules often combine depot-savings (`d0_next - d_cur_next`), capacity-fill regime switching, "
        "and optional voluntary early return (`return 0` when `current_node != 0`) when remaining capacity is small or the nearest feasible customer is far."
    ),
    "cvrp_parallel_merge_static": (
        "KB DOMAIN CLUES (from M1.5 card method-cvrp-cw-parallel & Yellow/Paessens generalized savings):\n"
        "- CRITICAL: To stay coordinate-scale invariant WITHOUT destroying far-from-depot radial priority, normalize distances by a GLOBAL instance scale "
        "like `scale = np.mean(distance_matrix[0, 1:])` — do NOT divide savings by per-pair `(d0i + d0j)`.\n"
        "- Classic Clarke-Wright `s_ij = d0i + d0j - dij` is a strong anchor; explore subtle generalized savings refinements "
        "`(d0i + d0j - lam * dij + mu * |d0i - d0j|) / scale` (e.g. lam in [0.9, 1.4], small mu in [-0.2, 0.25]) plus mild demand/capacity-fill adjustments."
    ),
    "cvrp_parallel_merge_dynamic": (
        "KB DOMAIN CLUES (from M1.5 card method-cvrp-cw-parallel & dynamic route-state merging):\n"
        "- CRITICAL: Normalize distances by a GLOBAL instance scale like `scale = np.mean(distance_matrix[0, 1:])` — do NOT divide savings by per-pair `(d0i + d0j)`, "
        "otherwise far-from-depot radial priority is lost.\n"
        "- Classic Clarke-Wright `(d0i + d0j - dij) / scale` is a strong anchor; augment it gently with generalized savings (`lam * dij`, `mu * |d0i - d0j|`) "
        "and live route-state signals (`(load_i + load_j) / capacity`, capacity slack near full truckload, route-length balance, or merge progress via `remaining_routes`).\n"
        "- Keep expressions fast and vectorized (O(M) numpy operations per call)."
    ),
    "cvrp_ruin_recreate": (
        "KB DOMAIN CLUES (from M2/M3 Ruin-and-Recreate LNS & scale-invariance principles):\n"
        "- CRITICAL: Normalize distances and `removal_savings` by a GLOBAL instance scale `scale = np.maximum(np.mean(distance_matrix[0, 1:]), 1e-12)` so ruin priorities remain coordinate-scale invariant.\n"
        "- Strong LNS ruin rules combine normalized detour `removal_savings / scale`, route slack `1 - route_loads / capacity`, and adaptive diversification via `stagnation_ratio` and `iter_frac`."
    ),
}


def _utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_design_for_template(
    template_id: str,
    template_version: str = "v1",
    *,
    design_id: str | None = None,
    postprocess_mode: str = "none",
    diagnostic_ref: dict[str, Any] | None = None,
    rationale: str = "",
) -> InterfaceDesign:
    if template_id == "cvrp_sequential_construct" and template_version == "v1":
        return build_sequential_construct_design(
            design_id=design_id or "m2_l1_sequential",
            postprocess_mode=postprocess_mode,
            diagnostic_ref=diagnostic_ref,
            rationale=rationale or "L1 sequential construct template.",
        )
    if template_id == "cvrp_parallel_merge_static" and template_version == "v1":
        return build_classic_cw_static_design(
            design_id=design_id or "m2_l2a_merge_static",
            postprocess_mode=postprocess_mode,
            diagnostic_ref=diagnostic_ref,
            rationale=rationale or "L2a static parallel merge template.",
        )
    if template_id == "cvrp_parallel_merge_dynamic" and template_version == "v1":
        return build_parallel_merge_dynamic_design(
            design_id=design_id or "m2_l2b_merge_dynamic",
            postprocess_mode=postprocess_mode,
            diagnostic_ref=diagnostic_ref,
            rationale=rationale or "L2b dynamic-refresh parallel merge template.",
        )
    if template_id == "cvrp_ruin_recreate" and template_version == "v1":
        return build_ruin_recreate_design(
            design_id=design_id or "m3_l3_ruin_recreate",
            postprocess_mode=postprocess_mode,
            diagnostic_ref=diagnostic_ref,
            rationale=rationale or "L3 Ruin-and-Recreate LNS template.",
        )
    raise KeyError(f"unsupported_template_builder:{template_id}/{template_version}")


def probe_template_budget_headroom(
    *,
    time_budget_ms: float = 500.0,
    probe_suite_specs: Sequence[tuple[str, str, int | None]] = (
        ("cvrp_dev_hetero_24", "dev_train", 12),
        ("cvrp_select_multiscale_64", "selection", 8),  # includes n=200 tail check below
    ),
    include_n200_probe: bool = True,
) -> dict[str, Any]:
    """Zero-LLM-Token baseline timing & outcome probe for L1, L2a, L2b-ctrl under ``time_budget_ms``."""
    t0 = time.perf_counter()
    probe_instances: list[dict[str, Any]] = []
    for suite_id, split, limit in probe_suite_specs:
        assert_suite_not_blind(suite_id)
        suite = load_profile_suite(BENCHMARK_ID, suite_id, split=split)
        assert_suite_not_blind(suite_id, suite)
        insts = suite["instances"]
        if include_n200_probe and suite_id == "cvrp_select_multiscale_64":
            n200 = [x for x in insts if int(x["size"]) == 200][: (limit or 8)]
            probe_instances.extend(n200)
        else:
            probe_instances.extend(insts[:limit] if limit is not None else insts)

    per_template: dict[str, Any] = {}
    for tid, tver in CANDIDATE_TEMPLATE_ORDER:
        tpl = get_template_spec(tid, tver)
        hook_fn = compile_hook_function(
            tpl.default_baseline_hook_code,
            hook_name=tpl.hook_name,
            expected_args=tpl.hook_signature,
        )
        # Warm-up 1 call to avoid cold numpy jitter
        evaluate_hook_on_instance_inprocess(
            template_id=tid,
            template_version=tver,
            hook_fn=hook_fn,
            instance=probe_instances[0],
            postprocess_mode="none",
            time_budget_ms=time_budget_ms,
        )

        solve_ms_list: list[float] = []
        cand_ms_list: list[float] = []
        hook_ms_list: list[float] = []
        lens: list[float] = []
        outcomes = {
            OUTCOME_COMPLETED: 0,
            OUTCOME_BUDGET_EXHAUSTED_INCUMBENT: 0,
            OUTCOME_TIMEOUT_OR_INFEASIBLE: 0,
        }
        n200_solve_ms: list[float] = []
        n200_completed = 0
        n200_total = 0

        for inst in probe_instances:
            res = evaluate_hook_on_instance_inprocess(
                template_id=tid,
                template_version=tver,
                hook_fn=hook_fn,
                instance=inst,
                postprocess_mode="none",
                time_budget_ms=time_budget_ms,
            )
            oc = str(res["outcome_class"])
            outcomes[oc] = outcomes.get(oc, 0) + 1
            solve_ms_list.append(float(res["solve_ms"]))
            cand_ms_list.append(float(res["candidate_gen_ms"]))
            hook_ms_list.append(float(res["hook_ms"]))
            if res["valid"] and res["tour_length"] is not None:
                lens.append(float(res["tour_length"]))
            if int(inst["size"]) >= 200:
                n200_total += 1
                n200_solve_ms.append(float(res["solve_ms"]))
                if oc == OUTCOME_COMPLETED:
                    n200_completed += 1

        n_tot = len(probe_instances)
        p50 = round(float(np.percentile(solve_ms_list, 50)), 4)
        p95 = round(float(np.percentile(solve_ms_list, 95)), 4)
        max_ms = round(float(max(solve_ms_list)), 4)
        per_template[f"{tid}/{tver}"] = {
            "template_id": tid,
            "template_version": tver,
            "n_instances": n_tot,
            "full_completion_rate": round(outcomes[OUTCOME_COMPLETED] / max(1, n_tot), 4),
            "feasible_rate": round(
                (outcomes[OUTCOME_COMPLETED] + outcomes[OUTCOME_BUDGET_EXHAUSTED_INCUMBENT]) / max(1, n_tot),
                4,
            ),
            "outcome_counts": outcomes,
            "baseline_mean_tour_length": round(float(np.mean(lens)), 4) if lens else None,
            "solve_ms_p50": p50,
            "solve_ms_p95": p95,
            "solve_ms_max": max_ms,
            "candidate_gen_ms_p95": round(float(np.percentile(cand_ms_list, 95)), 4),
            "hook_ms_p95": round(float(np.percentile(hook_ms_list, 95)), 4),
            "headroom_ratio_p95": round((time_budget_ms - p95) / max(time_budget_ms, 1e-9), 4),
            "n200_total": n200_total,
            "n200_full_completion_rate": round(n200_completed / max(1, n200_total), 4) if n200_total else None,
            "n200_solve_ms_p95": round(float(np.percentile(n200_solve_ms, 95)), 4) if n200_solve_ms else None,
        }

    return {
        "schema_version": "m2-template-budget-probe/v1",
        "generated_at": _utc_now(),
        "time_budget_ms": float(time_budget_ms),
        "probe_instance_count": len(probe_instances),
        "probe_wall_ms": round((time.perf_counter() - t0) * 1000.0, 2),
        "templates": per_template,
    }


def select_interface_by_diagnostic_rule(
    *,
    diagnostic_summary: Mapping[str, Any],
    budget_probe: Mapping[str, Any],
    target_budget_ms: float = 500.0,
    dynamic_headroom_threshold_ratio: float = 0.45,
    diagnostic_ref: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Arm 4a: Deterministic 0-LLM-Token diagnostic-driven interface selection policy.

    Decision logic (explicit, auditable, reproducible):
    1. Check 2x3 exploratory diagnostic on ``cvrp_dev_hetero_24``: if the best pointwise rule
       even after identical Relocate+2-opt still has higher mean tour length than bare
       ``cw_parallel_merge``, prune ``cvrp_sequential_construct/v1`` in favor of ``parallel_merge``.
    2. Between ``cvrp_parallel_merge_static/v1`` (L2a) and ``cvrp_parallel_merge_dynamic/v1`` (L2b),
       inspect the target-budget timing probe (``budget_probe``):
       - If L2b-ctrl does NOT achieve 100% full completion (``full_completion_rate < 1.0``) OR
         its ``solve_ms_p95 > (1 - dynamic_headroom_threshold_ratio) * target_budget_ms``
         (leaving insufficient room for richer evolved dynamic hooks under tight budgets like 25 ms),
         select ``cvrp_parallel_merge_static/v1`` (L2a).
       - Otherwise (plenty of budget headroom, e.g., 500 ms), select ``cvrp_parallel_merge_dynamic/v1`` (L2b)
         to unlock real-time route-load & travel-distance state feedback.
    """
    dev_sum = (diagnostic_summary.get("summary_by_suite") or {}).get("cvrp_dev_hetero_24") or {}
    bridging = dev_sum.get("bridging_vs_cw_raw") or {}
    # Check remaining gap of best pointwise solver (C1 or R5) after Relocate+2opt vs bare CW
    pw_remaining_gaps = [
        float(v["remaining_gap_vs_cw_raw_pct"])
        for k, v in bridging.items()
        if isinstance(v, Mapping) and "remaining_gap_vs_cw_raw_pct" in v
    ]
    min_pw_remaining = min(pw_remaining_gaps) if pw_remaining_gaps else 0.0

    tpl_probes = budget_probe.get("templates") or {}
    l2a_p = tpl_probes.get("cvrp_parallel_merge_static/v1") or {}
    l2b_p = tpl_probes.get("cvrp_parallel_merge_dynamic/v1") or {}

    trace: list[str] = []
    if min_pw_remaining > 0.0:
        trace.append(
            f"Step 1 (2x3 gap decomposition on dev_24): best pointwise + Relocate+2opt still trails bare CW "
            f"by +{min_pw_remaining:.2f}% -> switch paradigm from sequential_construct to parallel_merge."
        )
        l2b_full = float(l2b_p.get("full_completion_rate", 0.0))
        l2b_p95 = float(l2b_p.get("solve_ms_p95", target_budget_ms))
        max_allowed_ms = (1.0 - dynamic_headroom_threshold_ratio) * float(target_budget_ms)
        if l2b_full < 1.0 or l2b_p95 > max_allowed_ms:
            chosen_id, chosen_ver = "cvrp_parallel_merge_static", "v1"
            trace.append(
                f"Step 2 (target budget={target_budget_ms} ms headroom check): L2b-ctrl full_completion={l2b_full:.2%}, "
                f"p95={l2b_p95:.2f} ms > threshold {max_allowed_ms:.2f} ms (vs L2a p95={l2a_p.get('solve_ms_p95')} ms) "
                f"-> select cvrp_parallel_merge_static/v1 (L2a) to protect completion & budget headroom."
            )
            cited = ("method-cvrp-cw-parallel", "method-cvrp-i605-tworegime-savings")
        else:
            chosen_id, chosen_ver = "cvrp_parallel_merge_dynamic", "v1"
            trace.append(
                f"Step 2 (target budget={target_budget_ms} ms headroom check): L2b-ctrl full_completion={l2b_full:.2%}, "
                f"p95={l2b_p95:.2f} ms <= threshold {max_allowed_ms:.2f} ms -> select cvrp_parallel_merge_dynamic/v1 (L2b) "
                f"for real-time route-load and distance feedback."
            )
            cited = ("method-cvrp-cw-parallel", "method-cvrp-i605-tworegime-savings")
    else:
        chosen_id, chosen_ver = "cvrp_sequential_construct", "v1"
        trace.append(
            f"Step 1: pointwise + Relocate+2opt matched/beat bare CW (remaining={min_pw_remaining:+.2f}%) -> keep L1."
        )
        cited = ("method-cvrp-i605-tworegime-savings",)

    design = build_design_for_template(
        chosen_id,
        chosen_ver,
        design_id=f"m2_diag_rule_{chosen_id}_{int(target_budget_ms)}ms",
        postprocess_mode="none",
        diagnostic_ref=diagnostic_ref,
        rationale=" ".join(trace),
    )
    return {
        "planner_kind": "deterministic_diagnostic_rule",
        "target_budget_ms": float(target_budget_ms),
        "selected_template_id": chosen_id,
        "selected_template_version": chosen_ver,
        "cited_kb_ids": list(cited),
        "decision_trace": trace,
        "planning_requests": 0,
        "planning_input_tokens": 0,
        "planning_output_tokens": 0,
        "diagnostic_probe_wall_ms": float(budget_probe.get("probe_wall_ms", 0.0)),
        "design": design,
    }


def select_interface_by_llm_planner(
    *,
    diagnostic_summary: Mapping[str, Any],
    budget_probe: Mapping[str, Any],
    target_budget_ms: float = 500.0,
    endpoint: str = "https://opencode.ai/zen/go/v1/chat/completions",
    model: str = "deepseek-v4.1-flash",
    api_key_env: str = "OPENCODE_GO_API_KEY",
    diagnostic_ref: dict[str, Any] | None = None,
    timeout_s: float = 60.0,
    request_budget: RequestBudget | None = None,
) -> dict[str, Any]:
    """Arm 4b: LLM planning agent reading the exact same diagnostic & timing probe as Arm 4a (1 request)."""
    budget = request_budget if request_budget is not None else RequestBudget(5)
    initial_attempts = budget.used
    load_local_env()
    api_key = os.environ.get(api_key_env, "").strip()
    if not api_key:
        raise RuntimeError(f"missing_api_key:{api_key_env}")

    dev_sum = (diagnostic_summary.get("summary_by_suite") or {}).get("cvrp_dev_hetero_24") or {}
    compact_evidence = {
        "target_budget_ms": float(target_budget_ms),
        "dev_24_exploratory_2x3_bridging": dev_sum.get("bridging_vs_cw_raw"),
        "budget_headroom_probe": budget_probe.get("templates"),
        "available_templates": [
            {
                "template_id": "cvrp_sequential_construct",
                "template_version": "v1",
                "kb_clue": "method-cvrp-i605-tworegime-savings: fast O(n^2) pointwise construction; lags bare CW on dev_24 even with Relocate+2opt.",
            },
            {
                "template_id": "cvrp_parallel_merge_static",
                "template_version": "v1",
                "kb_clue": "method-cvrp-cw-parallel: one-shot vectorized static pair scoring; ultra-fast (~1-3 ms even on n=200), reproduces CW.",
            },
            {
                "template_id": "cvrp_parallel_merge_dynamic",
                "template_version": "v1",
                "kb_clue": "method-cvrp-cw-parallel + live route state: refreshes feasible endpoint pairs every merge and exposes load_i, load_j, route_dist_i, route_dist_j, remaining_routes; higher per-instance compute cost.",
            },
        ],
    }

    prompt = (
        "You are an autonomous algorithm-design planner for CVRP.\n"
        "Given the executable diagnostic evidence below, choose EXACTLY ONE registered template "
        "from `available_templates` to receive the evolution search budget under `target_budget_ms`.\n"
        "Consider BOTH solution quality gap AND whether the template leaves safe timing headroom "
        "under `target_budget_ms` (avoid templates whose baseline p95 solve time consumes >55% of target_budget_ms "
        "or fails 100% completion on n=200).\n"
        "Return ONLY a JSON object with keys: `template_id`, `template_version`, `cited_kb_ids` (list), `rationale` (string).\n\n"
        + json.dumps(compact_evidence, ensure_ascii=False, indent=2)
    )

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        **generation_parameters(endpoint, "provider-default", repair=False),
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "eoh-frozen-bridge/0908",
        "x-opencode-session": f"m2-plan-{int(time.time())}",
    }

    t0 = time.perf_counter()
    raw = b""
    last_exc: Exception | None = None
    backoff_schedule = (3.0, 6.0, 10.0, 15.0)
    max_attempts = len(backoff_schedule) + 1
    for attempt in range(max_attempts):
        slot = budget.reserve(purpose="interface_planning", problem="cvrp", attempt=attempt + 1, model=model)
        if slot is None:
            raise BudgetExhausted("planning_request_budget_exhausted")
        try:
            status, raw = http_post_with_deadline(endpoint, headers, json.dumps(payload).encode("utf-8"), timeout_s)
            last_exc = None
            break
        except Exception as exc:
            budget.finish(slot, "failed", error_code=getattr(exc, "error_code", type(exc).__name__))
            last_exc = exc
            if attempt < max_attempts - 1 and budget.remaining != 0:
                time.sleep(backoff_schedule[attempt])
                continue
            raise
    if last_exc is not None:
        raise last_exc
    plan_ms = (time.perf_counter() - t0) * 1000.0
    try:
        parsed = json.loads(raw.decode("utf-8"))
        content = str(parsed["choices"][0]["message"]["content"] or "").strip()
        usage = parsed.get("usage") or {}
        in_tok = int(usage.get("prompt_tokens") or 0)
        out_tok = int(usage.get("completion_tokens") or 0)
    except (ValueError, TypeError, KeyError, IndexError):
        budget.finish(slot, "failed", status=status, error_code="invalid_provider_response")
        raise
    budget.finish(slot, "complete", status=status, input_tokens=in_tok, output_tokens=out_tok)

    # Extract JSON cleanly even if wrapped in markdown fences
    m = re.search(r"\{.*\}", content, flags=re.DOTALL)
    if not m:
        raise ValueError(f"llm_planner_invalid_json:{content[:200]}")
    choice = json.loads(m.group(0))
    tid = str(choice["template_id"])
    tver = str(choice.get("template_version", "v1"))
    get_template_spec(tid, tver)  # verify exists in registry
    cited = [str(x) for x in (choice.get("cited_kb_ids") or ["method-cvrp-cw-parallel"])]
    rationale = str(choice.get("rationale") or "")

    design = build_design_for_template(
        tid,
        tver,
        design_id=f"m2_llm_plan_{tid}_{int(target_budget_ms)}ms",
        postprocess_mode="none",
        diagnostic_ref=diagnostic_ref,
        rationale=rationale,
    )
    return {
        "planner_kind": "llm_diagnostic_planner",
        "model": model,
        "target_budget_ms": float(target_budget_ms),
        "selected_template_id": tid,
        "selected_template_version": tver,
        "cited_kb_ids": cited,
        "rationale": rationale,
        "raw_response": content,
        "planning_requests": 1,
        "planning_request_attempts": budget.used - initial_attempts,
        "planning_input_tokens": in_tok,
        "planning_output_tokens": out_tok,
        "planning_wall_ms": round(plan_ms, 2),
        "diagnostic_probe_wall_ms": float(budget_probe.get("probe_wall_ms", 0.0)),
        "design": design,
    }


def run_short_pilot_racing(
    *,
    output_dir: Path,
    total_sample_budget: int,
    pilot_samples_per_arm: int,
    total_request_cap: int,
    candidate_templates: Sequence[tuple[str, str]] = CANDIDATE_TEMPLATE_ORDER,
    suite_id: str = "cvrp_dev_hetero_24",
    split: str = "dev_train",
    max_instances: int | None = None,
    instance_time_budget_ms: float = 500.0,
    search_seed: int = 20261122,
    mode: str = "live",
    endpoint: str = "https://opencode.ai/zen/go/v1/chat/completions",
    model: str = "deepseek-v4.1-flash",
    api_key_env: str = "OPENCODE_GO_API_KEY",
    diagnostic_ref: dict[str, Any] | None = None,
    solver_id_prefix: str = "m2_racing",
) -> dict[str, Any]:
    """Arm 3: Pre-declared Short-Pilot Racing protocol with total budget accounting & seed carry-over.

    Pre-declared rules:
    - Pilot phase: each of the K candidate templates receives ``pilot_samples_per_arm`` EoH samples.
    - Winner criterion: among templates producing >= 1 valid evolved candidate, rank by
      (1) lowest valid evolved best objective on ``suite_id`` under ``instance_time_budget_ms``;
      (2) tie-break within 1e-4 by lower baseline/best wall solve time;
      (3) deterministic order in ``candidate_templates``.
    - Continuation phase: winning template receives the exact remaining sample budget
      ``remaining_samples = max(1, total_sample_budget - K * pilot_samples_per_arm)`` and
      remaining request cap, seeded with its best valid pilot candidate(s) (``resume_from_pilot_seeds``).
    - Every pilot + continuation request and token is summed into one unified resource ledger.
    """
    from .dynamic_eoh import _summarize_request_log, run_dynamic_eoh_evolution

    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    if (output_dir / "frozen_solver_manifest.json").exists() or (output_dir / "racing_ledger.json").exists():
        raise FileExistsError(f"racing_output_already_exists:{output_dir}")
    with (output_dir / "racing.started").open("x", encoding="utf-8"):
        pass
    t_wall0 = time.perf_counter()

    k = len(candidate_templates)
    pilot_total_samples = k * pilot_samples_per_arm
    if pilot_total_samples >= total_sample_budget:
        raise ValueError(f"pilot_budget_exceeds_total:{pilot_total_samples}>={total_sample_budget}")

    if not k or pilot_samples_per_arm < 1 or total_request_cap < k + 1:
        raise ValueError("racing_budget_must_cover_pilots_and_continuation")
    budget = RequestBudget(total_request_cap)
    pilot_req_per_arm = total_request_cap // (k + 1)
    pilot_results: list[dict[str, Any]] = []
    used_requests = 0
    pilot_in_tok = 0
    pilot_out_tok = 0

    for idx, (tid, tver) in enumerate(candidate_templates):
        design = build_design_for_template(
            tid,
            tver,
            design_id=f"{solver_id_prefix}_pilot_{tid}",
            diagnostic_ref=diagnostic_ref,
        )
        p_dir = output_dir / f"pilot_{idx}_{tid}"
        try:
            res = run_dynamic_eoh_evolution(
                design=design,
                output_dir=p_dir,
                suite_id=suite_id,
                split=split,
                max_instances=max_instances,
                pop_size=2,
                n_pop=1,
                max_sample_nums=pilot_samples_per_arm,
                operators=("e1", "m1"),
                search_seed=search_seed + idx,
                instance_time_budget_ms=instance_time_budget_ms,
                solver_id=f"{solver_id_prefix}_pilot_{tid}",
                display_name=f"Racing Pilot · {tid}",
                mode=mode,
                endpoint=endpoint,
                model=model,
                api_key_env=api_key_env,
                max_requests=pilot_req_per_arm,
                request_budget=budget,
                require_evolved=True,
                round_context=KB_ROUND_CONTEXT_BY_TEMPLATE.get(tid),
            )
            reqs = res["resource_ledger"]["requests"]
            used_requests += int(reqs.get("completed_requests", 0))
            pilot_in_tok += int(reqs.get("prompt_tokens", 0))
            pilot_out_tok += int(reqs.get("completion_tokens", 0))
            pilot_results.append({
                "template_id": tid,
                "template_version": tver,
                "order_idx": idx,
                "ok": True,
                "best_objective": float(res["best_objective"]),
                "baseline_objective": float(res["baseline_objective"]),
                "evolved_count": int(res["evolved_count"]),
                "hook_code": res["frozen_solver"]["hook_code"],
                "requests": reqs,
                "output_dir": str(p_dir),
            })
        except Exception as exc:
            reqs = _summarize_request_log(p_dir / "results" / "requests.jsonl")
            used_requests += int(reqs["completed_requests"])
            pilot_in_tok += int(reqs["prompt_tokens"])
            pilot_out_tok += int(reqs["completion_tokens"])
            pilot_results.append({
                "template_id": tid,
                "template_version": tver,
                "order_idx": idx,
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
                "best_objective": None,
                "baseline_objective": None,
                "evolved_count": 0,
                "hook_code": None,
                "requests": reqs,
                "output_dir": str(p_dir),
            })

    valid_pilots = [p for p in pilot_results if p["ok"] and p["best_objective"] is not None]
    if not valid_pilots:
        raise RuntimeError(f"racing_all_pilots_failed:{pilot_results}")

    winner = min(valid_pilots, key=lambda p: (round(float(p["best_objective"]), 4), p["order_idx"]))
    win_tid = winner["template_id"]
    win_tver = winner["template_version"]

    remaining_samples = total_sample_budget - pilot_total_samples
    remaining_requests = budget.remaining

    win_design = build_design_for_template(
        win_tid,
        win_tver,
        design_id=f"{solver_id_prefix}_final_{win_tid}",
        diagnostic_ref=diagnostic_ref,
        rationale=(
            f"Short-Pilot Racing selected {win_tid}/{win_tver} (pilot best={winner['best_objective']:.4f}) "
            f"after {pilot_samples_per_arm} samples/arm across {k} templates; resumed with {remaining_samples} samples."
        ),
    )
    cont_dir = output_dir / f"continuation_{win_tid}"
    cont_res = run_dynamic_eoh_evolution(
        design=win_design,
        output_dir=cont_dir,
        suite_id=suite_id,
        split=split,
        max_instances=max_instances,
        pop_size=3,
        n_pop=max(1, remaining_samples // 3),
        max_sample_nums=remaining_samples,
        operators=("e1", "e2", "m1", "m2"),
        search_seed=search_seed + 100,
        instance_time_budget_ms=instance_time_budget_ms,
        solver_id=f"{solver_id_prefix}_winner",
        display_name=f"M2 Racing Winner ({win_tid})",
        mode=mode,
        endpoint=endpoint,
        model=model,
        api_key_env=api_key_env,
        max_requests=remaining_requests,
        request_budget=budget,
        require_evolved=False,  # pilot winner already evolved & carried over as seed
        extra_seed_entries=[{"algorithm": "Best valid candidate from Racing pilot phase.", "code": winner["hook_code"]}],
        round_context=KB_ROUND_CONTEXT_BY_TEMPLATE.get(win_tid),
    )

    # Best overall across pilot winner and continuation winner
    final_frozen = dict(cont_res["frozen_solver"])
    final_best_obj = float(cont_res["best_objective"])
    if float(winner["best_objective"]) < final_best_obj - 1e-9:
        # Pilot winner remained strictly better than continuation candidates
        pilot_manifest = json.loads((Path(winner["output_dir"]) / "frozen_solver_manifest.json").read_text(encoding="utf-8"))
        pilot_manifest["solver_id"] = f"{solver_id_prefix}_winner"
        pilot_manifest["display_name"] = f"M2 Racing Winner ({win_tid})"
        final_frozen = pilot_manifest
        final_best_obj = float(winner["best_objective"])

    cont_reqs = cont_res["resource_ledger"]["requests"]
    total_wall_ms = (time.perf_counter() - t_wall0) * 1000.0
    combined_ledger = {
        "schema_version": "m2-racing-ledger/v1",
        "protocol": {
            "candidate_templates": [f"{a}/{b}" for a, b in candidate_templates],
            "total_sample_budget": total_sample_budget,
            "pilot_samples_per_arm": pilot_samples_per_arm,
            "continuation_samples": remaining_samples,
            "resume_policy": "resume_from_pilot_seeds",
            "winner_criterion": "lowest_valid_evolved_objective_then_template_order",
            "total_request_cap": total_request_cap,
        },
        "pilot_results": [
            {k2: v2 for k2, v2 in p.items() if k2 != "hook_code"} for p in pilot_results
        ],
        "selected_template_id": win_tid,
        "selected_template_version": win_tver,
        "requests": {
            "attempted_requests": budget.used if mode == "live" else (
                sum(int(p["requests"].get("attempted_requests", 0)) for p in pilot_results)
                + int(cont_reqs.get("attempted_requests", 0))
            ),
            "pilot_requests": used_requests,
            "continuation_requests": int(cont_reqs.get("completed_requests", 0)),
            "completed_requests": used_requests + int(cont_reqs.get("completed_requests", 0)),
            "pilot_input_tokens": pilot_in_tok,
            "pilot_output_tokens": pilot_out_tok,
            "continuation_input_tokens": int(cont_reqs.get("prompt_tokens", 0)),
            "continuation_output_tokens": int(cont_reqs.get("completion_tokens", 0)),
            "prompt_tokens": pilot_in_tok + int(cont_reqs.get("prompt_tokens", 0)),
            "completion_tokens": pilot_out_tok + int(cont_reqs.get("completion_tokens", 0)),
            "total_tokens": (
                pilot_in_tok
                + pilot_out_tok
                + int(cont_reqs.get("prompt_tokens", 0))
                + int(cont_reqs.get("completion_tokens", 0))
            ),
        },
        "best_objective": final_best_obj,
        "total_wall_ms": round(total_wall_ms, 2),
    }
    (output_dir / "racing_ledger.json").write_text(
        json.dumps(combined_ledger, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (output_dir / "frozen_solver_manifest.json").write_text(
        json.dumps(final_frozen, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return {
        "ok": True,
        "selected_template_id": win_tid,
        "selected_template_version": win_tver,
        "best_objective": final_best_obj,
        "frozen_solver": final_frozen,
        "racing_ledger": combined_ledger,
        "output_dir": str(output_dir),
    }
