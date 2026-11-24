"""Milestone 2: Diagnostic-driven autonomous solver interface design and validation.

Pure additive package layered on top of Milestone 1 / 1.5 immutable infrastructure
without modifying ``eoh_frozen/``, ``benchmarks/eohs_v1/``, or historic releases.
"""

from .archive import ComplementaryArchive, compute_portfolio_complementarity
from .blind_commitment import (
    ALL_BLIND_SUITE_IDS,
    BLIND_COMMITMENT_PATH,
    DEFAULT_SEALED_BLIND_PATH,
    M3_BLIND_COMMITMENT_PATH,
    SEALED_BLIND_SUITE_ID,
    SEALED_M3_BLIND_SUITE_ID,
    assert_suite_allowed_for_interactive_role,
    assert_suite_not_blind,
    seal_m2_blind_120,
    seal_m3_blind_120,
    verify_sealed_against_commitment,
)
from .blind_eval import (
    execute_m2_blind_evaluation,
    freeze_pre_blind_protocol,
    paired_bootstrap_comparison,
    paired_wilcoxon_signed_rank,
    unseal_and_verify_m2_blind_suite,
)
from .contracts import (
    ALLOWED_POSTPROCESS_MODES,
    FrozenInterfaceSolver,
    GateFailure,
    HookSpec,
    InterfaceDesign,
    LEGACY_CVRP_PROTOCOL_ID,
    ValidationReport,
    classify_outcome,
    hook_bundle_metadata,
)
from .diagnostics import run_gap_decomposition_diagnostic
from .planner import (
    CANDIDATE_TEMPLATE_ORDER,
    M3_CANDIDATE_TEMPLATE_ORDER,
    build_design_for_template,
    build_interface_design,
    parse_hook_candidate,
    probe_template_budget_headroom,
    run_short_pilot_racing,
    select_interface_by_diagnostic_rule,
    select_interface_by_llm_planner,
)
from .runtime import (
    PROBLEM_ADAPTERS,
    DynamicSubprocessEvaluator,
    ProblemRuntimeAdapter,
    compile_hook_bundle,
    compile_hook_function,
    derive_outer_timeout_s,
    evaluate_frozen_interface_solver,
    evaluate_hook_on_instance_inprocess,
    register_problem_adapter,
    resolve_problem_adapter,
    validate_hook_ast,
    validate_hook_bundle,
)
from .templates import (
    CLASSIC_CW_DYNAMIC_STATIC_HOOK_CODE,
    CLASSIC_CW_STATIC_HOOK_CODE,
    CLASSIC_L3_WORST_REMOVAL_HOOK_CODE,
    CLASSIC_NN_SEQUENTIAL_HOOK_CODE,
    TEMPLATE_REGISTRY,
    TemplateSpec,
    apply_intra_2opt,
    apply_relocate_2opt,
    build_classic_cw_static_design,
    build_parallel_merge_dynamic_design,
    build_ruin_recreate_design,
    build_sequential_construct_design,
    compute_template_source_sha256,
    get_template_spec,
    register_template,
)
from .validator import (
    PROBLEM_GATE_PROBES,
    GateProbeContext,
    GateProbeResult,
    InterfaceValidator,
    ProblemGateProbes,
    ProblemGateProbeSpec,
    register_problem_gate_probe,
)

__all__ = [
    "ALL_BLIND_SUITE_IDS",
    "ALLOWED_POSTPROCESS_MODES",
    "BLIND_COMMITMENT_PATH",
    "CLASSIC_CW_STATIC_HOOK_CODE",
    "CLASSIC_L3_WORST_REMOVAL_HOOK_CODE",
    "DEFAULT_MOCK_CANDIDATES_BY_TEMPLATE",
    "DEFAULT_SEALED_BLIND_PATH",
    "DynamicInterfaceProblem",
    "DynamicSubprocessEvaluator",
    "FrozenInterfaceSolver",
    "GateFailure",
    "GateProbeContext",
    "GateProbeResult",
    "HookSpec",
    "InterfaceDesign",
    "InterfaceValidator",
    "LEGACY_CVRP_PROTOCOL_ID",
    "M3_BLIND_COMMITMENT_PATH",
    "M3_CANDIDATE_TEMPLATE_ORDER",
    "PROBLEM_ADAPTERS",
    "PROBLEM_GATE_PROBES",
    "ProblemGateProbes",
    "ProblemGateProbeSpec",
    "ProblemRuntimeAdapter",
    "SEALED_BLIND_SUITE_ID",
    "SEALED_M3_BLIND_SUITE_ID",
    "TEMPLATE_REGISTRY",
    "TemplateSpec",
    "ValidationReport",
    "apply_intra_2opt",
    "apply_relocate_2opt",
    "assert_suite_allowed_for_interactive_role",
    "assert_suite_not_blind",
    "build_classic_cw_static_design",
    "build_interface_design",
    "build_ruin_recreate_design",
    "classify_outcome",
    "compile_hook_bundle",
    "compile_hook_function",
    "compute_template_source_sha256",
    "derive_outer_timeout_s",
    "evaluate_frozen_interface_solver",
    "evaluate_hook_on_instance_inprocess",
    "get_template_spec",
    "hook_bundle_metadata",
    "parse_hook_candidate",
    "register_problem_adapter",
    "register_problem_gate_probe",
    "register_template",
    "resolve_problem_adapter",
    "run_dynamic_eoh_evolution",
    "run_gap_decomposition_diagnostic",
    "seal_m2_blind_120",
    "seal_m3_blind_120",
    "validate_hook_ast",
    "validate_hook_bundle",
    "verify_sealed_against_commitment",
]


def __getattr__(name: str):
    if name in {
        "DEFAULT_MOCK_CANDIDATES_BY_TEMPLATE",
        "DynamicInterfaceProblem",
        "run_dynamic_eoh_evolution",
    }:
        from . import dynamic_eoh

        return getattr(dynamic_eoh, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
