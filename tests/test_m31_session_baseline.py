from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_skill_loop.__main__ import main as cli_main
from agent_skill_loop.cvrp_workbench.suites import BENCHMARK_ID
from agent_skill_loop.interface_design.session_baseline import (
    freeze_session_baseline,
    load_dev_or_public_suite,
    re_eval_session_baseline,
)
from agent_skill_loop.session_runtime import SessionError, initialize_session, read_state
from research_agent.contracts import AgentConfig
from research_agent.loop import run_research_agent


@pytest.mark.parametrize(
    "suite_id,problem_family,template_id,expected_protocol",
    [
        ("cvrp_dev_hetero_24", "cvrp", "cvrp_parallel_merge_static", "cvrp/v1"),
        ("tsp_m31_dev_36", "tsp", "tsp_constructive_step", "tsp/v1"),
        ("obp_m31_dev_36", "obp", "obp_online_priority", "obp_online/v1"),
        ("bpp_m31_dev_36", "bpp", "bpp_offline_reorder_repack", "bpp_offline/v1"),
    ],
)
def test_freeze_and_re_eval_baseline_across_problem_families(
    tmp_path: Path,
    suite_id: str,
    problem_family: str,
    template_id: str,
    expected_protocol: str,
) -> None:
    sess_dir = tmp_path / f"sess_{problem_family}"
    suite_preview = load_dev_or_public_suite(suite_id, split="dev_train", role="interactive_sandbox")
    assert len(suite_preview["instances"]) >= 1

    st = initialize_session(
        output=sess_dir,
        operation_id=f"init_{problem_family}",
        problem=problem_family,
        benchmark_id=BENCHMARK_ID,
        benchmark_profile_name=suite_id,
        eoh_model="mock",
        eoh_endpoint="mock://local",
        max_rounds=1,
    )
    ver = int(st["state_version"])

    frozen = freeze_session_baseline(
        run=sess_dir,
        operation_id=f"freeze_{problem_family}",
        expected_state_version=ver,
        template_id=template_id,
        postprocess_mode="none",
        time_budget_ms=500.0,
        suite_id=suite_id,
    )
    res_f = frozen["result"]
    assert res_f["protocol_id"] == expected_protocol
    assert res_f["completion_rate"] == 1.0
    assert res_f["mean_objective"] is not None
    bl_doc = json.loads((sess_dir / res_f["baseline_ref"]).read_text(encoding="utf-8"))
    assert bl_doc["baseline_eval"]["all_completed"] is True
    ver = int(frozen["state_version"])

    # Idempotent replay with same operation_id + args
    replay = freeze_session_baseline(
        run=sess_dir,
        operation_id=f"freeze_{problem_family}",
        expected_state_version=ver - 1,
        template_id=template_id,
        postprocess_mode="none",
        time_budget_ms=500.0,
        suite_id=suite_id,
    )
    assert replay["result"]["baseline_id"] == res_f["baseline_id"]

    # Re-evaluate in fresh worker via Session action
    reeval = re_eval_session_baseline(
        run=sess_dir,
        operation_id=f"reeval_{problem_family}",
        expected_state_version=ver,
        baseline_id=res_f["baseline_id"],
        suite_id=suite_id,
        protocol_id=expected_protocol,
        time_budget_ms=500.0,
        replicate_id="rep_1",
    )
    res_r = reeval["result"]
    assert res_r["matched_reference"] is True
    assert res_r["all_completed"] is True
    assert res_r["protocol_id"] == expected_protocol
    re_doc = json.loads((sess_dir / res_r["report_ref"]).read_text(encoding="utf-8"))
    assert re_doc["evaluation"]["completion_bitmap"] == bl_doc["baseline_eval"]["completion_bitmap"]
    assert re_doc["evaluation"]["ordered_instance_ids"] == bl_doc["baseline_eval"]["ordered_instance_ids"]


def test_freeze_and_re_eval_cli_and_protocol_mismatch_rejected(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    sess_dir = tmp_path / "sess_obp_cli"
    init = initialize_session(
        output=sess_dir,
        operation_id="init_obp_cli",
        problem="obp",
        benchmark_id=BENCHMARK_ID,
        benchmark_profile_name="obp_m31_dev_36",
        eoh_model="mock",
        eoh_endpoint="mock://local",
        max_rounds=1,
    )
    ver = int(init["state_version"])

    rc1 = cli_main([
        "session",
        "freeze-baseline",
        "--run", str(sess_dir),
        "--operation-id", "cli_freeze_obp",
        "--expected-state-version", str(ver),
        "--template-id", "obp_online_priority",
        "--suite-id", "obp_m31_dev_36",
        "--baseline-id", "bl_obp_online",
    ])
    assert rc1 == 0
    out1 = json.loads(capsys.readouterr().out)
    assert out1["result"]["protocol_id"] == "obp_online/v1"
    ver = int(out1["state_version"])

    # Strictly forbid cross-protocol confusion between Online OBP and Offline BPP
    with pytest.raises(SessionError) as exc_info:
        re_eval_session_baseline(
            run=sess_dir,
            operation_id="bad_proto",
            expected_state_version=ver,
            baseline_id="bl_obp_online",
            protocol_id="bpp_offline/v1",
        )
    assert exc_info.value.code == "PROTOCOL_MISMATCH"

    rc2 = cli_main([
        "session",
        "re-eval-baseline",
        "--run", str(sess_dir),
        "--operation-id", "cli_reeval_obp",
        "--expected-state-version", str(ver),
        "--baseline-id", "bl_obp_online",
        "--protocol-id", "obp_online/v1",
        "--replicate-id", "rep_cli",
    ])
    assert rc2 == 0
    out2 = json.loads(capsys.readouterr().out)
    assert out2["result"]["matched_reference"] is True


def test_tsplib_public_suite_session_baseline_freeze(tmp_path: Path) -> None:
    sess_dir = tmp_path / "sess_tsplib"
    suite = load_dev_or_public_suite("tsp_ext_tsplib_euc2d", split="heldout", role="diagnostic_interactive")
    assert len(suite["instances"]) == 18
    init = initialize_session(
        output=sess_dir,
        operation_id="init_tsplib",
        problem="tsp",
        benchmark_id=BENCHMARK_ID,
        benchmark_profile_name="tsp_m31_dev_36",
        eoh_model="mock",
        eoh_endpoint="mock://local",
        max_rounds=1,
    )
    frozen = freeze_session_baseline(
        run=sess_dir,
        operation_id="freeze_tsplib",
        expected_state_version=int(init["state_version"]),
        template_id="tsp_constructive_step",
        suite_id="tsp_ext_tsplib_euc2d",
        time_budget_ms=500.0,
    )
    bl_doc = json.loads((sess_dir / frozen["result"]["baseline_ref"]).read_text(encoding="utf-8"))
    assert bl_doc["baseline_eval"]["instance_count"] == 18
    assert bl_doc["baseline_eval"]["all_completed"] is True


@pytest.mark.parametrize(
    "problem_family,suite_id,allowed_templates,initial_tpl",
    [
        ("tsp", "tsp_m31_dev_36", ("tsp_constructive_step", "tsp_guided_insertion_2opt"), "tsp_constructive_step"),
        ("obp", "obp_m31_dev_36", ("obp_online_priority",), "obp_online_priority"),
        ("cvrp", "cvrp_dev_hetero_24", ("cvrp_ruin_recreate_dual",), "cvrp_ruin_recreate_dual"),
    ],
)
def test_research_agent_mock_rounds_tsp_obp_and_l3b(
    tmp_path: Path,
    problem_family: str,
    suite_id: str,
    allowed_templates: tuple[str, ...],
    initial_tpl: str,
) -> None:
    out_dir = tmp_path / f"agent_{problem_family}_{initial_tpl}"
    cfg = AgentConfig(
        run_id=f"mock_{problem_family}_{initial_tpl}",
        output_dir=str(out_dir),
        problem_family=problem_family,
        arm_id="arm_mock_m31_m32",
        max_rounds=2,
        total_request_cap=24,
        eoh_pop_size=2,
        eoh_n_pop=1,
        eoh_max_sample_nums=4,
        instance_time_budget_ms=500.0,
        allowed_templates=allowed_templates,
        allowed_postprocess_modes=("none",),
        initial_template_id=initial_tpl,
        initial_postprocess_mode="none",
        dev_suite_id=suite_id,
        dev_split="dev_train",
        use_benchmark_dev_suite=True,
        checkpoint_budgets=(12,),
        mode="mock",
    )
    summary = run_research_agent(cfg, resume=False)
    assert summary["final_phase"] == "completed"
    assert len(summary["completed_rounds"]) == 2
    assert summary["best_dev_objective"] is not None
    assert (out_dir / "research_summary.json").is_file()
    st = read_state(run=out_dir / "session_run")
    assert st["round_id"] == 2
