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

from typing import Any, Mapping, Sequence

from agent_skill_loop.benchmark.catalog import load_profile_suite
from agent_skill_loop.cvrp_workbench.suites import BENCHMARK_ID

from .blind_commitment import assert_suite_not_m2_blind
from .contracts import (
    OUTCOME_BUDGET_EXHAUSTED_INCUMBENT,
    OUTCOME_COMPLETED,
    OUTCOME_TIMEOUT_OR_INFEASIBLE,
    GateFailure,
    InterfaceDesign,
    ValidationReport,
    sha256_text,
)
from .runtime import DynamicSubprocessEvaluator, validate_hook_ast
from .templates import get_template_spec


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
}


def _default_gate3_instances() -> list[dict[str, Any]]:
    suite = load_profile_suite(BENCHMARK_ID, "cvrp_dev_hetero_24", split="dev_train")
    assert_suite_not_m2_blind("cvrp_dev_hetero_24", suite)
    insts = suite["instances"]
    # 4 balanced instances covering n=50/100, uniform/clustered, centre/eccentric, loose/tight
    return [insts[0], insts[5], insts[12], insts[17]]


def _default_gate5_instances() -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    dev_suite = load_profile_suite(BENCHMARK_ID, "cvrp_dev_hetero_24", split="dev_train")
    sel_suite = load_profile_suite(BENCHMARK_ID, "cvrp_select_multiscale_64", split="selection")
    assert_suite_not_m2_blind("cvrp_dev_hetero_24", dev_suite)
    assert_suite_not_m2_blind("cvrp_select_multiscale_64", sel_suite)
    n200_insts = [inst for inst in sel_suite["instances"] if int(inst["size"]) == 200][:2]
    nominal = dev_suite["instances"][0]
    scaled = dev_suite["scale_stress_instances"][0]
    return n200_insts, nominal, scaled


class InterfaceValidator:
    """Five-gate behavioral validator for Milestone 2 InterfaceDesign objects."""

    def __init__(
        self,
        *,
        candidate_timeout_s: float = 20.0,
        instance_time_budget_ms: float = 500.0,
        evaluator: DynamicSubprocessEvaluator | None = None,
    ) -> None:
        self.candidate_timeout_s = float(candidate_timeout_s)
        self.instance_time_budget_ms = float(instance_time_budget_ms)
        self.evaluator = evaluator or DynamicSubprocessEvaluator(candidate_timeout_s=self.candidate_timeout_s)

    def validate(
        self,
        design: InterfaceDesign,
        *,
        gate3_instances: Sequence[Mapping[str, Any]] | None = None,
        gate5_n200_instances: Sequence[Mapping[str, Any]] | None = None,
        gate5_scale_pair: tuple[Mapping[str, Any], Mapping[str, Any]] | None = None,
        hook_code_override: str | None = None,
    ) -> ValidationReport:
        """Run all 5 validation gates sequentially and return a structured ``ValidationReport``."""
        hook_code = hook_code_override if hook_code_override is not None else design.baseline_hook_code
        hook_sha = sha256_text(hook_code)
        gates_summary: list[dict[str, Any]] = []
        failures: list[GateFailure] = []
        diagnostics: dict[str, Any] = {
            "candidate_timeout_s": self.candidate_timeout_s,
            "instance_time_budget_ms": self.instance_time_budget_ms,
        }

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
        g1_failures, g2_sig_failures = validate_hook_ast(
            hook_code,
            hook_name=expected_hook_name,
            expected_args=expected_args,
        )
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
            if design.hook_name != tpl.hook_name or tuple(design.hook_signature) != tuple(tpl.hook_signature):
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

        # Short-circuit execution gates if Gate 1 or Gate 2 failed
        if failures or tpl is None:
            for gid, gname in ((3, "subprocess_feasibility"), (4, "dual_action_causal_sensitivity"), (5, "budget_and_scale_diagnostics")):
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

        # --- Gate 3: Restricted Subprocess Execution & Baseline Feasibility ---
        g3_insts = list(gate3_instances) if gate3_instances is not None else _default_gate3_instances()
        g3_resp = self.evaluator.evaluate(
            template_id=design.template_id,
            template_version=design.template_version,
            hook_code=hook_code,
            instances=g3_insts,
            postprocess_mode=design.postprocess_mode,
            template_options=design.template_options,
            instance_time_budget_ms=self.instance_time_budget_ms,
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
        g4_inst = build_gate4_dual_action_instance()
        probe_cfg = _GATE4_PROBES_BY_TEMPLATE.get(design.template_id)
        if probe_cfg is None:
            raise ValueError(f"missing_gate4_probe_config:{design.template_id}")
        expected_a = probe_cfg["expected_A"]
        expected_b = probe_cfg["expected_B"]
        probe_a = self.evaluator.evaluate(
            template_id=design.template_id,
            template_version=design.template_version,
            hook_code=probe_cfg["prefer_A"],
            instances=[g4_inst],
            postprocess_mode=design.postprocess_mode,
            template_options=design.template_options,
            instance_time_budget_ms=self.instance_time_budget_ms,
            capture_merge_sequence=True,
        )
        probe_b = self.evaluator.evaluate(
            template_id=design.template_id,
            template_version=design.template_version,
            hook_code=probe_cfg["prefer_B"],
            instances=[g4_inst],
            postprocess_mode=design.postprocess_mode,
            template_options=design.template_options,
            instance_time_budget_ms=self.instance_time_budget_ms,
            capture_merge_sequence=True,
        )
        # Supplementary diagnostics on the actual candidate hook + negated + constant-zero
        probe_base = self.evaluator.evaluate(
            template_id=design.template_id,
            template_version=design.template_version,
            hook_code=hook_code,
            instances=[g4_inst],
            postprocess_mode=design.postprocess_mode,
            template_options=design.template_options,
            instance_time_budget_ms=self.instance_time_budget_ms,
            capture_merge_sequence=True,
        )
        probe_zero = self.evaluator.evaluate(
            template_id=design.template_id,
            template_version=design.template_version,
            hook_code=probe_cfg["constant_zero"],
            instances=[g4_inst],
            postprocess_mode=design.postprocess_mode,
            template_options=design.template_options,
            instance_time_budget_ms=self.instance_time_budget_ms,
            capture_merge_sequence=True,
        )
        probe_neg = self.evaluator.evaluate(
            template_id=design.template_id,
            template_version=design.template_version,
            hook_code=probe_cfg["negated"],
            instances=[g4_inst],
            postprocess_mode=design.postprocess_mode,
            template_options=design.template_options,
            instance_time_budget_ms=self.instance_time_budget_ms,
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
            n200_list, nom_inst, scl_inst = _default_gate5_instances()

        g5_insts = [*n200_list, nom_inst, scl_inst]
        g5_resp = self.evaluator.evaluate(
            template_id=design.template_id,
            template_version=design.template_version,
            hook_code=hook_code,
            instances=g5_insts,
            postprocess_mode=design.postprocess_mode,
            template_options=design.template_options,
            instance_time_budget_ms=self.instance_time_budget_ms,
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

        return ValidationReport(
            passed=len(failures) == 0,
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
