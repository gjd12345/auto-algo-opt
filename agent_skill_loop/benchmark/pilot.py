"""Deterministic v1.1 controlled-pilot manifest construction.

The pilot builder only expands one frozen experiment definition into the four
factor combinations from the benchmark protocol.  It never creates a Session
or contacts a provider; the caller still runs each manifest in an independent
Session and records the resulting evidence separately.
"""

from __future__ import annotations

from typing import Any, Mapping

from .contracts import ExperimentManifest
from agent_skill_loop.evidence.search_progress import POLICY_SCHEMA_VERSION


PILOT_GROUPS = ("A", "B", "C", "D")
PILOT_SCHEMA = "algorithm-optimization-controlled-pilot/v1"
CO_PILOT_GROUPS = ("G0", "G1", "G2", "G3", "G4")
CO_PILOT_SCHEMA = "algorithm-optimization-co-controlled-pilot/v1"
RESEARCH_LOOP_GROUPS = ("A", "B", "C")
RESEARCH_LOOP_SCHEMA = "algorithm-optimization-research-loop-pilot/v1"


def _manifest_values(payload: Mapping[str, Any]) -> dict[str, Any]:
    values = dict(payload)
    for key in ("schema_version", "manifest_version", "experiment_manifest_sha256"):
        values.pop(key, None)
    return values


def build_research_loop_manifests(base: Mapping[str, Any]) -> dict[str, Any]:
    """Freeze the OBP A/B/C reflection and online-Memory diagnostic."""
    if not isinstance(base, Mapping):
        raise ValueError("research_loop_base_manifest_invalid")
    try:
        source = ExperimentManifest(**_manifest_values(base))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"research_loop_base_manifest_invalid:{exc}") from exc
    if source.repair_mode != "off" or source.inheritance_mode != "population_seeds":
        raise ValueError("research_loop_requires_population_seeds_and_repair_off")
    extra_base = dict(source.extra)
    if extra_base.get("knowledge_mode", "off") != "off":
        raise ValueError("research_loop_requires_knowledge_off")
    extra_base.update({
        "research_loop_schema": RESEARCH_LOOP_SCHEMA,
        "problem_scope": "obp_online",
        "benchmark_profile": "obp_evolution_mini",
        "primary_budget_resource": "solver_calls",
        "comparison_packet_policy": "obp-research-contrasts/v1",
        "controller_usage_requirement": "complete_or_explicitly_unavailable",
        "heldout_policy": "locked_no_access_diagnostic",
        "diversity_interpretation": "diagnostic_only",
        "population_seed_policy": "verified_final_population_up_to_capacity_minimum_one",
        "knowledge_mode": "off",
        "search_progress_mode": "expose",
        "search_progress_policy": {
            "schema_version": POLICY_SCHEMA_VERSION,
            "enabled": True,
            "window_evaluations": 25,
            "min_absolute_gain": 0.0001,
            "min_relative_gain": 0.0001,
            "min_behavior_coverage": 0.5,
            "phase_budgets": {"exploration": 50, "exploitation": 50},
            "phase_schedule": ["exploration", "exploration", "exploitation", "exploitation"],
            "enforce_subbudgets": True,
        },
        "search_policy_defaults": {"pop_size": source.population_size, "n_pop": 2, "max_sample_nums": 100},
        "search_policy_limits": {
            "pop_size": [source.population_size, source.population_size],
            "n_pop": [2, 2], "max_sample_nums": [100, 100],
        },
    })
    if "resource_contract" in extra_base:
        resources = dict(extra_base["resource_contract"])
        resources.update(evaluation_budget=100, round_evaluation_budget=25)
        extra_base["resource_contract"] = resources

    def make(treatment: str, memory_enabled: bool, memory_source: str) -> ExperimentManifest:
        extra = {**extra_base, "treatment": treatment, "memory_source": memory_source,
                 "agent_input_contract": "same_comparison_packet_schema_and_selection_policy"}
        return ExperimentManifest(
            benchmark_spec_hash=source.benchmark_spec_hash,
            metric_spec_hash=source.metric_spec_hash,
            eoh_commit=source.eoh_commit,
            runtime_hash=source.runtime_hash,
            skill_hash=source.skill_hash,
            model=source.model,
            endpoint_identity=source.endpoint_identity,
            inheritance_mode="population_seeds",
            feedback_mode="runtime_facts",
            agent_guidance=True,
            repair_mode="off",
            memory_enabled=memory_enabled,
            evaluation_budget=100,
            population_size=source.population_size,
            rounds=4,
            round_budget=25,
            search_seed=source.search_seed,
            manifest_version=source.manifest_version,
            extra=extra,
        )

    manifests = {
        "A": make("facts_to_plan", False, "disabled"),
        "B": make("explicit_reflection", False, "disabled"),
        "C": make("reflection_with_online_memory", True, "run_internal_empty_start"),
    }
    groups = {
        group: {"description": {
            "A": "same evidence packet, facts directly to next Plan",
            "B": "A plus an explicit evidence-bound research note",
            "C": "B plus run-internal online Memory from an empty store",
        }[group], "manifest": {**manifest.as_dict(), "experiment_manifest_sha256": manifest.content_hash}}
        for group, manifest in manifests.items()
    }
    return {
        "schema_version": RESEARCH_LOOP_SCHEMA,
        "pilot_id": "obp_research_loop_v1",
        "shared_factors": {
            "problem_scope": "obp_online", "benchmark_profile": "obp_evolution_mini",
            "primary_budget_resource": "solver_calls", "evaluation_budget": 100,
            "rounds": 4, "round_budget": 25, "search_seed": source.search_seed,
            "comparison_packet_policy": "obp-research-contrasts/v1",
            "heldout_policy": "locked_no_access_diagnostic",
        },
        "groups": groups,
    }


def build_pilot_manifests(base: Mapping[str, Any]) -> dict[str, Any]:
    """Expand a validated base manifest into the fixed A/B/C/D pilot.

    All groups share benchmark/runtime/model/endpoint/seed, evaluator budget,
    population and repair/Memory settings.  A uses one Runtime Session and
    the full total budget; B/C/D use the requested multi-round allocation.
    C and D are deliberately identical except for ``agent_guidance``.
    """
    if not isinstance(base, Mapping):
        raise ValueError("pilot_base_manifest_invalid")
    values = _manifest_values(base)
    try:
        source = ExperimentManifest(**values)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"pilot_base_manifest_invalid:{exc}") from exc
    if source.evaluation_budget < 1:
        raise ValueError("pilot_requires_positive_evaluation_budget")
    if source.repair_mode != "off" or source.memory_enabled:
        raise ValueError("pilot_requires_repair_off_and_memory_disabled")
    if source.rounds < 2:
        raise ValueError("pilot_requires_at_least_two_rounds_for_b_c_d")

    common_extra = dict(source.extra)
    if common_extra.get("knowledge_mode", "off") != "off" or any(
        key.startswith("knowledge_") and key != "knowledge_mode" for key in common_extra
    ):
        raise ValueError("pilot_requires_knowledge_off")
    common_extra["knowledge_mode"] = "off"
    # ``max_sample_nums`` is the upstream engine's local evolution cap.  A
    # fixed value such as 8 can terminate a nominally 100/2000-call pilot
    # before its shared evaluator budget is reachable.  Derive one common
    # cap from the frozen budgets instead: A uses the total budget, while
    # B/C/D are stopped by their smaller per-round solver budget.  The
    # Session ledger remains the hard authority for actual calls.
    pilot_max_sample_nums = max(source.evaluation_budget, source.round_budget)
    common_extra.update({
        "pilot_schema": PILOT_SCHEMA,
        "pilot_id": "obp_v1.1_controlled",
        # Search parameters are not Agent factors.  Keep them in the hashed
        # manifest so each pilot Session can reject an accidental CLI override.
        "search_policy_defaults": {
            "pop_size": source.population_size,
            "n_pop": 2,
            "max_sample_nums": pilot_max_sample_nums,
        },
        "search_policy_limits": {
            "pop_size": [source.population_size, source.population_size],
            "n_pop": [2, 2],
            "max_sample_nums": [pilot_max_sample_nums, pilot_max_sample_nums],
        },
    })

    def make(*, inheritance_mode: str, feedback_mode: str, agent_guidance: bool,
             rounds: int, round_budget: int) -> ExperimentManifest:
        extra = dict(common_extra)
        if "resource_contract" in extra:
            resources = dict(extra["resource_contract"])
            resources["round_evaluation_budget"] = round_budget
            if rounds == 1:
                resources["round_request_budget"] = resources["request_budget"]
                resources["round_wall_clock_budget"] = resources["wall_clock_budget"]
            extra["resource_contract"] = resources
        return ExperimentManifest(
            benchmark_spec_hash=source.benchmark_spec_hash,
            metric_spec_hash=source.metric_spec_hash,
            eoh_commit=source.eoh_commit,
            runtime_hash=source.runtime_hash,
            skill_hash=source.skill_hash,
            model=source.model,
            endpoint_identity=source.endpoint_identity,
            inheritance_mode=inheritance_mode,
            feedback_mode=feedback_mode,
            agent_guidance=agent_guidance,
            repair_mode="off",
            memory_enabled=False,
            evaluation_budget=source.evaluation_budget,
            population_size=source.population_size,
            rounds=rounds,
            round_budget=round_budget,
            search_seed=source.search_seed,
            manifest_version=source.manifest_version,
            extra=extra,
        )

    # A is the continuous-EoH comparison implemented through the same
    # Runtime adapter, not a raw upstream EoH invocation.
    manifests = {
        "A": make(
            inheritance_mode="incumbent_only",
            feedback_mode="off",
            agent_guidance=False,
            rounds=1,
            round_budget=source.evaluation_budget,
        ),
        "B": make(
            inheritance_mode="incumbent_only",
            feedback_mode="runtime_facts",
            agent_guidance=False,
            rounds=source.rounds,
            round_budget=source.round_budget,
        ),
        "C": make(
            inheritance_mode="population_seeds",
            feedback_mode="runtime_facts",
            agent_guidance=False,
            rounds=source.rounds,
            round_budget=source.round_budget,
        ),
        "D": make(
            inheritance_mode="population_seeds",
            feedback_mode="runtime_facts",
            agent_guidance=True,
            rounds=source.rounds,
            round_budget=source.round_budget,
        ),
    }
    c_values = manifests["C"].as_dict()
    d_values = manifests["D"].as_dict()
    if {key: value for key, value in c_values.items() if key != "agent_guidance"} != {
        key: value for key, value in d_values.items() if key != "agent_guidance"
    }:
        raise ValueError("pilot_c_d_factors_not_controlled")

    groups: dict[str, dict[str, Any]] = {}
    descriptions = {
        "A": "one full Session through the neutral Runtime adapter",
        "B": "fixed multi-round Session with incumbent-only inheritance",
        "C": "fixed multi-round Session with population-seed inheritance",
        "D": "C with adaptive Agent guidance enabled",
    }
    for group in PILOT_GROUPS:
        manifest = manifests[group]
        groups[group] = {
            "description": descriptions[group],
            "interpretation": (
                "continuous_eoh_vs_sessionized_baseline" if group in {"A", "B"}
                else "agent_guidance_comparison" if group == "D"
                else "population_seed_baseline"
            ),
            "manifest": {**manifest.as_dict(), "experiment_manifest_sha256": manifest.content_hash},
        }
    return {
        "schema_version": PILOT_SCHEMA,
        "pilot_id": "obp_v1.1_controlled",
        "shared_factors": {
            "benchmark_spec_hash": source.benchmark_spec_hash,
            "metric_spec_hash": source.metric_spec_hash,
            "eoh_commit": source.eoh_commit,
            "runtime_hash": source.runtime_hash,
            "skill_hash": source.skill_hash,
            "model": source.model,
            "endpoint_identity": source.endpoint_identity,
            "evaluation_budget": source.evaluation_budget,
            "population_size": source.population_size,
            "search_seed": source.search_seed,
            "repair_mode": "off",
            "memory_enabled": False,
            "knowledge_mode": "off",
            "budget_comparison": "equal_total_evaluation_attempts",
        },
        "groups": groups,
    }


def build_co_pilot_manifests(base: Mapping[str, Any]) -> dict[str, Any]:
    """Freeze the Iteration-B G0--G4 factor matrix.

    The groups differ only in host guidance, SearchProgress exposure, Memory,
    and the explicitly enabled outer stagnation policy.  Official EoH search
    parameters and all evaluator/request budgets remain common.
    """
    if not isinstance(base, Mapping):
        raise ValueError("co_pilot_base_manifest_invalid")
    values = _manifest_values(base)
    try:
        source = ExperimentManifest(**values)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"co_pilot_base_manifest_invalid:{exc}") from exc
    if source.evaluation_budget < 1 or source.rounds < 2:
        raise ValueError("co_pilot_requires_multi_round_positive_budget")
    if source.repair_mode != "off":
        raise ValueError("co_pilot_requires_repair_off")
    if source.round_budget * source.rounds > source.evaluation_budget:
        raise ValueError("co_pilot_round_budgets_exceed_total")
    common_extra = dict(source.extra)
    if common_extra.get("knowledge_mode", "off") != "off" or any(
        key.startswith("knowledge_") and key != "knowledge_mode" for key in common_extra
    ):
        raise ValueError("co_pilot_requires_knowledge_off")
    common_extra["knowledge_mode"] = "off"
    common_extra["co_pilot_schema"] = CO_PILOT_SCHEMA
    common_extra["search_policy_defaults"] = {
        "pop_size": source.population_size,
        "n_pop": 2,
        "max_sample_nums": max(source.evaluation_budget, source.round_budget),
    }
    common_extra["search_policy_limits"] = {
        "pop_size": [source.population_size, source.population_size],
        "n_pop": [2, 2],
        "max_sample_nums": [common_extra["search_policy_defaults"]["max_sample_nums"], common_extra["search_policy_defaults"]["max_sample_nums"]],
    }
    if "resource_contract" in common_extra:
        resource = dict(common_extra["resource_contract"])
        resource["evaluation_budget"] = source.evaluation_budget
        resource["round_evaluation_budget"] = source.round_budget
        common_extra["resource_contract"] = resource

    half = source.evaluation_budget // 2
    policy_off = {
        "schema_version": POLICY_SCHEMA_VERSION,
        "enabled": False,
        "window_evaluations": source.round_budget,
        "min_absolute_gain": 0.0001,
        "min_relative_gain": 0.0001,
        "min_behavior_coverage": 0.5,
        "phase_budgets": {"exploration": half, "exploitation": source.evaluation_budget - half},
        "phase_schedule": [],
        "enforce_subbudgets": False,
    }
    policy_on = {
        **policy_off,
        "enabled": True,
        "phase_schedule": ["exploration" if index == 0 else "exploitation" for index in range(source.rounds)],
        "enforce_subbudgets": True,
    }

    def make(group: str, *, guidance: bool, progress_mode: str, memory: bool, feedback: str, policy: Mapping[str, Any]) -> ExperimentManifest:
        extra = dict(common_extra)
        extra.update({
            "search_progress_mode": progress_mode,
            "search_progress_policy": dict(policy),
            "memory_store_scope": "independent_group_store" if memory else "disabled",
            "co_group": group,
        })
        return ExperimentManifest(
            benchmark_spec_hash=source.benchmark_spec_hash,
            metric_spec_hash=source.metric_spec_hash,
            eoh_commit=source.eoh_commit,
            runtime_hash=source.runtime_hash,
            skill_hash=source.skill_hash,
            model=source.model,
            endpoint_identity=source.endpoint_identity,
            inheritance_mode=source.inheritance_mode,
            feedback_mode=feedback,
            agent_guidance=guidance,
            repair_mode="off",
            memory_enabled=memory,
            evaluation_budget=source.evaluation_budget,
            population_size=source.population_size,
            rounds=source.rounds,
            round_budget=source.round_budget,
            search_seed=source.search_seed,
            manifest_version=source.manifest_version,
            extra=extra,
        )

    manifests = {
        "G0": make("G0", guidance=False, progress_mode="record_only", memory=False, feedback="off", policy=policy_off),
        "G1": make("G1", guidance=True, progress_mode="record_only", memory=False, feedback="runtime_facts", policy=policy_off),
        "G2": make("G2", guidance=True, progress_mode="expose", memory=False, feedback="runtime_facts", policy=policy_off),
        "G3": make("G3", guidance=True, progress_mode="expose", memory=True, feedback="runtime_facts", policy=policy_off),
        "G4": make("G4", guidance=True, progress_mode="expose", memory=True, feedback="runtime_facts", policy=policy_on),
    }
    groups: dict[str, dict[str, Any]] = {}
    descriptions = {
        "G0": "neutral host control; SearchProgress is recorded only",
        "G1": "adaptive host Plan with existing factual feedback only",
        "G2": "G1 plus exposed SearchProgress facts",
        "G3": "G2 plus an independent empty Memory store",
        "G4": "G3 plus the frozen stagnation gate and phase subbudgets",
    }
    for group in CO_PILOT_GROUPS:
        manifest = manifests[group]
        groups[group] = {
            "description": descriptions[group],
            "factors": {
                "host_guidance": manifest.agent_guidance,
                "search_progress_mode": manifest.extra["search_progress_mode"],
                "memory": manifest.memory_enabled,
                "stagnation_policy": manifest.extra["search_progress_policy"]["enabled"],
            },
            "manifest": {**manifest.as_dict(), "experiment_manifest_sha256": manifest.content_hash},
        }
    common_keys = {key: value for key, value in groups["G0"]["manifest"].items() if key not in {"agent_guidance", "feedback_mode", "memory_enabled", "experiment_manifest_sha256", "extra"}}
    return {
        "schema_version": CO_PILOT_SCHEMA,
        "pilot_id": "obp_v1.1_co_iteration_b",
        "shared_factors": {
            **common_keys,
            "benchmark_spec_hash": source.benchmark_spec_hash,
            "metric_spec_hash": source.metric_spec_hash,
            "model": source.model,
            "endpoint_identity": source.endpoint_identity,
            "inheritance_mode": source.inheritance_mode,
            "evaluation_budget": source.evaluation_budget,
            "rounds": source.rounds,
            "round_budget": source.round_budget,
            "repair_mode": "off",
            "search_policy": common_extra["search_policy_defaults"],
            "budget_semantics": "total_evaluation_attempts_including_baseline_seed_repair",
        },
        "groups": groups,
    }
