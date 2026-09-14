"""Deterministic v1.1 controlled-pilot manifest construction.

The pilot builder only expands one frozen experiment definition into the four
factor combinations from the benchmark protocol.  It never creates a Session
or contacts a provider; the caller still runs each manifest in an independent
Session and records the resulting evidence separately.
"""

from __future__ import annotations

from typing import Any, Mapping

from .contracts import ExperimentManifest


PILOT_GROUPS = ("A", "B", "C", "D")
PILOT_SCHEMA = "algorithm-optimization-controlled-pilot/v1"


def _manifest_values(payload: Mapping[str, Any]) -> dict[str, Any]:
    values = dict(payload)
    for key in ("schema_version", "manifest_version", "experiment_manifest_sha256"):
        values.pop(key, None)
    return values


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
