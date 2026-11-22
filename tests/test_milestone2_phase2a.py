"""Milestone 2 Phase 2A verification tests:
- 2A-1: Public blind commitment isolation & cryptographic verification
- 2A-2: 2x3 exploratory diagnostic schema, stop reasons, and blind refusal
- 2A-3: Exact un-truncated CW equivalence, 5-gate behavioral validation & all 5 adversarial catches
- 2A-4: DynamicInterfaceProblem + real upstream EoH (deterministic mock) + frozen manifest provenance
- 2A-5: run_frozen_workbench_bundle + build_dashboard integration & hash-tamper guardrails
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_skill_loop.benchmark.catalog import load_profile_suite
from agent_skill_loop.cvrp_workbench.protocol import prepare_instance_arrays, verify_cvrp_solution
from agent_skill_loop.cvrp_workbench.runner import WORKBENCH_SUITES, run_frozen_workbench_bundle
from agent_skill_loop.cvrp_workbench.solvers import solve_cw_parallel_merge
from agent_skill_loop.cvrp_workbench.suites import BENCHMARK_ID, REGISTRY_PATH
from agent_skill_loop.interface_design.blind_commitment import (
    SEALED_BLIND_SUITE_ID,
    seal_m2_blind_120,
    verify_sealed_against_commitment,
)
from agent_skill_loop.interface_design.contracts import (
    FrozenInterfaceSolver,
    InterfaceDesign,
    sha256_text,
)
from agent_skill_loop.interface_design.diagnostics import run_gap_decomposition_diagnostic
from agent_skill_loop.interface_design.dynamic_eoh import (
    DynamicInterfaceProblem,
    run_dynamic_eoh_evolution,
)
from agent_skill_loop.interface_design.runtime import (
    DynamicSubprocessEvaluator,
    compile_hook_function,
    evaluate_frozen_interface_solver,
    evaluate_hook_on_instance_inprocess,
)
from agent_skill_loop.interface_design.templates import (
    CLASSIC_CW_STATIC_HOOK_CODE,
    TEMPLATE_REGISTRY,
    TemplateSpec,
    build_classic_cw_static_design,
    get_template_spec,
)
from agent_skill_loop.interface_design.validator import InterfaceValidator, build_gate4_dual_action_instance
from frontend.build_dashboard import build_dashboard

_REPO = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# 2A-1: Blind commitment isolation & integrity
# ---------------------------------------------------------------------------

def test_2a1_blind_commitment_isolation_and_verification(tmp_path: Path) -> None:
    comm_path = tmp_path / "commitment.json"
    sealed_path = tmp_path / "sealed.json"

    seal_res = seal_m2_blind_120(
        commitment_path=comm_path,
        sealed_path=sealed_path,
        seed_token="unit_test_seed_token_20261122",
        overwrite=True,
    )
    assert seal_res["ok"] is True
    assert seal_res["instance_count"] == 120

    # Public commitment must NOT leak coordinates, demands, or seed
    comm = json.loads(comm_path.read_text(encoding="utf-8"))
    for forbidden in ("sealed_seed_token", "seed", "depot", "customer_coordinates", "demands"):
        assert forbidden not in comm
    assert comm["exposure_status"] == "locked_m2_blind"
    assert len(comm["instances"]) == 120
    for row in comm["instances"]:
        for forbidden in ("depot", "customer_coordinates", "demands", "seed", "reference_objective"):
            assert forbidden not in row
        assert len(row["instance_sha256"]) == 64

    # Cryptographic verification succeeds cleanly
    ver = verify_sealed_against_commitment(sealed_path=sealed_path, commitment_path=comm_path)
    assert ver["ok"] is True
    assert ver["verified_instances"] == 120

    # Tampering a single coordinate breaks verification immediately
    sealed_doc = json.loads(sealed_path.read_text(encoding="utf-8"))
    sealed_doc["instances"][0]["customer_coordinates"][0][0] += 0.001
    sealed_path.write_text(json.dumps(sealed_doc), encoding="utf-8")
    with pytest.raises(ValueError, match="blind_suite_sha256_mismatch"):
        verify_sealed_against_commitment(sealed_path=sealed_path, commitment_path=comm_path)

    # Default M1 loaders & registry never contain cvrp_m2_blind_120
    assert all(sid != SEALED_BLIND_SUITE_ID for sid, _ in WORKBENCH_SUITES)
    reg = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    assert SEALED_BLIND_SUITE_ID not in reg.get("profiles", {})


def test_2a1_dev_pipelines_refuse_m2_blind_suite(tmp_path: Path) -> None:
    design = build_classic_cw_static_design()
    with pytest.raises(ValueError, match="m2_blind_suite_forbidden"):
        run_gap_decomposition_diagnostic(
            output_dir=tmp_path / "diag",
            suites=((SEALED_BLIND_SUITE_ID, "heldout"),),
        )
    with pytest.raises(ValueError, match="m2_blind_suite_forbidden"):
        DynamicInterfaceProblem(
            design=design,
            instances=[build_gate4_dual_action_instance()],
            suite_id=SEALED_BLIND_SUITE_ID,
        )
    with pytest.raises(ValueError, match="m2_blind_suite_forbidden"):
        run_frozen_workbench_bundle(
            tmp_path / "wb",
            frozen_solvers=[],
            suite_specs=((SEALED_BLIND_SUITE_ID, "heldout"),),
        )


# ---------------------------------------------------------------------------
# 2A-2: Exploratory 2x3 diagnostic schema & stop reasons
# ---------------------------------------------------------------------------

def test_2a2_gap_decomposition_diagnostic_schema(tmp_path: Path) -> None:
    res = run_gap_decomposition_diagnostic(
        output_dir=tmp_path / "diag",
        suites=(("cvrp_dev_hetero_24", "dev_train"),),
        constructors=(("s2_r5_spiral", "sequential_construct"), ("cw_parallel_merge", "parallel_merge")),
        time_budget_ms=500.0,
    )
    assert res["ok"] is True
    assert res["record_count"] == 24 * 2 * 3
    doc = json.loads(Path(res["json_path"]).read_text(encoding="utf-8"))
    assert doc["run_params"]["usage_role"] == "dev_selection"
    sample = doc["records"][0]
    for field in ("raw_tour_length", "final_tour_length", "valid", "outcome_class", "stop_reason", "verify_ms"):
        assert field in sample
    # Verify exact known dev_24 bare CW mean matches M1.5 record
    cw_raw = doc["summary_by_suite"]["cvrp_dev_hetero_24"]["matrix"]["cw_parallel_merge"]["modes"]["raw"]["mean_tour_length"]
    assert abs(cw_raw - 16.2225) < 1e-4


# ---------------------------------------------------------------------------
# 2A-3: Exact CW equivalence & 5-gate behavioral validation
# ---------------------------------------------------------------------------

def test_2a3_exact_untruncated_cw_equivalence_on_dev24() -> None:
    suite = load_profile_suite(BENCHMARK_ID, "cvrp_dev_hetero_24", split="dev_train")
    tpl = get_template_spec("cvrp_parallel_merge_static", "v1")
    hook_fn = compile_hook_function(
        CLASSIC_CW_STATIC_HOOK_CODE,
        hook_name=tpl.hook_name,
        expected_args=tpl.hook_signature,
    )
    for inst in suite["instances"]:
        matrix, demands, capacity = prepare_instance_arrays(inst, distance_convention="euc_2d_float")
        ref_routes, _ = solve_cw_parallel_merge(matrix, demands, capacity, time_budget_ms=None)
        ref_ver = verify_cvrp_solution(inst, ref_routes, distance_convention="euc_2d_float")

        tpl_res = evaluate_hook_on_instance_inprocess(
            template_id="cvrp_parallel_merge_static",
            template_version="v1",
            hook_fn=hook_fn,
            instance=inst,
            postprocess_mode="none",
            template_options={"positive_savings_only": True},
            distance_convention="euc_2d_float",
            time_budget_ms=None,
            capture_merge_sequence=True,
        )
        assert tpl_res["valid"] is True
        assert tpl_res["routes"] == ref_routes
        assert abs(float(tpl_res["tour_length"]) - float(ref_ver["tour_length"])) == 0.0
        assert tpl_res["hook_call_count"] == 1


def test_2a3_five_gates_pass_classic_cw_and_relocate_postprocess() -> None:
    validator = InterfaceValidator(candidate_timeout_s=20.0, instance_time_budget_ms=500.0)
    # Test both raw and relocate_2opt (verifying Gate 4 checks pre-postprocessing causal control!)
    for mode in ("none", "relocate_2opt"):
        design = build_classic_cw_static_design(design_id=f"test_cw_{mode}", postprocess_mode=mode)
        report = validator.validate(design)
        assert report.passed is True, f"Failed for mode={mode}: {report.failures}"
        assert report.diagnostics["gate4"]["prefer_A_first_merge"] == [1, 2]
        assert report.diagnostics["gate4"]["prefer_B_first_merge"] == [1, 3]
        assert report.diagnostics["gate4"]["prefer_A_pre_routes"] != report.diagnostics["gate4"]["prefer_B_pre_routes"]
        assert report.diagnostics["gate5"]["scale_drift_pct"] == 0.0


def test_2a3_five_adversarial_failures_caught_at_exact_gates(monkeypatch: pytest.MonkeyPatch) -> None:
    base = build_classic_cw_static_design()
    validator = InterfaceValidator(candidate_timeout_s=2.5, instance_time_budget_ms=500.0)

    # Gate 1 adversarial: forbidden import os + open() -> exact line_no & symbol
    bad_ast_code = (
        "import os\n"
        "import numpy as np\n\n"
        "def score_merge_static(distance_matrix, demands, capacity, i_idx, j_idx):\n"
        "    return distance_matrix[0, i_idx]\n"
    )
    r1 = validator.validate(base, hook_code_override=bad_ast_code)
    assert r1.passed is False
    assert r1.failures[0].gate_id == 1
    assert r1.failures[0].error_code == "forbidden_import"
    assert r1.failures[0].line_no == 1
    assert r1.failures[0].symbol == "os"

    # Gate 2 adversarial: wrong parameter list
    bad_sig_code = (
        "import numpy as np\n\n"
        "def score_merge_static(distance_matrix, demands):\n"
        "    return demands\n"
    )
    r2 = validator.validate(base, hook_code_override=bad_sig_code)
    assert r2.passed is False
    assert any(f.gate_id == 2 and f.error_code == "signature_mismatch" for f in r2.failures)

    # Gate 3 adversarial: returns NaN scores -> caught at Gate 3
    bad_nan_code = (
        "import numpy as np\n\n"
        "def score_merge_static(distance_matrix, demands, capacity, i_idx, j_idx):\n"
        "    return np.full(i_idx.shape[0], np.nan)\n"
    )
    r3 = validator.validate(base, hook_code_override=bad_nan_code)
    assert r3.passed is False
    assert any(f.gate_id == 3 and f.error_code == "nonfinite_objective" for f in r3.failures)

    # Gate 4 adversarial: hollow/bypass template that ignores hook scores -> caught at Gate 4!
    def _bypass_runner(distance_matrix, demands, capacity, hook_fn, **kwargs):
        # Calls hook_fn to fake call count, then ignores its return and runs fixed CW!
        iu = [1]
        routes, meta = solve_cw_parallel_merge(distance_matrix, demands, capacity, time_budget_ms=None)
        return routes, {
            "merges_applied": meta["merges_applied"],
            "hook_call_count": 1,
            "candidate_pair_count": len(iu),
            "candidate_gen_ms": 0.0,
            "hook_ms": 0.0,
            "merge_ms": 0.0,
            "postprocess_ms": 0.0,
            "budget_exhausted": False,
            "stop_reason": "completed",
            "merge_sequence": [[1, 2]],  # Always identical regardless of prefer_A vs prefer_B!
            "pre_postprocess_routes": routes,
        }

    # Test Gate 4 bypass detection via an in-process mock evaluator simulating a hollow template
    class _BypassEval(DynamicSubprocessEvaluator):
        def evaluate(self, *, template_id, template_version, hook_code, instances, capture_merge_sequence=False, **kw):
            records = []
            for inst in instances:
                matrix, demands, capacity = prepare_instance_arrays(inst)
                routes, meta = _bypass_runner(matrix, demands, capacity, None)
                ver = verify_cvrp_solution(inst, routes)
                records.append({
                    "instance_id": inst["instance_id"],
                    "valid": ver["valid"],
                    "tour_length": ver["tour_length"],
                    "outcome_class": "completed",
                    "hook_call_count": 1,
                    "merge_sequence": meta["merge_sequence"] if capture_merge_sequence else None,
                    "pre_postprocess_routes": meta["pre_postprocess_routes"] if capture_merge_sequence else None,
                    "solve_ms": 0.1,
                })
            return {"valid": True, "objective": records[0]["tour_length"], "records": records}

    bypass_validator = InterfaceValidator(evaluator=_BypassEval(candidate_timeout_s=5.0))
    r4 = bypass_validator.validate(base)
    assert r4.passed is False
    assert any(f.gate_id == 4 and f.error_code == "hook_not_causally_effective" for f in r4.failures)

    # Gate 5 / subprocess timeout adversarial: infinite loop killed cleanly by outer timeout
    inf_loop_code = (
        "import numpy as np\n\n"
        "def score_merge_static(distance_matrix, demands, capacity, i_idx, j_idx):\n"
        "    x = 0\n"
        "    while True:\n"
        "        x += 1\n"
        "    return np.zeros(i_idx.shape[0])\n"
    )
    fast_eval = DynamicSubprocessEvaluator(candidate_timeout_s=1.2)
    r5_resp = fast_eval.evaluate(
        template_id="cvrp_parallel_merge_static",
        template_version="v1",
        hook_code=inf_loop_code,
        instances=[build_gate4_dual_action_instance()],
        instance_time_budget_ms=500.0,
    )
    assert r5_resp["valid"] is False
    assert r5_resp["error_code"] == "candidate_timeout"


# ---------------------------------------------------------------------------
# 2A-4 & 2A-5: End-to-end DynamicInterfaceProblem -> EoH -> Frozen Bundle -> Dashboard
# ---------------------------------------------------------------------------

def test_2a4_and_2a5_eoh_mock_to_workbench_bundle_and_dashboard(tmp_path: Path) -> None:
    design = build_classic_cw_static_design(design_id="test_2a4_mock_l2a", postprocess_mode="none")
    eoh_out = tmp_path / "eoh_mock_run"
    eoh_res = run_dynamic_eoh_evolution(
        design=design,
        output_dir=eoh_out,
        suite_id="cvrp_dev_hetero_24",
        split="dev_train",
        max_instances=6,
        pop_size=2,
        n_pop=1,
        max_sample_nums=3,
        operators=("m1",),
        search_seed=20261122,
        solver_id="m2_eoh_test_mock_v1",
        display_name="M2 EoH Test Mock (v1)",
        mode="mock",
    )
    assert eoh_res["ok"] is True
    assert eoh_res["evaluations_valid"] >= 2
    assert eoh_res["evolved_count"] >= 1
    assert Path(eoh_res["frozen_manifest_path"]).is_file()
    assert Path(eoh_res["resource_ledger_path"]).is_file()

    frozen = FrozenInterfaceSolver.from_dict(eoh_res["frozen_solver"])
    tpl = get_template_spec(frozen.template_id, frozen.template_version)
    assert frozen.template_source_sha256 == tpl.template_source_sha256
    assert frozen.hook_code_sha256 == sha256_text(frozen.hook_code)
    assert frozen.design_sha256 == design.design_sha256

    # Hash tamper guardrail on unified frozen execution adapter
    tampered = FrozenInterfaceSolver.from_dict({
        **frozen.to_dict(),
        "template_source_sha256": "0" * 64,
    })
    with pytest.raises(ValueError, match="template_source_sha256_mismatch"):
        evaluate_frozen_interface_solver(tampered, build_gate4_dual_action_instance())

    # 2A-5: Workbench frozen bundle + existing frontend/build_dashboard.py
    bundle_dir = tmp_path / "wb_bundle"
    wb_res = run_frozen_workbench_bundle(
        bundle_dir,
        frozen_solvers=[frozen],
        reference_solver_ids=("s2_r5_spiral", "i605_cvrp_c1_tworegime", "cw_parallel_merge"),
        suite_specs=(("cvrp_dev_hetero_24", "dev_train"),),
        budget_id="standard_500ms",
        time_budget_ms=500.0,
    )
    assert wb_res["ok"] is True
    assert wb_res["record_count"] == 24 * 4
    assert frozen.solver_id in wb_res["algorithms"]

    dash_dir = tmp_path / "dashboard"
    dash_res = build_dashboard(
        bundle_dir=bundle_dir,
        workspace_dir=_REPO / "knowledge_workspace",
        output_dir=dash_dir,
        release_id="m2-phase2a-test-500ms",
    )
    assert dash_res["ok"] is True
    assert Path(dash_res["dashboard_html"]).is_file()
    assert (dash_dir / "workbench_data" / "core.js").is_file()
    assert (dash_dir / "workbench_data" / "suite_cvrp_dev_hetero_24.js").is_file()
    core_text = (dash_dir / "workbench_data" / "core.js").read_text(encoding="utf-8")
    assert frozen.solver_id in core_text
    assert "i605_cvrp_c1_tworegime" in core_text
