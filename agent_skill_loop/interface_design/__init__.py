"""Milestone 2: Diagnostic-driven autonomous solver interface design and validation.

Pure additive package layered on top of Milestone 1 / 1.5 immutable infrastructure
without modifying ``eoh_frozen/``, ``benchmarks/eohs_v1/``, or historic releases.
"""

from .archive import ComplementaryArchive, compute_portfolio_complementarity
from .blind_commitment import (
    BLIND_COMMITMENT_PATH,
    DEFAULT_SEALED_BLIND_PATH,
    SEALED_BLIND_SUITE_ID,
    seal_m2_blind_120,
    verify_sealed_against_commitment,
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
from .dynamic_eoh import DynamicInterfaceProblem, run_dynamic_eoh_evolution
from .planner import (
    CANDIDATE_TEMPLATE_ORDER,
    build_design_for_template,
    probe_template_budget_headroom,
    run_short_pilot_racing,
    select_interface_by_diagnostic_rule,
    select_interface_by_llm_planner,
)
from .runtime import (
    DynamicSubprocessEvaluator,
    compile_hook_function,
    evaluate_frozen_interface_solver,
    validate_hook_ast,
)
from .templates import (
    CLASSIC_CW_DYNAMIC_STATIC_HOOK_CODE,
    CLASSIC_CW_STATIC_HOOK_CODE,
    CLASSIC_NN_SEQUENTIAL_HOOK_CODE,
    TEMPLATE_REGISTRY,
    TemplateSpec,
    apply_intra_2opt,
    apply_relocate_2opt,
    build_classic_cw_static_design,
    build_parallel_merge_dynamic_design,
    build_sequential_construct_design,
    get_template_spec,
)
from .validator import InterfaceValidator

__all__ = [
    "ALLOWED_POSTPROCESS_MODES",
    "BLIND_COMMITMENT_PATH",
    "CLASSIC_CW_STATIC_HOOK_CODE",
    "DEFAULT_SEALED_BLIND_PATH",
    "DynamicInterfaceProblem",
    "DynamicSubprocessEvaluator",
    "FrozenInterfaceSolver",
    "GateFailure",
    "InterfaceDesign",
    "InterfaceValidator",
    "SEALED_BLIND_SUITE_ID",
    "TEMPLATE_REGISTRY",
    "TemplateSpec",
    "ValidationReport",
    "apply_intra_2opt",
    "apply_relocate_2opt",
    "build_classic_cw_static_design",
    "classify_outcome",
    "compile_hook_function",
    "evaluate_frozen_interface_solver",
    "get_template_spec",
    "run_dynamic_eoh_evolution",
    "run_gap_decomposition_diagnostic",
    "seal_m2_blind_120",
    "validate_hook_ast",
    "verify_sealed_against_commitment",
]
