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
    InterfaceDesign,
    ValidationReport,
    classify_outcome,
)
from .diagnostics import run_gap_decomposition_diagnostic
from .dynamic_eoh import (
    DEFAULT_MOCK_CANDIDATES_BY_TEMPLATE,
    DynamicInterfaceProblem,
    run_dynamic_eoh_evolution,
)
from .planner import (
    CANDIDATE_TEMPLATE_ORDER,
    M3_CANDIDATE_TEMPLATE_ORDER,
    build_design_for_template,
    probe_template_budget_headroom,
    run_short_pilot_racing,
    select_interface_by_diagnostic_rule,
    select_interface_by_llm_planner,
)
from .runtime import (
    PROBLEM_ADAPTERS,
    DynamicSubprocessEvaluator,
    ProblemRuntimeAdapter,
    compile_hook_function,
    evaluate_frozen_interface_solver,
    validate_hook_ast,
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
    get_template_spec,
)
from .validator import PROBLEM_GATE_PROBES, InterfaceValidator, ProblemGateProbes

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
    "InterfaceDesign",
    "InterfaceValidator",
    "M3_BLIND_COMMITMENT_PATH",
    "M3_CANDIDATE_TEMPLATE_ORDER",
    "PROBLEM_ADAPTERS",
    "PROBLEM_GATE_PROBES",
    "ProblemGateProbes",
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
    "build_ruin_recreate_design",
    "classify_outcome",
    "compile_hook_function",
    "evaluate_frozen_interface_solver",
    "get_template_spec",
    "run_dynamic_eoh_evolution",
    "run_gap_decomposition_diagnostic",
    "seal_m2_blind_120",
    "seal_m3_blind_120",
    "validate_hook_ast",
    "verify_sealed_against_commitment",
]
