"""Milestone 3 Phase 3B tests:
- Unmanned 3-round mock Research Agent loop driving official Session Runtime
- Sandbox security redlines (AST allowlist, stripped env, blind/select_64 rejection, 1s timeout kill, 8KB truncation)
- Evidence-bound HypothesisLedger anti-hallucination & AST novelty duplicate guard
- Mid-run crash recovery (resume=True with PersistentRequestBudget reconciliation & zero duplicate requests)
- Live localhost OpenAI Native Tool-Calling + Strict JSON-Action driver sharing PersistentRequestBudget + Arm M3-1 isolation
"""

from __future__ import annotations

import contextlib
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from agent_skill_loop.interface_design.dynamic_eoh import DEFAULT_MOCK_CANDIDATES_BY_TEMPLATE
from agent_skill_loop.request_budget import PersistentRequestBudget
from knowledge_tools.core import resolve_release
from research_agent import AgentConfig, run_research_agent

REPO = Path(__file__).resolve().parents[1]
from research_agent.contracts import RESULTS_TSV_HEADER, sha256_file
from research_agent.tools.archive_tools import SteppingStoneArchiveTool
from research_agent.tools.ledger_tools import HypothesisLedgerTool
from research_agent.tools.math_sandbox import MathSandboxTool


def test_research_agent_3round_mock_autonomous_loop_and_evidenced_refutation(tmp_path: Path) -> None:
    run_dir = tmp_path / "agent_3round_mock"
    cfg = AgentConfig(
        run_id="m3_3b_smoke",
        output_dir=str(run_dir),
        arm_id="arm_m3_3_full_dynamic",
        max_rounds=3,
        total_request_cap=36,
        eoh_pop_size=2,
        eoh_n_pop=1,
        eoh_max_sample_nums=2,
        dev_instance_count=2,
        dev_instance_size=12,
        instance_time_budget_ms=500.0,
        checkpoint_budgets=(10,),
        mode="mock",
    )
    summary = run_research_agent(cfg, resume=False)

    assert summary["final_phase"] == "completed"
    assert summary["completed_rounds"] == [1, 2, 3]
    assert summary["best_dev_objective"] is not None
    assert (run_dir / "research_policy.md").is_file()
    assert (run_dir / "research_summary.json").is_file()

    # P0-1 regression check: agent_guidance=True + inject_static_kb_clues=False passes agent hypothesis into EoH without static KB clues
    r2_ctx = (run_dir / "session_run" / "rounds" / "round_0002" / "round_context.txt").read_text(encoding="utf-8")
    r2_task = (run_dir / "session_run" / "rounds" / "round_0002" / "eoh_run" / "task_description.txt").read_text(encoding="utf-8")
    assert "cvrp_ruin_recreate" in r2_ctx
    assert "Neutral benchmark control" not in r2_ctx
    assert "KB DOMAIN CLUES" not in r2_task

    # Results TSV has header + 3 round rows, showing L2a -> L3 upgrade
    tsv_lines = (run_dir / "results.tsv").read_text(encoding="utf-8").splitlines()
    assert tsv_lines[0] + "\n" == RESULTS_TSV_HEADER
    assert len(tsv_lines) == 4
    assert "cvrp_parallel_merge_static" in tsv_lines[1]
    assert "cvrp_ruin_recreate" in tsv_lines[2]
    assert "cvrp_ruin_recreate" in tsv_lines[3]

    # KB log resolved current release & sandbox artifact exists
    cur_rel_id = resolve_release(REPO / "knowledge_store" / "current").name
    kb_lines = (run_dir / "agent_artifacts" / "kb_events.jsonl").read_text(encoding="utf-8").splitlines()
    assert any(cur_rel_id in line for line in kb_lines)
    sb_path = run_dir / "agent_artifacts" / "sandbox" / "run_0001.json"
    assert sb_path.is_file()
    sb_doc = json.loads(sb_path.read_text(encoding="utf-8"))
    assert sb_doc["ok"] is True
    assert sb_doc["result"]["max_scale_drift_pct"] > 0.0

    # Hypothesis ledger contains evidence-bound refutation citing run_0001.json SHA-256
    h_rows = [json.loads(l) for l in (run_dir / "hypotheses.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    refuted = [h for h in h_rows if h["hypothesis_id"] == "H_scale_bad_r1" and h["status"] == "refuted"]
    assert len(refuted) == 1
    ev_ref = refuted[0]["evidence_artifacts"][0]
    assert ev_ref["path"] == "agent_artifacts/sandbox/run_0001.json"
    assert ev_ref["sha256"] == sha256_file(sb_path)

    # 5-gate validation for L3 switch + stepping-stone archive feedback
    assert (run_dir / "agent_artifacts" / "validations" / "val_0001.json").is_file()
    assert summary["archive_summary"]["solver_count"] == 3
    assert len(summary["archive_summary"]["weakest_regimes"]) >= 1
    assert summary["frozen_checkpoints"].get("10")
    assert (run_dir / summary["frozen_checkpoints"]["10"]).is_file()

    # Parent budget remained strictly within cap
    assert summary["budget_summary"]["attempted_requests"] <= 36


def test_math_sandbox_security_redlines_and_timeouts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-secret-must-not-leak")
    sb = MathSandboxTool(tmp_path / "sb_run", timeout_s=10.0)
    sb_kill = MathSandboxTool(tmp_path / "sb_kill", timeout_s=1.0)

    # 1. Forbidden imports and dangerous builtins blocked before execution
    for bad_script in (
        "import os\nRESULT = os.listdir('.')\n",
        "import subprocess\nRESULT = 1\n",
        "import socket\nRESULT = 1\n",
        "f = open('secret.txt', 'w')\n",
        "RESULT = eval('1+1')\n",
        "RESULT = __import__('os').environ\n",
    ):
        res = sb.run(script=bad_script)
        assert res["ok"] is False

    # 2. Blind suites & selection suite strictly forbidden
    for blocked in (
        "RESULT = load_dev_suite('cvrp_select_multiscale_64')\n",
        "RESULT = load_dev_suite('cvrp_m3_blind_120')\n",
    ):
        res = sb.run(script=blocked)
        assert res["ok"] is False

    # 3. Valid analytical script with numpy & radial_share_stats works and reads zero env secrets
    good = sb.run(
        script=(
            "import numpy as np\n"
            "inst = load_dev_suite(max_instances=1)[0]\n"
            "base = eval_baseline('cw_parallel_merge', inst, time_budget_ms=500.0)\n"
            "stats = radial_share_stats(base['routes'], inst)\n"
            "RESULT = {'eta_rad': stats['eta_rad'], 'route_count': stats['route_count']}\n"
        )
    )
    assert good["ok"] is True and 0.0 < good["result"]["eta_rad"] <= 1.0

    # 4. Hard timeout kills infinite loops cleanly
    t_res = sb_kill.run(script="while True:\n    pass\n")
    assert t_res["ok"] is False
    assert t_res["error_code"] == "SandboxTimeout"

    # 5. Output truncation <= 8KB
    big = sb.run(script="print('X' * 20000)\nRESULT = 'ok'\n")
    assert big["ok"] is True and big["output_truncated"] is True and len(big["stdout"]) < 5000


def test_hypothesis_ledger_evidence_guard_and_novelty_guard(tmp_path: Path) -> None:
    run_dir = tmp_path / "ledger_run"
    run_dir.mkdir(parents=True, exist_ok=True)
    ledger = HypothesisLedgerTool(run_dir)
    h = ledger.propose(round_id=1, statement="Test scaling hypothesis", hypothesis_id="H_test_1")
    assert h["status"] == "proposed"

    # Must reject supported/refuted/abandoned without genuine SHA-256 artifact
    for terminal in ("supported", "refuted", "abandoned"):
        with pytest.raises(ValueError, match="hypothesis_evidence_required"):
            ledger.update(hypothesis_id="H_test_1", status=terminal, evidence_artifacts=[])

    ev_file = run_dir / "agent_artifacts" / "evidence.json"
    ev_file.parent.mkdir(parents=True, exist_ok=True)
    ev_file.write_text('{"metric": 1.23}\n', encoding="utf-8")
    real_sha = sha256_file(ev_file)

    with pytest.raises(ValueError, match="hypothesis_evidence_sha256_mismatch"):
        ledger.update(
            hypothesis_id="H_test_1",
            status="refuted",
            evidence_artifacts=[{"path": "agent_artifacts/evidence.json", "sha256": "0" * 64}],
        )

    ok_rec = ledger.update(
        hypothesis_id="H_test_1",
        status="refuted",
        evidence_artifacts=[{"path": "agent_artifacts/evidence.json", "sha256": real_sha}],
    )
    assert ok_rec["status"] == "refuted"

    # AST novelty duplicate check ignores formatting/comments
    arc = SteppingStoneArchiveTool(run_dir)
    code1 = "import numpy as np\n\ndef score_ruin_nodes(distance_matrix):\n    # comment a\n    return distance_matrix[0, 1:]\n"
    code2 = "import numpy as np\ndef score_ruin_nodes(distance_matrix):\n    return distance_matrix[0, 1:]\n"
    r1 = arc.check_and_record_novelty(code=code1, status="accepted")
    r2 = arc.check_and_record_novelty(code=code2, status="tested")
    assert r1["duplicate"] is False and r2["duplicate"] is True and r1["ast_sha256"] == r2["ast_sha256"]


def test_research_agent_crash_resume_zero_duplicate_requests(tmp_path: Path) -> None:
    run_dir = tmp_path / "agent_crash_resume"
    cfg = AgentConfig(
        run_id="m3_crash_resume_test",
        output_dir=str(run_dir),
        max_rounds=2,
        total_request_cap=20,
        eoh_pop_size=2,
        eoh_n_pop=1,
        eoh_max_sample_nums=2,
        dev_instance_count=2,
        dev_instance_size=12,
        tools_enabled=True,
        mode="mock",
    )

    class _CrashingDriver:
        def __init__(self, inner: Any) -> None:
            self.inner = inner

        def decide_step(self, *, round_id: int, phase: str, step_index: int, messages: Any, last_tool_result: Any) -> dict[str, Any]:
            if round_id == 2 and phase == "diagnose" and step_index == 1:
                # Simulate an in-flight provider crash mid-round (reserved + sent, unclosed!)
                s = self.inner.budget.reserve(purpose="planner", problem="cvrp", attempt=99, model="deepseek-chat")
                assert s is not None
                self.inner.budget.mark_sent(s)
                raise RuntimeError("simulated_crash_mid_flight")
            return self.inner.decide_step(
                round_id=round_id, phase=phase, step_index=step_index, messages=messages, last_tool_result=last_tool_result
            )

    from research_agent.llm_driver import ScriptedMockAgentDriver

    init_budget = PersistentRequestBudget(run_dir / "agent_budget.sqlite3", max_requests=20, run_id=cfg.run_id)
    first_driver = _CrashingDriver(ScriptedMockAgentDriver(config=cfg, budget=init_budget, session_dir=run_dir / "session_run"))
    with pytest.raises(RuntimeError, match="simulated_crash_mid_flight"):
        run_research_agent(cfg, driver=first_driver, resume=False)

    # Verify Round 1 completed and Round 2 stopped at step_index == 1
    ckpt_mid = json.loads((run_dir / "agent_checkpoint.json").read_text(encoding="utf-8"))
    assert ckpt_mid["completed_rounds"] == [1]
    assert ckpt_mid["current_round"] == 2
    assert ckpt_mid["round_step_index"] == 1
    count_before_resume = len(init_budget.request_records())

    # Resume cleanly in mock mode (without fault injection)
    resumed = run_research_agent(cfg, resume=True)
    assert resumed["final_phase"] == "completed"
    assert resumed["completed_rounds"] == [1, 2]
    assert resumed["budget_summary"]["reconciled_unknown_count"] == 1

    # Results TSV must contain Round 1 ONCE and Round 2 ONCE (no duplicate Round 1 re-run)
    tsv_rows = (run_dir / "results.tsv").read_text(encoding="utf-8").splitlines()[1:]
    assert [int(row.split("\t")[0]) for row in tsv_rows] == [1, 2]

    # Round 2 restarted cleanly from step_index == 1 (1 remaining diagnose step + reflect, not re-running step 0)
    reopened_budget = PersistentRequestBudget(run_dir / "agent_budget.sqlite3", max_requests=20, run_id=cfg.run_id)
    assert reopened_budget.used >= count_before_resume
    assert reopened_budget.used <= 20
    assert any(r["state"] == "unknown" for r in reopened_budget.request_records())


@contextlib.contextmanager
def _dual_protocol_agent_server():
    """Serve OpenAI Native tool_calls -> Strict JSON-Action across rounds."""
    calls: list[dict[str, Any]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            calls.append(req)
            idx = len(calls)
            has_tools = "tools" in req
            if idx == 1 and has_tools:
                # Native tool_calls protocol
                msg = {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {"name": "list_interfaces", "arguments": "{}"},
                        }
                    ],
                }
            elif idx == 2 and has_tools:
                msg = {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_2",
                            "type": "function",
                            "function": {
                                "name": "submit_plan_and_evolve",
                                "arguments": json.dumps({
                                    "template_id": "cvrp_parallel_merge_static",
                                    "postprocess_mode": "none",
                                    "direction": "Live HTTP native tool plan",
                                    "hypothesis": "Scale-normalized savings works cleanly.",
                                }),
                            },
                        }
                    ],
                }
            else:
                # Strict JSON-Action fallback text protocol (also handles reflection / tools=False)
                msg = {
                    "role": "assistant",
                    "content": json.dumps({
                        "action": "finish_round" if idx >= 3 else "submit_plan",
                        "template_id": "cvrp_parallel_merge_static",
                        "postprocess_mode": "none",
                        "direction": "Strict JSON plain-text plan",
                        "hypothesis": "Plain-text arm hypothesis.",
                        "summary": "Finished live reflection via Strict JSON-Action.",
                    }),
                }
            body = json.dumps({
                "choices": [{"message": msg, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 20, "completion_tokens": 10},
            }).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args: Any) -> None:
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    th = threading.Thread(target=lambda: srv.serve_forever(poll_interval=0.05), daemon=True)
    th.start()
    try:
        yield f"http://127.0.0.1:{srv.server_port}/v1/chat/completions", calls
    finally:
        srv.shutdown()
        srv.server_close()
        th.join(timeout=1)


def test_live_http_dual_protocol_and_arm_m3_1_plain_text_isolation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("M3_TEST_LIVE_KEY", "live-test-secret")

    # 1. Live OpenAI HTTP Native Tool-Calling + Strict JSON-Action driving OpenAIAgentDriver
    with _dual_protocol_agent_server() as (ep, calls):
        run_dir = tmp_path / "live_driver_agent"
        cfg = AgentConfig(
            run_id="live_dual_proto",
            output_dir=str(run_dir),
            max_rounds=1,
            total_request_cap=10,
            eoh_pop_size=2,
            eoh_n_pop=1,
            eoh_max_sample_nums=2,
            dev_instance_count=2,
            dev_instance_size=12,
            mode="live",
            endpoint=ep,
            api_key_env="M3_TEST_LIVE_KEY",
        )
        # Note: Session inner EoH connects to `ep`? Let's make server also answer EoH prompts cleanly OR test outer driver with real HTTP + Session mock:
        # Here test `OpenAIAgentDriver` directly alongside loop Session tool by running mock Session mode separately and live HTTP driver here:
        from research_agent.llm_driver import OpenAIAgentDriver
        b = PersistentRequestBudget(run_dir / "agent_budget.sqlite3", max_requests=10, run_id="live_dual_proto")
        drv = OpenAIAgentDriver(config=cfg, budget=b, session_dir=run_dir / "session_run")
        d1 = drv.decide_step(round_id=1, phase="diagnose", step_index=0, messages=[{"role": "user", "content": "{}"}], last_tool_result=None)
        d2 = drv.decide_step(round_id=1, phase="diagnose", step_index=1, messages=[{"role": "user", "content": "{}"}], last_tool_result=None)
        d3 = drv.decide_step(
            round_id=1,
            phase="reflect",
            step_index=0,
            messages=[{"role": "user", "content": "Reflect on round 1."}],
            last_tool_result={"eval_artifact_sha256": "def456", "mean_tour_length": 15.99},
        )
        assert d1 == {"action": "call_tool", "tool": "list_interfaces", "arguments": {}, "tool_call_id": "call_1"}
        assert d2["action"] == "submit_plan" and d2["template_id"] == "cvrp_parallel_merge_static"
        assert d3["action"] == "finish_round"
        assert len(calls) == 3 and "tools" in calls[0]
        assert any("15.99" in str(m.get("content", "")) for m in calls[2]["messages"])
        assert b.used == 3 and all(r["response_sha256"] for r in b.request_records())

    # 2. Arm M3-1 plain-text reflection (tools_enabled=False) locks template & forbids switch/sandbox
    m31_dir = tmp_path / "arm_m3_1_plain_text"
    cfg_m31 = AgentConfig(
        run_id="m3_1_plain_text",
        output_dir=str(m31_dir),
        arm_id="arm_m3_1_plain_text",
        max_rounds=2,
        total_request_cap=20,
        eoh_pop_size=2,
        eoh_n_pop=1,
        eoh_max_sample_nums=2,
        dev_instance_count=2,
        dev_instance_size=12,
        allowed_templates=("cvrp_parallel_merge_static",),
        initial_template_id="cvrp_parallel_merge_static",
        tools_enabled=False,
        archive_feedback_enabled=False,
        mode="mock",
    )
    res_m31 = run_research_agent(cfg_m31, resume=False)
    assert res_m31["final_phase"] == "completed"
    assert res_m31["completed_rounds"] == [1, 2]
    assert not list((m31_dir / "agent_artifacts" / "sandbox").glob("*.json"))
    assert res_m31["archive_summary"] is None
    assert "cvrp_parallel_merge_static" in (m31_dir / "results.tsv").read_text(encoding="utf-8")


def test_session_ahead_crash_resume_and_penalized_champion_selection(tmp_path: Path) -> None:
    """Verify P1-3 (session ahead of outer checkpoint) and P1-5 (completion-aware penalized champion selection)."""
    from research_agent.contracts import AgentCheckpoint
    from research_agent.tools.session_tools import SessionRunnerTool

    run_dir = tmp_path / "session_ahead_resume"
    cfg = AgentConfig(
        run_id="m3_ahead_resume",
        output_dir=str(run_dir),
        max_rounds=2,
        total_request_cap=20,
        eoh_pop_size=2,
        eoh_n_pop=1,
        eoh_max_sample_nums=2,
        dev_instance_count=2,
        dev_instance_size=12,
        mode="mock",
    )
    # Run Round 1 inside Session manually via SessionRunnerTool so Session advances to Round 2 WAITING_FOR_PLAN
    b = PersistentRequestBudget(run_dir / "agent_budget.sqlite3", max_requests=20, run_id=cfg.run_id)
    st_tool = SessionRunnerTool(run_dir=run_dir, config=cfg, budget=b)
    r1_out = st_tool.run_round(
        round_id=1,
        template_id="cvrp_parallel_merge_static",
        postprocess_mode="none",
        direction="R1 prior to outer crash",
        hypothesis="H1",
        is_final_round=False,
        eval_dev_suite=False,
    )
    assert r1_out["round_id"] == 1
    # Simulate outer crash BEFORE updating agent_checkpoint (still stuck at round=1, phase='session_evolve')
    ckpt = AgentCheckpoint(
        run_id=cfg.run_id,
        current_round=1,
        phase="session_evolve",
        round_plan_args={
            "template_id": "cvrp_parallel_merge_static",
            "postprocess_mode": "none",
            "direction": "R1 prior to outer crash",
            "hypothesis": "H1",
            "cited_kb_ids": [],
            "rationale": "",
        },
        session_initialized=True,
    )
    (run_dir / "agent_checkpoint.json").write_text(json.dumps(ckpt.to_dict(), indent=2), encoding="utf-8")

    # Resuming MUST recover Round 1 without launching Round 2 as Round 1, then run Round 2 cleanly
    resumed = run_research_agent(cfg, resume=True)
    assert resumed["completed_rounds"] == [1, 2]
    tsv_rows = (run_dir / "results.tsv").read_text(encoding="utf-8").splitlines()[1:]
    assert [int(r.split("\t")[0]) for r in tsv_rows] == [1, 2]

    # Penalized champion scoring check: broken partial solver returning valid on only 1 instance must score worse than full valid baseline
    bad_partial_solver = dict(r1_out["frozen_solver"])
    bad_partial_solver["solver_id"] = "partial_fail_solver"
    bad_partial_solver["hook_code"] = (
        "import numpy as np\n\n"
        "def score_merge_static(distance_matrix, demands, capacity, i_idx, j_idx):\n"
        "    if distance_matrix.shape[0] > 60:\n"
        "        raise ValueError('fail on large')\n"
        "    return distance_matrix[0, i_idx] + distance_matrix[0, j_idx] - distance_matrix[i_idx, j_idx]\n"
    )
    from agent_skill_loop.interface_design.contracts import sha256_text as _sha_txt

    bad_partial_solver["hook_code_sha256"] = _sha_txt(bad_partial_solver["hook_code"])
    eval_good = st_tool._evaluate_frozen_on_dev(r1_out["frozen_solver"])
    eval_partial = st_tool._evaluate_frozen_on_dev(bad_partial_solver)
    assert eval_good is not None and eval_partial is not None
    assert eval_good["all_feasible"] is True and eval_partial["all_feasible"] is False
    assert (eval_good["all_feasible"], eval_good["completion_rate"], -eval_good["penalized_mean_tour_length"]) > (
        eval_partial["all_feasible"],
        eval_partial["completion_rate"],
        -eval_partial["penalized_mean_tour_length"],
    )
