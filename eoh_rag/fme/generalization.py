"""Phase 6 多领域泛化契约；只定义准入与迁移边界，不扩大活跃问题集。"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Literal, Mapping, Sequence


ObjectiveDirection = Literal["minimize", "maximize"]
Readiness = Literal["contract_only", "evaluator_ready", "pilot_ready"]


def _sha256(payload: object) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class GeneralizationDomainSpec:
    """一个新问题进入 FME 前必须冻结的最小描述。"""

    problem_id: str
    domain_family: str
    objective_direction: ObjectiveDirection
    instance_schema: tuple[str, ...]
    solution_schema: tuple[str, ...]
    feasibility_oracle: str
    objective_metric: str
    deterministic_baseline: str
    budget_unit: str
    dev_split_rule: str
    heldout_split_rule: str
    admission_reason: str
    readiness: Readiness = "contract_only"

    @property
    def contract_hash(self) -> str:
        return _sha256(asdict(self))

    def missing_fields(self) -> tuple[str, ...]:
        payload = asdict(self)
        return tuple(
            name
            for name, value in payload.items()
            if value is None or value == "" or value == ()
        )


@dataclass(frozen=True)
class AbstractTransferEnvelope:
    """跨域只允许传递抽象机制和证据边界。"""

    source_problem: str
    target_problem: str
    mechanism_name: str
    invariant: str
    expected_effect: str
    failure_regime: str
    evidence_hashes: tuple[str, ...]
    contains_executable_code: bool = False
    contains_heldout_evidence: bool = False
    contains_source_solution: bool = False

    @property
    def allowed(self) -> bool:
        return bool(
            self.mechanism_name
            and self.invariant
            and self.expected_effect
            and self.failure_regime
            and self.evidence_hashes
            and self.source_problem != self.target_problem
            and not self.contains_executable_code
            and not self.contains_heldout_evidence
            and not self.contains_source_solution
        )


@dataclass(frozen=True)
class GeneralizationPilotProtocol:
    arms: tuple[str, ...]
    paired_seed_count: int
    candidate_evaluations_per_arm: int
    primary_metrics: tuple[str, ...]
    guardrails: tuple[str, ...]
    exit_conditions: tuple[str, ...]

    @property
    def evaluations_per_domain(self) -> int:
        return len(self.arms) * self.paired_seed_count * self.candidate_evaluations_per_arm


PHASE6_DOMAINS: tuple[GeneralizationDomainSpec, ...] = (
    GeneralizationDomainSpec(
        problem_id="maxcut_construct",
        domain_family="graph_partition",
        objective_direction="maximize",
        instance_schema=("weighted_undirected_graph", "node_count", "edge_weights"),
        solution_schema=("binary_partition",),
        feasibility_oracle="every node appears in exactly one partition",
        objective_metric="cut_weight",
        deterministic_baseline="seeded_greedy_gain_local_search",
        budget_unit="evaluated_candidate_algorithm",
        dev_split_rule="seeded graph generators and public instances; hashes frozen before generation",
        heldout_split_rule="unseen generator seeds and instance families; inaccessible to retrieval",
        admission_reason="引入图划分与最大化目标，检验当前路由/装箱机制是否只是表面迁移",
    ),
    GeneralizationDomainSpec(
        problem_id="knapsack_select",
        domain_family="subset_selection",
        objective_direction="maximize",
        instance_schema=("item_values", "item_weights", "capacity"),
        solution_schema=("selected_item_indices",),
        feasibility_oracle="total selected weight does not exceed capacity",
        objective_metric="selected_value",
        deterministic_baseline="density_ordered_greedy_with_single_item_guard",
        budget_unit="evaluated_candidate_algorithm",
        dev_split_rule="seeded value-weight regimes; regime labels visible only on dev",
        heldout_split_rule="unseen correlations and capacity ratios; hashes frozen before pilot",
        admission_reason="与 BP 共享容量概念但解表示和离线目标不同，适合检验抽象机制迁移边界",
    ),
    GeneralizationDomainSpec(
        problem_id="jssp_schedule",
        domain_family="precedence_scheduling",
        objective_direction="minimize",
        instance_schema=("jobs", "machine_routes", "processing_times"),
        solution_schema=("machine_operation_order", "start_times"),
        feasibility_oracle="machine non-overlap and job precedence both hold",
        objective_metric="makespan",
        deterministic_baseline="seeded_priority_dispatch_with_left_shift",
        budget_unit="evaluated_candidate_algorithm",
        dev_split_rule="seeded job-machine-size strata with frozen instance hashes",
        heldout_split_rule="unseen size strata and processing-time regimes; retrieval denied",
        admission_reason="引入先后约束与时间结构，覆盖当前三问题不具备的约束族",
    ),
)

PHASE6_SELECTED_PILOT = "jssp_schedule"


PHASE6_PILOT = GeneralizationPilotProtocol(
    arms=("no_transfer", "abstract_transfer", "shuffled_abstract_transfer"),
    paired_seed_count=3,
    candidate_evaluations_per_arm=30,
    primary_metrics=(
        "quality_potential_auc",
        "first_budget_reaching_5pct",
        "analysis_direction_accuracy",
        "analysis_brier_score",
        "valid_candidate_rate",
        "transfer_regret",
    ),
    guardrails=(
        "same frozen provider and controller configuration across arms",
        "no source executable code or source solution injection",
        "no heldout retrieval before the final frozen evaluation",
        "candidate evaluations, not generations, are the common budget unit",
    ),
    exit_conditions=(
        "valid candidate rate is below the no-transfer arm by more than 10 percentage points",
        "abstract transfer does not beat shuffled transfer on at least two paired seeds",
        "analysis confidence is uncalibrated and does not improve candidate ranking",
        "the domain requires a second top-level controller or incomparable budget semantics",
    ),
)


def build_readiness_snapshot(
    domains: Sequence[GeneralizationDomainSpec] = PHASE6_DOMAINS,
    pilot: GeneralizationPilotProtocol = PHASE6_PILOT,
    selected_pilot: str = PHASE6_SELECTED_PILOT,
) -> Mapping[str, object]:
    """生成静态准入快照；它不是求解器实验结果。"""

    domain_rows = []
    families: set[str] = set()
    for domain in domains:
        if domain.problem_id in {row["problem_id"] for row in domain_rows}:
            raise ValueError("duplicate_phase6_problem_id")
        families.add(domain.domain_family)
        domain_rows.append(
            {
                **asdict(domain),
                "contract_hash": domain.contract_hash,
                "missing_fields": list(domain.missing_fields()),
                "contract_completeness_gate_passed": not domain.missing_fields(),
            }
        )

    if selected_pilot not in {domain.problem_id for domain in domains}:
        raise ValueError("unknown_phase6_selected_pilot")

    payload: dict[str, object] = {
        "schema_version": "refactor0830-phase6-generalization-readiness/v1",
        "status": "contract_ready_single_domain_pilot_not_started",
        "claim_boundary": (
            "Static contract coverage only. No new-domain solver, candidate evaluation, "
            "LLM call, or generalization effect is claimed."
        ),
        "active_mainline_unchanged": ["bp_online", "tsp_construct", "cvrp_construct"],
        "candidate_domains": domain_rows,
        "domain_family_count": len(families),
        "pilot_protocol": {
            **asdict(pilot),
            "selected_target_problem": selected_pilot,
            "deferred_candidate_problems": [
                domain.problem_id for domain in domains if domain.problem_id != selected_pilot
            ],
            "evaluations_per_domain": pilot.evaluations_per_domain,
            "total_candidate_evaluations": pilot.evaluations_per_domain,
        },
    }
    payload["snapshot_hash"] = _sha256(payload)
    return payload


__all__ = [
    "AbstractTransferEnvelope",
    "GeneralizationDomainSpec",
    "GeneralizationPilotProtocol",
    "PHASE6_DOMAINS",
    "PHASE6_PILOT",
    "PHASE6_SELECTED_PILOT",
    "build_readiness_snapshot",
]
