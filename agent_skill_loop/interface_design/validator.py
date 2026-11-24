"""Five-gate behavioral InterfaceValidator for Milestone 2.

Gates:
1. AST Capability Whitelist (exact evaluator.py allowlist + line numbers & fix hints).
2. Template Version, Source Hash & Hook Signature Consistency.
3. Restricted Subprocess Execution & Baseline Feasibility (M1 verify_cvrp_solution).
4. Dual-Action Causal Sensitivity Probe (pre-postprocessing prefer_A vs prefer_B on a
   fixed 2-simultaneously-feasible-action instance, plus call count / negated / zero diagnostics).
5. Unified 500 ms Budget Boundary, 3-Class Outcome Accounting & 1e-3 Scale-Drift Diagnostics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import partial
import hashlib
import math
import random
from typing import Any, Callable, Mapping, Sequence

from agent_skill_loop.benchmark.catalog import load_profile_suite
from agent_skill_loop.cvrp_workbench.suites import BENCHMARK_ID

from .blind_commitment import assert_suite_not_blind
from .contracts import (
    OUTCOME_BUDGET_EXHAUSTED_INCUMBENT,
    OUTCOME_COMPLETED,
    OUTCOME_TIMEOUT_OR_INFEASIBLE,
    GateFailure,
    InterfaceDesign,
    LEGACY_CVRP_PROTOCOL_ID,
    ValidationReport,
    hook_bundle_metadata,
    sha256_text,
)
from .runtime import DynamicSubprocessEvaluator, validate_hook_ast, validate_hook_bundle
from .templates import _load_interface_extensions, get_template_spec


def build_gate4_dual_action_instance() -> dict[str, Any]:
    """Fixed 4-customer CVRP instance with two simultaneously feasible, mutually exclusive first merges.

    Geometry (depot at (0.5, 0.5), capacity = 10):
      - Customer 1 at (0.90, 0.50), demand = 6  (d01 = 0.40)
      - Customer 2 at (0.80, 0.70), demand = 4  (d02 = 0.3606, d12 = 0.2236, sav(1,2) = +0.5370 > 0)
      - Customer 3 at (0.80, 0.30), demand = 4  (d03 = 0.3606, d13 = 0.2236, sav(1,3) = +0.5370 > 0)
      - Customer 4 at (0.10, 0.50), demand = 3  (d04 = 0.40)

    Because d[1] + d[2] = 10 <= 10 and d[1] + d[3] = 10 <= 10, BOTH pair A = (1, 2) and
    pair B = (1, 3) have strictly positive savings and are simultaneously feasible. Once
    customer 1 merges with 2 (load=10), it CANNOT merge with 3 (10+4=14 > 10), and vice versa.
    Therefore:
      - prefer_A MUST execute first merge [1, 2] (putting {1, 2} together, separating {1, 3})
      - prefer_B MUST execute first merge [1, 3] (putting {1, 3} together, separating {1, 2})
    """
    return {
        "instance_id": "m2_gate4_dual_action_4cust",
        "cell": "gate4_dual_action",
        "size": 4,
        "spatial": "diagnostic",
        "depot_style": "centre",
        "capacity_level": "tight",
        "demand_dist": "diagnostic",
        "depot": [0.5, 0.5],
        "customer_coordinates": [
            [0.90, 0.50],  # 1
            [0.80, 0.70],  # 2
            [0.80, 0.30],  # 3
            [0.10, 0.50],  # 4
        ],
        "demands": [6, 4, 4, 3],
        "capacity": 10,
    }


_GATE4_PREFER_A_CODE = """import numpy as np

def score_merge_static(distance_matrix, demands, capacity, i_idx, j_idx):
    scores = np.zeros(i_idx.shape[0], dtype=np.float64)
    is_a = (i_idx == 1) & (j_idx == 2)
    is_b = (i_idx == 1) & (j_idx == 3)
    scores = np.where(is_a, 100.0, scores)
    scores = np.where(is_b, 1.0, scores)
    return scores
"""

_GATE4_PREFER_B_CODE = """import numpy as np

def score_merge_static(distance_matrix, demands, capacity, i_idx, j_idx):
    scores = np.zeros(i_idx.shape[0], dtype=np.float64)
    is_a = (i_idx == 1) & (j_idx == 2)
    is_b = (i_idx == 1) & (j_idx == 3)
    scores = np.where(is_b, 100.0, scores)
    scores = np.where(is_a, 1.0, scores)
    return scores
"""

_GATE4_CONSTANT_ZERO_CODE = """import numpy as np

def score_merge_static(distance_matrix, demands, capacity, i_idx, j_idx):
    return np.zeros(i_idx.shape[0], dtype=np.float64)
"""

_GATE4_NEGATED_CW_CODE = """import numpy as np

def score_merge_static(distance_matrix, demands, capacity, i_idx, j_idx):
    return -(distance_matrix[0, i_idx] + distance_matrix[0, j_idx] - distance_matrix[i_idx, j_idx])
"""

_GATE4_PROBES_BY_TEMPLATE: dict[str, dict[str, Any]] = {
    "cvrp_parallel_merge_static": {
        "prefer_A": _GATE4_PREFER_A_CODE,
        "prefer_B": _GATE4_PREFER_B_CODE,
        "expected_A": [1, 2],
        "expected_B": [1, 3],
        "constant_zero": _GATE4_CONSTANT_ZERO_CODE,
        "negated": _GATE4_NEGATED_CW_CODE,
    },
    "cvrp_parallel_merge_dynamic": {
        "prefer_A": """import numpy as np

def score_merge_dynamic(distance_matrix, demands, capacity, i_idx, j_idx, load_i, load_j, route_dist_i, route_dist_j, remaining_routes):
    scores = np.zeros(i_idx.shape[0], dtype=np.float64)
    is_a = (i_idx == 1) & (j_idx == 2)
    is_b = (i_idx == 1) & (j_idx == 3)
    scores = np.where(is_a, 100.0, scores)
    scores = np.where(is_b, 1.0, scores)
    return scores
""",
        "prefer_B": """import numpy as np

def score_merge_dynamic(distance_matrix, demands, capacity, i_idx, j_idx, load_i, load_j, route_dist_i, route_dist_j, remaining_routes):
    scores = np.zeros(i_idx.shape[0], dtype=np.float64)
    is_a = (i_idx == 1) & (j_idx == 2)
    is_b = (i_idx == 1) & (j_idx == 3)
    scores = np.where(is_b, 100.0, scores)
    scores = np.where(is_a, 1.0, scores)
    return scores
""",
        "expected_A": [1, 2],
        "expected_B": [1, 3],
        "constant_zero": """import numpy as np

def score_merge_dynamic(distance_matrix, demands, capacity, i_idx, j_idx, load_i, load_j, route_dist_i, route_dist_j, remaining_routes):
    return np.zeros(i_idx.shape[0], dtype=np.float64)
""",
        "negated": """import numpy as np

def score_merge_dynamic(distance_matrix, demands, capacity, i_idx, j_idx, load_i, load_j, route_dist_i, route_dist_j, remaining_routes):
    return -(distance_matrix[0, i_idx] + distance_matrix[0, j_idx] - distance_matrix[i_idx, j_idx])
""",
    },
    "cvrp_sequential_construct": {
        "prefer_A": """import numpy as np

def select_next_node(current_node, depot, unvisited_nodes, rest_capacity, demands, distance_matrix):
    if current_node == 0 and np.any(unvisited_nodes == 1):
        return 1
    return int(unvisited_nodes[0])
""",
        "prefer_B": """import numpy as np

def select_next_node(current_node, depot, unvisited_nodes, rest_capacity, demands, distance_matrix):
    if current_node == 0 and np.any(unvisited_nodes == 2):
        return 2
    return int(unvisited_nodes[-1])
""",
        "expected_A": [0, 1],
        "expected_B": [0, 2],
        "constant_zero": """import numpy as np

def select_next_node(current_node, depot, unvisited_nodes, rest_capacity, demands, distance_matrix):
    return int(unvisited_nodes[0])
""",
        "negated": """import numpy as np

def select_next_node(current_node, depot, unvisited_nodes, rest_capacity, demands, distance_matrix):
    return int(unvisited_nodes[np.argmax(distance_matrix[current_node, unvisited_nodes])])
""",
    },
    "cvrp_ruin_recreate": {
        "prefer_A": """import numpy as np

def score_ruin_nodes(distance_matrix, demands, capacity, route_ids, route_loads, route_dists, removal_savings, stagnation_ratio, iter_frac):
    return np.array([400.0, 300.0, 200.0, 100.0, 0.0, 0.0], dtype=np.float64)
""",
        "prefer_B": """import numpy as np

def score_ruin_nodes(distance_matrix, demands, capacity, route_ids, route_loads, route_dists, removal_savings, stagnation_ratio, iter_frac):
    return np.array([0.0, 0.0, 400.0, 300.0, 200.0, 100.0], dtype=np.float64)
""",
        "expected_A": [1, 2, 3, 4],
        "expected_B": [3, 4, 5, 6],
        "constant_zero": """import numpy as np

def score_ruin_nodes(distance_matrix, demands, capacity, route_ids, route_loads, route_dists, removal_savings, stagnation_ratio, iter_frac):
    return np.zeros(removal_savings.shape[0], dtype=np.float64)
""",
        "negated": """import numpy as np

def score_ruin_nodes(distance_matrix, demands, capacity, route_ids, route_loads, route_dists, removal_savings, stagnation_ratio, iter_frac):
    scale = np.maximum(np.mean(distance_matrix[0, 1:]), 1e-12)
    return -removal_savings / scale
""",
    },
}


def build_gate4_l3_6cust_instance() -> dict[str, Any]:
    """Fixed 6-customer CVRP probe instance for L3 (n=6 -> q=clip(0,4,24)=4).

    Two tie-free 4-of-6 ruin groups ({1,2,3,4} vs {3,4,5,6}) induce strictly
    different partial routes prior to deterministic Regret-2 recreate.
    """
    return {
        "instance_id": "m3_gate4_dual_action_6cust",
        "cell": "gate4_dual_action_l3",
        "size": 6,
        "spatial": "diagnostic",
        "depot_style": "centre",
        "capacity_level": "tight",
        "demand_dist": "diagnostic",
        "depot": [0.5, 0.5],
        "customer_coordinates": [
            [0.85, 0.50],  # 1
            [0.75, 0.78],  # 2
            [0.25, 0.80],  # 3
            [0.12, 0.50],  # 4
            [0.24, 0.20],  # 5
            [0.78, 0.22],  # 6
        ],
        "demands": [3, 4, 3, 4, 3, 4],
        "capacity": 10,
    }


def _default_gate3_instances() -> list[dict[str, Any]]:
    suite = load_profile_suite(BENCHMARK_ID, "cvrp_dev_hetero_24", split="dev_train")
    assert_suite_not_blind("cvrp_dev_hetero_24", suite)
    insts = suite["instances"]
    # 4 balanced instances covering n=50/100, uniform/clustered, centre/eccentric, loose/tight
    return [insts[0], insts[5], insts[12], insts[17]]


def _default_gate4_cvrp_instance(template_id: str) -> dict[str, Any]:
    if template_id == "cvrp_ruin_recreate":
        return build_gate4_l3_6cust_instance()
    return build_gate4_dual_action_instance()


def _build_gate5_n200_stress_instances() -> list[dict[str, Any]]:
    """Build deterministic standalone n=200 Gate-5 stress probes isolated from selection/blind splits."""
    specs = (
        ("m3_gate5_stress_n200_00", "uniform", "eccentric", "tight", "uniform", 28, [0.05, 0.95]),
        ("m3_gate5_stress_n200_01", "clustered", "centre", "loose", "bimodal", 45, [0.5, 0.5]),
    )
    probes: list[dict[str, Any]] = []
    for inst_id, spatial, depot_style, cap_lvl, ddist, cap, depot in specs:
        digest = hashlib.sha256(f"gate5_stress_probe/v1|{inst_id}".encode("utf-8")).hexdigest()
        rng = random.Random(int(digest[:16], 16))
        if spatial == "uniform":
            coords = [[round(rng.random(), 8), round(rng.random(), 8)] for _ in range(200)]
        else:
            centres = [(rng.random(), rng.random()) for _ in range(4)]
            coords = []
            for _ in range(200):
                cx, cy = centres[rng.randrange(4)]
                coords.append([
                    round(min(1.0, max(0.0, rng.gauss(cx, 0.06))), 8),
                    round(min(1.0, max(0.0, rng.gauss(cy, 0.06))), 8),
                ])
        if ddist == "uniform":
            demands = [rng.randint(1, 9) for _ in range(200)]
        else:
            choices = (1, 2, 8, 9)
            demands = [choices[rng.randrange(4)] for _ in range(200)]
        probes.append({
            "instance_id": inst_id,
            "cell": f"n200_{spatial}_{depot_style}_{cap_lvl}_{ddist}",
            "size": 200,
            "spatial": spatial,
            "depot_style": depot_style,
            "capacity_level": cap_lvl,
            "demand_dist": ddist,
            "source_tag": "gate5_independent_stress_probe",
            "depot": depot,
            "customer_coordinates": coords,
            "demands": demands,
            "capacity": cap,
        })
    return probes


def _default_gate5_instances() -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    dev_suite = load_profile_suite(BENCHMARK_ID, "cvrp_dev_hetero_24", split="dev_train")
    assert_suite_not_blind("cvrp_dev_hetero_24", dev_suite)
    n200_insts = _build_gate5_n200_stress_instances()
    nominal = dev_suite["instances"][0]
    scaled = dev_suite["scale_stress_instances"][0]
    return n200_insts, nominal, scaled


@dataclass(frozen=True)
class ProblemGateProbes:
    """Problem-family registry for Gate 3/4/5 validation probes (M3 -> M3.1 hook)."""

    problem_family: str
    gate3_instances: Callable[[], list[dict[str, Any]]]
    gate4_instance: Callable[[str], dict[str, Any]]
    gate5_instances: Callable[[], tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]]


@dataclass(frozen=True)
class GateProbeResult:
    diagnostics: dict[str, Any] = field(default_factory=dict)
    failures: tuple[GateFailure, ...] = ()


@dataclass(frozen=True)
class GateProbeContext:
    """Run trusted fixtures through the same worker and protocol as the candidate."""

    design: InterfaceDesign
    protocol_id: str
    solve_deadline_ms: float
    evaluate: Callable[..., dict[str, Any]]


@dataclass(frozen=True)
class ProblemGateProbeSpec:
    """Gate fixtures and checks for one protocol and optionally one template version.

    Gate 4 owns action and prefix assertions. Gate 5 receives the ordered stress
    records and may run further scale fixtures through the bound evaluator.
    """

    problem_family: str
    protocol_id: str
    gate3_instances: Callable[[InterfaceDesign], Sequence[Mapping[str, Any]]]
    gate4: Callable[[GateProbeContext], GateProbeResult]
    gate5_instances: Callable[[InterfaceDesign], Sequence[Mapping[str, Any]]]
    gate5: Callable[[GateProbeContext, Sequence[Mapping[str, Any]]], GateProbeResult] | None = None
    template_key: tuple[str, str] | None = None
    distance_convention: str = "euc_2d_float"
    vehicle_limit_policy: str = "unconstrained"


PROBLEM_GATE_PROBES: dict[str | tuple[str, str] | tuple[str, str, tuple[str, str]], ProblemGateProbes | ProblemGateProbeSpec] = {
    "cvrp": ProblemGateProbes(
        problem_family="cvrp",
        gate3_instances=_default_gate3_instances,
        gate4_instance=_default_gate4_cvrp_instance,
        gate5_instances=_default_gate5_instances,
    ),
}


def register_problem_gate_probe(spec: ProblemGateProbeSpec) -> None:
    if not spec.problem_family.strip() or not spec.protocol_id.strip():
        raise ValueError("empty_problem_gate_probe_identity")
    key = (spec.problem_family, spec.protocol_id)
    if spec.template_key is not None:
        key = (*key, spec.template_key)
    if key in PROBLEM_GATE_PROBES:
        raise ValueError(f"duplicate_problem_gate_probe:{key}")
    PROBLEM_GATE_PROBES[key] = spec


def _resolve_gate_probe(design: InterfaceDesign, protocol_id: str) -> ProblemGateProbeSpec | None:
    key = (design.problem_family, protocol_id)
    template_key = (*key, (design.template_id, design.template_version))
    if design.protocol_id is not None or design.hook_specs:
        _load_interface_extensions(probes=True)
    probe = PROBLEM_GATE_PROBES.get(template_key, PROBLEM_GATE_PROBES.get(key))
    return probe if isinstance(probe, ProblemGateProbeSpec) else None


class InterfaceValidator:
    """Five-gate behavioral validator for Milestone 2 InterfaceDesign objects."""

    def __init__(
        self,
        *,
        candidate_timeout_s: float = 20.0,
        instance_time_budget_ms: float = 500.0,
        evaluator: DynamicSubprocessEvaluator | None = None,
        solve_deadline_ms: float | None = None,
        outer_timeout_s: float | None = None,
        allow_extended_numpy_whitelist: bool | None = None,
        enable_degenerate_constant_screen: bool = False,
    ) -> None:
        self.candidate_timeout_s = float(candidate_timeout_s)
        self.instance_time_budget_ms = float(instance_time_budget_ms if solve_deadline_ms is None else solve_deadline_ms)
        self.outer_timeout_s = outer_timeout_s
        self.evaluator = evaluator or DynamicSubprocessEvaluator(candidate_timeout_s=self.candidate_timeout_s)
        self.allow_extended_numpy_whitelist = allow_extended_numpy_whitelist
        self.enable_degenerate_constant_screen = enable_degenerate_constant_screen

    def _allow_extended_numpy(self, design: InterfaceDesign) -> bool:
        if self.allow_extended_numpy_whitelist is not None:
            return self.allow_extended_numpy_whitelist
        return design.template_options.get("allow_extended_numpy_whitelist", True)

    def validate(
        self,
        design: InterfaceDesign,
        *,
        gate3_instances: Sequence[Mapping[str, Any]] | None = None,
        gate5_n200_instances: Sequence[Mapping[str, Any]] | None = None,
        gate5_scale_pair: tuple[Mapping[str, Any], Mapping[str, Any]] | None = None,
        hook_code_override: str | None = None,
        hook_implementations: Mapping[str, str] | None = None,
    ) -> ValidationReport:
        """Run all 5 validation gates sequentially and return a structured ``ValidationReport``."""
        hook_code = hook_code_override if hook_code_override is not None else design.baseline_hook_code
        allow_extended_numpy = self._allow_extended_numpy(design)
        hook_sha = sha256_text(hook_code)
        gates_summary: list[dict[str, Any]] = []
        failures: list[GateFailure] = []
        diagnostics: dict[str, Any] = {
            "candidate_timeout_s": self.candidate_timeout_s,
            "instance_time_budget_ms": self.instance_time_budget_ms,
        }
        if self.outer_timeout_s is not None:
            diagnostics["outer_timeout_s"] = self.outer_timeout_s

        # Resolve template first (needed for Gate 2 signature & Gate 1 entrypoint check)
        tpl = None
        template_sha: str | None = None
        try:
            tpl = get_template_spec(design.template_id, design.template_version)
            template_sha = tpl.template_source_sha256
        except KeyError as exc:
            failures.append(GateFailure(
                gate_id=2,
                gate_name="template_and_signature",
                error_code="unknown_template",
                line_no=None,
                symbol=f"{design.template_id}/{design.template_version}",
                detail=str(exc),
                fix_hint="Select a registered (template_id, template_version) from TEMPLATE_REGISTRY.",
            ))

        expected_hook_name = tpl.hook_name if tpl is not None else design.hook_name
        expected_args = tpl.hook_signature if tpl is not None else design.hook_signature

        # --- Gate 1: AST Capability Whitelist ---
        specs = tpl.effective_hook_specs if tpl is not None else design.hook_specs
        implementations = hook_implementations
        candidate_error: GateFailure | None = None
        if implementations is None and hook_code_override is not None and len(specs) > 1 and tpl is not None:
            from .planner import parse_hook_candidate

            try:
                implementations = parse_hook_candidate(
                    tpl.template_id, tpl.template_version, hook_code_override,
                    allow_extended_numpy_whitelist=allow_extended_numpy,
                )
            except (ValueError, SyntaxError) as exc:
                candidate_error = GateFailure(
                    2, "template_and_signature", "invalid_hook_bundle_program", None, None,
                    str(exc), "Provide one program with every declared hook or a named source map.",
                )
        if implementations is None and design.hook_specs:
            implementations = dict(design.hook_implementations)
            if hook_code_override is not None and len(specs) == 1:
                implementations[design.hook_name] = hook_code_override
        if implementations is not None:
            g1_failures, g2_sig_failures = validate_hook_bundle(
                specs, implementations, allow_extended_numpy_whitelist=allow_extended_numpy,
            )
            if not g2_sig_failures:
                hook_sha = sha256_text(implementations[expected_hook_name])
                diagnostics["hook_bundle"] = hook_bundle_metadata(specs, implementations)
                if (hook_code_override is not None and hook_implementations is not None
                        and implementations[expected_hook_name] != hook_code_override):
                    g2_sig_failures.append(GateFailure(
                        2, "template_and_signature", "primary_hook_mismatch", None, expected_hook_name,
                        "The primary override differs from its named source.", "Supply matching sources.",
                    ))
        else:
            g1_failures, g2_sig_failures = validate_hook_ast(
                hook_code, hook_name=expected_hook_name, expected_args=expected_args,
                allow_extended_numpy_whitelist=allow_extended_numpy,
            )
        if candidate_error is not None:
            g2_sig_failures.append(candidate_error)
        gates_summary.append({
            "gate_id": 1,
            "gate_name": "ast_whitelist",
            "passed": len(g1_failures) == 0,
            "failure_count": len(g1_failures),
        })
        failures.extend(g1_failures)

        # --- Gate 2: Template Version, Contract & Signature Consistency ---
        g2_failures: list[GateFailure] = list(g2_sig_failures)
        if tpl is not None:
            if design.problem_family != tpl.problem_family:
                g2_failures.append(GateFailure(
                    gate_id=2,
                    gate_name="template_and_signature",
                    error_code="problem_family_mismatch",
                    line_no=None,
                    symbol=design.problem_family,
                    detail=f"Design problem_family='{design.problem_family}' != template '{tpl.problem_family}'.",
                    fix_hint=f"Set problem_family='{tpl.problem_family}'.",
                ))
            if design.postprocess_mode not in tpl.allowed_postprocess_modes:
                g2_failures.append(GateFailure(
                    gate_id=2,
                    gate_name="template_and_signature",
                    error_code="unsupported_postprocess_mode",
                    line_no=None,
                    symbol=design.postprocess_mode,
                    detail=f"postprocess_mode='{design.postprocess_mode}' not allowed by template.",
                    fix_hint=f"Use one of: {sorted(tpl.allowed_postprocess_modes)}.",
                ))
            if (design.hook_name != tpl.hook_name or tuple(design.hook_signature) != tuple(tpl.hook_signature)
                    or design.hook_specs != tpl.hook_specs):
                g2_failures.append(GateFailure(
                    gate_id=2,
                    gate_name="template_and_signature",
                    error_code="design_contract_mismatch",
                    line_no=None,
                    symbol=design.hook_name,
                    detail=(
                        f"Design hook contract `{design.hook_name}({', '.join(design.hook_signature)})` "
                        f"does not match template `{tpl.hook_name}({', '.join(tpl.hook_signature)})`."
                    ),
                    fix_hint="Align design.hook_name and design.hook_signature with the registered TemplateSpec.",
                ))
            protocol_id = tpl.effective_protocol_id
            if ((design.protocol_id is not None and design.protocol_id != protocol_id)
                    or (tpl.protocol_id is not None and design.protocol_id != tpl.protocol_id)):
                g2_failures.append(GateFailure(
                    2, "template_and_signature", "protocol_id_mismatch", None, design.protocol_id,
                    f"Expected protocol {protocol_id}.", "Use the protocol declared by the registered template.",
                ))
            diagnostics["gate2"] = {
                "template_source_sha256": tpl.template_source_sha256,
                "advisory_deadline_supported": tpl.advisory_deadline_supported,
            }

        g2_passed = (tpl is not None) and (len(g2_failures) == 0)
        gates_summary.append({
            "gate_id": 2,
            "gate_name": "template_and_signature",
            "passed": g2_passed,
            "failure_count": len(g2_failures) + (0 if tpl is not None else 1),
        })
        failures.extend(g2_failures)

        def report() -> ValidationReport:
            return ValidationReport(
                passed=not failures,
                design_id=design.design_id,
                design_sha256=design.design_sha256,
                template_id=design.template_id,
                template_version=design.template_version,
                template_source_sha256=template_sha,
                hook_code_sha256=hook_sha,
                gates=tuple(gates_summary),
                failures=tuple(failures),
                diagnostics=diagnostics,
            )

        # Short-circuit execution gates if Gate 1 or Gate 2 failed
        if failures or tpl is None:
            for gid, gname in ((3, "subprocess_feasibility"), (4, "dual_action_causal_sensitivity"), (5, "budget_and_scale_diagnostics")):
                gates_summary.append({"gate_id": gid, "gate_name": gname, "passed": False, "skipped": True})
            return report()

        protocol_id = tpl.effective_protocol_id
        probe_spec = _resolve_gate_probe(design, protocol_id)
        evaluator = partial(
            self.evaluator.evaluate,
            template_id=design.template_id,
            template_version=design.template_version,
            postprocess_mode=design.postprocess_mode,
            template_options=design.template_options,
            protocol_id=protocol_id,
            instance_time_budget_ms=self.instance_time_budget_ms,
            allow_extended_numpy_whitelist=allow_extended_numpy,
            **({"outer_timeout_s": self.outer_timeout_s} if self.outer_timeout_s is not None else {}),
        )
        if probe_spec is not None:
            def evaluate_probe(
                instances: Sequence[Mapping[str, Any]], *,
                hook_code: str | None = None,
                hook_implementations: Mapping[str, str] | None = None,
                capture_merge_sequence: bool = False,
                distance_convention: str | None = None,
            ) -> dict[str, Any]:
                sources = implementations if hook_code is None and hook_implementations is None else hook_implementations
                return evaluator(
                    instances=instances,
                    hook_code=hook_code if sources is not None or hook_code is not None else candidate_code,
                    hook_implementations=sources,
                    distance_convention=distance_convention or probe_spec.distance_convention,
                    vehicle_limit_policy=probe_spec.vehicle_limit_policy,
                    capture_merge_sequence=capture_merge_sequence,
                )

            candidate_code = hook_code
            context = GateProbeContext(design, protocol_id, self.instance_time_budget_ms, evaluate_probe)
            self._validate_registered_probes(
                probe_spec, context, gate3_instances, gate5_n200_instances, gates_summary, failures, diagnostics,
            )
            return report()

        # --- Gate 3: Restricted Subprocess Execution & Baseline Feasibility ---
        probe_family = PROBLEM_GATE_PROBES.get(design.problem_family)
        if (not isinstance(probe_family, ProblemGateProbes) or protocol_id != LEGACY_CVRP_PROTOCOL_ID
                or design.template_id not in _GATE4_PROBES_BY_TEMPLATE):
            failures.append(GateFailure(
                3, "subprocess_feasibility", "missing_problem_gate_probe", None, protocol_id,
                "No validation probes are registered for this template and protocol.", "Register ProblemGateProbeSpec.",
            ))
            gates_summary.extend([
                {"gate_id": 3, "gate_name": "subprocess_feasibility", "passed": False},
                {"gate_id": 4, "gate_name": "dual_action_causal_sensitivity", "passed": False, "skipped": True},
                {"gate_id": 5, "gate_name": "budget_and_scale_diagnostics", "passed": False, "skipped": True},
            ])
            return report()
        g3_insts = list(gate3_instances) if gate3_instances is not None else probe_family.gate3_instances()
        g3_resp = evaluator(
            hook_code=hook_code,
            instances=g3_insts,
        )
        g3_failures: list[GateFailure] = []
        if not g3_resp.get("valid"):
            g3_failures.append(GateFailure(
                gate_id=3,
                gate_name="subprocess_feasibility",
                error_code=str(g3_resp.get("error_code") or "baseline_infeasible"),
                line_no=None,
                symbol=design.hook_name,
                detail=str(g3_resp.get("error_detail") or "Candidate failed feasibility on Gate 3 instances."),
                fix_hint="Return finite 1D float scores of length len(i_idx) without mutating inputs or exceeding timeout.",
            ))
        gates_summary.append({
            "gate_id": 3,
            "gate_name": "subprocess_feasibility",
            "passed": len(g3_failures) == 0,
            "n_instances": len(g3_insts),
            "objective": g3_resp.get("objective"),
            "worker_wall_ms": g3_resp.get("worker_wall_ms"),
            "subprocess_overhead_ms": g3_resp.get("subprocess_overhead_ms"),
        })
        diagnostics["gate3"] = {
            "n_instances": len(g3_insts),
            "objective": g3_resp.get("objective"),
            "outcomes": [r.get("outcome_class") for r in g3_resp.get("records", [])],
            "worker_wall_ms": g3_resp.get("worker_wall_ms"),
            "subprocess_overhead_ms": g3_resp.get("subprocess_overhead_ms"),
        }
        failures.extend(g3_failures)

        if g3_failures:
            for gid, gname in ((4, "dual_action_causal_sensitivity"), (5, "budget_and_scale_diagnostics")):
                gates_summary.append({"gate_id": gid, "gate_name": gname, "passed": False, "skipped": True})
            return ValidationReport(
                passed=False,
                design_id=design.design_id,
                design_sha256=design.design_sha256,
                template_id=design.template_id,
                template_version=design.template_version,
                template_source_sha256=template_sha,
                hook_code_sha256=hook_sha,
                gates=tuple(gates_summary),
                failures=tuple(failures),
                diagnostics=diagnostics,
            )

        # --- Gate 4: Dual-Action Causal Sensitivity Probe (Pre-Postprocessing) ---
        g4_inst = probe_family.gate4_instance(design.template_id)
        probe_cfg = _GATE4_PROBES_BY_TEMPLATE.get(design.template_id)
        if probe_cfg is None:
            raise ValueError(f"missing_gate4_probe_config:{design.template_id}")
        expected_a = probe_cfg["expected_A"]
        expected_b = probe_cfg["expected_B"]
        probe_a = evaluator(
            hook_code=probe_cfg["prefer_A"],
            instances=[g4_inst],
            capture_merge_sequence=True,
        )
        probe_b = evaluator(
            hook_code=probe_cfg["prefer_B"],
            instances=[g4_inst],
            capture_merge_sequence=True,
        )
        # Supplementary diagnostics on the actual candidate hook + negated + constant-zero
        probe_base = evaluator(
            hook_code=hook_code,
            instances=[g4_inst],
            capture_merge_sequence=True,
        )
        probe_zero = evaluator(
            hook_code=probe_cfg["constant_zero"],
            instances=[g4_inst],
            capture_merge_sequence=True,
        )
        probe_neg = evaluator(
            hook_code=probe_cfg["negated"],
            instances=[g4_inst],
            capture_merge_sequence=True,
        )

        g4_failures: list[GateFailure] = []
        rec_a = (probe_a.get("records") or [{}])[0]
        rec_b = (probe_b.get("records") or [{}])[0]
        rec_base = (probe_base.get("records") or [{}])[0]
        seq_a = rec_a.get("merge_sequence") or []
        seq_b = rec_b.get("merge_sequence") or []
        pre_a = rec_a.get("pre_postprocess_routes") or []
        pre_b = rec_b.get("pre_postprocess_routes") or []

        first_a = seq_a[0] if seq_a else None
        first_b = seq_b[0] if seq_b else None
        base_calls = int(rec_base.get("hook_call_count", 0))

        if not (probe_a.get("valid") and probe_b.get("valid")):
            g4_failures.append(GateFailure(
                gate_id=4,
                gate_name="dual_action_causal_sensitivity",
                error_code="probe_execution_failed",
                line_no=None,
                symbol=design.hook_name,
                detail=f"Dual-action probe failed: probe_a={probe_a.get('error_code')}, probe_b={probe_b.get('error_code')}.",
                fix_hint="Ensure template accepts valid hook priority scores and constructs feasible routes.",
            ))
        elif first_a != expected_a or first_b != expected_b or pre_a == pre_b:
            g4_failures.append(GateFailure(
                gate_id=4,
                gate_name="dual_action_causal_sensitivity",
                error_code="hook_not_causally_effective",
                line_no=None,
                symbol=design.hook_name,
                detail=(
                    f"Pre-postprocessing causal check failed: prefer_A executed {first_a} (expected {expected_a}), "
                    f"prefer_B executed {first_b} (expected {expected_b}), pre_routes_equal={pre_a == pre_b}."
                ),
                fix_hint="Verify the template actually executes decisions according to the hook's output before postprocessing.",
            ))
        if base_calls < 1:
            g4_failures.append(GateFailure(
                gate_id=4,
                gate_name="dual_action_causal_sensitivity",
                error_code="hook_never_called",
                line_no=None,
                symbol=design.hook_name,
                detail=f"Hook call count was {base_calls} (< 1) on the diagnostic instance.",
                fix_hint="Ensure the template invokes hook_fn on non-empty candidate pairs.",
            ))

        gates_summary.append({
            "gate_id": 4,
            "gate_name": "dual_action_causal_sensitivity",
            "passed": len(g4_failures) == 0,
            "first_merge_prefer_A": first_a,
            "first_merge_prefer_B": first_b,
            "pre_postprocess_routes_differ": pre_a != pre_b,
            "baseline_hook_calls": base_calls,
        })
        diagnostics["gate4"] = {
            "instance_id": g4_inst["instance_id"],
            "prefer_A_first_merge": first_a,
            "prefer_B_first_merge": first_b,
            "prefer_A_pre_routes": pre_a,
            "prefer_B_pre_routes": pre_b,
            "baseline_hook_calls": base_calls,
            "baseline_pre_routes": rec_base.get("pre_postprocess_routes"),
            "constant_zero_pre_routes": ((probe_zero.get("records") or [{}])[0]).get("pre_postprocess_routes"),
            "negated_cw_pre_routes": ((probe_neg.get("records") or [{}])[0]).get("pre_postprocess_routes"),
        }
        failures.extend(g4_failures)

        # --- Gate 5: Unified 500 ms Budget Boundary, 3-Class Outcomes & Scale Drift ---
        if gate5_n200_instances is not None and gate5_scale_pair is not None:
            n200_list = list(gate5_n200_instances)
            nom_inst, scl_inst = gate5_scale_pair
        else:
            n200_list, nom_inst, scl_inst = probe_family.gate5_instances()

        g5_insts = [*n200_list, nom_inst, scl_inst]
        g5_resp = evaluator(
            hook_code=hook_code,
            instances=g5_insts,
        )

        g5_failures: list[GateFailure] = []
        g5_records = g5_resp.get("records") or []
        outcome_counts = {
            OUTCOME_COMPLETED: 0,
            OUTCOME_BUDGET_EXHAUSTED_INCUMBENT: 0,
            OUTCOME_TIMEOUT_OR_INFEASIBLE: 0,
        }
        for rec in g5_records:
            oc = str(rec.get("outcome_class", OUTCOME_TIMEOUT_OR_INFEASIBLE))
            outcome_counts[oc] = outcome_counts.get(oc, 0) + 1

        if not g5_resp.get("valid") or outcome_counts[OUTCOME_TIMEOUT_OR_INFEASIBLE] > 0:
            g5_failures.append(GateFailure(
                gate_id=5,
                gate_name="budget_and_scale_diagnostics",
                error_code=str(g5_resp.get("error_code") or "budget_or_infeasible_failure"),
                line_no=None,
                symbol=design.hook_name,
                detail=(
                    f"Gate 5 encountered timeout_or_infeasible={outcome_counts[OUTCOME_TIMEOUT_OR_INFEASIBLE]} "
                    f"(error={g5_resp.get('error_code')}: {g5_resp.get('error_detail')})."
                ),
                fix_hint=f"Optimize hook to complete within {self.instance_time_budget_ms:.0f} ms per instance and return feasible finite scores.",
            ))

        # Compute 1e-3 scale drift diagnostic (advisory warning, does not silently hide drift)
        scale_drift_pct: float | None = None
        if len(g5_records) >= 2:
            nom_rec = g5_records[-2]
            scl_rec = g5_records[-1]
            scale_val = float(scl_inst.get("coord_scale", 1e-3))
            if nom_rec.get("tour_length") is not None and scl_rec.get("tour_length") is not None:
                nom_len = float(nom_rec["tour_length"])
                norm_scl = float(scl_rec["tour_length"]) / scale_val
                scale_drift_pct = round(100.0 * abs(norm_scl - nom_len) / max(nom_len, 1e-12), 4)

        timing_rows = [
            {
                "instance_id": r.get("instance_id"),
                "outcome_class": r.get("outcome_class"),
                "stop_reason": r.get("stop_reason"),
                "preprocess_ms": r.get("preprocess_ms"),
                "candidate_gen_ms": r.get("candidate_gen_ms"),
                "hook_ms": r.get("hook_ms"),
                "merge_ms": r.get("merge_ms"),
                "postprocess_ms": r.get("postprocess_ms"),
                "solve_ms": r.get("solve_ms"),
                "verify_ms": r.get("verify_ms"),
            }
            for r in g5_records
        ]
        max_solve_ms = max((float(r["solve_ms"]) for r in g5_records if r.get("solve_ms") is not None), default=None)

        gates_summary.append({
            "gate_id": 5,
            "gate_name": "budget_and_scale_diagnostics",
            "passed": len(g5_failures) == 0,
            "outcome_counts": outcome_counts,
            "max_solve_ms": max_solve_ms,
            "budget_headroom_ms": round(self.instance_time_budget_ms - max_solve_ms, 4) if max_solve_ms is not None else None,
            "scale_drift_pct": scale_drift_pct,
            "scale_drift_warning": bool(scale_drift_pct is not None and scale_drift_pct > 0.05),
        })
        diagnostics["gate5"] = {
            "budget_ms": self.instance_time_budget_ms,
            "outcome_counts": outcome_counts,
            "max_solve_ms": max_solve_ms,
            "budget_headroom_ms": round(self.instance_time_budget_ms - max_solve_ms, 4) if max_solve_ms is not None else None,
            "scale_drift_pct": scale_drift_pct,
            "scale_drift_warning": bool(scale_drift_pct is not None and scale_drift_pct > 0.05),
            "worker_wall_ms": g5_resp.get("worker_wall_ms"),
            "subprocess_overhead_ms": g5_resp.get("subprocess_overhead_ms"),
            "timing_breakdown": timing_rows,
        }
        failures.extend(g5_failures)

        return report()

    def validate_evolved_hook_n200_latency(
        self,
        design: InterfaceDesign,
        *,
        hook_code_override: str | None = None,
        hook_implementations: Mapping[str, str] | None = None,
        gate5_n200_instances: Sequence[Mapping[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Screen an evolved candidate hook directly on n=200 Gate-5 stress probes.

        Closes the inner-loop latency blind spot where Gate 5 was previously invoked
        only on the template baseline hook during design submission.
        """
        n200_insts = list(gate5_n200_instances) if gate5_n200_instances is not None else _build_gate5_n200_stress_instances()
        tpl = get_template_spec(design.template_id, design.template_version)
        hook_code = hook_code_override if hook_code_override is not None else design.baseline_hook_code
        eval_kwargs: dict[str, Any] = {
            "template_id": design.template_id,
            "template_version": design.template_version,
            "postprocess_mode": design.postprocess_mode,
            "template_options": design.template_options,
            "protocol_id": tpl.effective_protocol_id,
            "hook_code": hook_code,
            "instances": n200_insts,
            "solve_deadline_ms": self.instance_time_budget_ms,
            "allow_extended_numpy_whitelist": self._allow_extended_numpy(design),
            "enable_degenerate_constant_screen": self.enable_degenerate_constant_screen,
        }
        if hook_implementations is not None:
            eval_kwargs["hook_implementations"] = dict(hook_implementations)
        if self.outer_timeout_s is not None:
            eval_kwargs["outer_timeout_s"] = self.outer_timeout_s
        resp = self.evaluator.evaluate(**eval_kwargs)
        records = list(resp.get("records") or [])
        solve_times = [
            float(r["solve_ms"]) for r in records
            if isinstance(r.get("solve_ms"), (int, float)) and math.isfinite(r["solve_ms"])
        ]
        timeouts = sum(
            1 for r in records if r.get("budget_exhausted") is True or r.get("completed") is not True
            or (isinstance(r.get("solve_ms"), (int, float)) and r["solve_ms"] > self.instance_time_budget_ms)
        )
        feasible_count = sum(1 for r in records if r.get("valid") is True and r.get("objective") is not None)
        max_solve_ms = max(solve_times) if solve_times else None
        return {
            "passed": bool(
                n200_insts and resp.get("valid") and len(records) == len(n200_insts)
                and timeouts == 0 and len(solve_times) == feasible_count == len(n200_insts)
            ),
            "budget_ms": self.instance_time_budget_ms,
            "n_instances": len(n200_insts),
            "feasible_count": feasible_count,
            "timeout_count": timeouts,
            "max_solve_ms": round(max_solve_ms, 4) if max_solve_ms is not None else None,
            "budget_headroom_ms": round(self.instance_time_budget_ms - max_solve_ms, 4) if max_solve_ms is not None else None,
            "error_code": resp.get("error_code"),
            "error_detail": resp.get("error_detail"),
            "timeout_kind": resp.get("timeout_kind") or next(
                (record["timeout_kind"] for record in records if record.get("timeout_kind")), None,
            ),
            "outer_timeout_s": resp.get("outer_timeout_s"),
            "worker_wall_ms": resp.get("worker_wall_ms"),
            "failures": resp.get("failures") or [],
        }

    @staticmethod
    def _validate_registered_probes(
        spec: ProblemGateProbeSpec,
        context: GateProbeContext,
        gate3_override: Sequence[Mapping[str, Any]] | None,
        gate5_override: Sequence[Mapping[str, Any]] | None,
        gates: list[dict[str, Any]],
        failures: list[GateFailure],
        diagnostics: dict[str, Any],
    ) -> None:
        def add_gate(gate_id: int, name: str, result: GateProbeResult) -> None:
            gates.append({"gate_id": gate_id, "gate_name": name, "passed": not result.failures})
            diagnostics[f"gate{gate_id}"] = result.diagnostics
            failures.extend(result.failures)

        def evaluate_fixtures(
            instances: Sequence[Mapping[str, Any]], gate_id: int, name: str,
        ) -> tuple[GateProbeResult, Sequence[Mapping[str, Any]]]:
            if not instances:
                return GateProbeResult(failures=(GateFailure(
                    gate_id, name, "missing_probe_instances", None, None,
                    "The protocol gate has no fixtures.", "Register nonempty fixtures for this gate.",
                ),)), ()
            response = context.evaluate(instances)
            records = response.get("records", [])
            verified = (
                response.get("valid") and len(records) == len(instances)
                and all(record.get("valid") and record.get("objective") is not None for record in records)
            )
            errors = () if verified else (GateFailure(
                gate_id, name, response.get("error_code") or "probe_evaluation_failed", None, None,
                response.get("error_detail") or "The worker did not return verified objectives for all fixtures.",
                "Check feasibility, score shape, and timeout diagnostics.",
            ),)
            return GateProbeResult({
                "n_instances": len(instances),
                "objective": response.get("objective"),
                "outcomes": [record.get("outcome_class") for record in records],
                "timeout_kind": response.get("timeout_kind"),
                "outer_timeout_s": response.get("outer_timeout_s"),
            }, errors), records

        gate3_name = "subprocess_feasibility"
        gate4_name = "dual_action_causal_sensitivity"
        gate5_name = "budget_and_scale_diagnostics"
        gate3_instances = spec.gate3_instances(context.design) if gate3_override is None else gate3_override
        gate3, _ = evaluate_fixtures(gate3_instances, 3, gate3_name)
        add_gate(3, gate3_name, gate3)
        if gate3.failures:
            gates.extend([
                {"gate_id": 4, "gate_name": gate4_name, "passed": False, "skipped": True},
                {"gate_id": 5, "gate_name": gate5_name, "passed": False, "skipped": True},
            ])
            return
        add_gate(4, gate4_name, spec.gate4(context))
        gate5_instances = spec.gate5_instances(context.design) if gate5_override is None else gate5_override
        stress, records = evaluate_fixtures(gate5_instances, 5, gate5_name)
        if not stress.failures and spec.gate5 is not None:
            scale = spec.gate5(context, records)
            stress = GateProbeResult({**stress.diagnostics, **scale.diagnostics}, scale.failures)
        add_gate(5, gate5_name, stress)
