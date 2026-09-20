import json
import time

import pytest

pytest.importorskip("eoh")

from agent_skill_loop import session_actions as actions, session_runtime as db
from agent_skill_loop.benchmark.pilot import build_co_pilot_manifests
from eoh_frozen.smoke import fixture_provider


def test_g4_fixture_freezes_progress_context_and_phase_budget(tmp_path, monkeypatch):
    monkeypatch.setenv("ITERATION_B_FIXTURE_KEY", "fixture")

    def responder(prompt, index):
        if prompt == "1+1=?":
            return 200, "2"
        expression = "-bins" if index % 2 == 0 else "bins"
        code = f"def priority(item: float, bins: np.ndarray) -> np.ndarray:\n    variant = {index}\n    return {expression}\n"
        return 200, "{Fixture priority}\n```python\n" + code + "```"

    with fixture_provider("obp_online", responder=responder) as (endpoint, _prompts):
        source = tmp_path / "source"
        db.initialize_session(
            output=source, operation_id="source-init", eoh_model="fixture", eoh_endpoint=endpoint,
            eoh_api_key_env="ITERATION_B_FIXTURE_KEY", benchmark_id="eohs_v1", benchmark_profile_name="obp_evolution_mini",
            inheritance_mode="incumbent_only", max_rounds=2, round_budget=4, max_solver_calls=8,
        )
        base = json.loads((source / "config_frozen.json").read_text(encoding="utf-8"))["experiment_manifest"]["document"]
        manifest = build_co_pilot_manifests(base)["groups"]["G4"]["manifest"]
        root = tmp_path / "g4"
        db.initialize_session(
            output=root, operation_id="g4-init", experiment_manifest=manifest,
            eoh_model=manifest["model"], eoh_endpoint=manifest["endpoint_identity"],
            eoh_api_key_env="ITERATION_B_FIXTURE_KEY", memory_store=str(tmp_path / "memory"),
            benchmark_id="eohs_v1", benchmark_profile_name="obp_evolution_mini",
        )
        for round_id in (1, 2):
            state = db.read_state(run=root)
            plan = {
                "round_id": round_id, "direction": "fixture progress contract",
                "operations": [{"type": "preserve", "target": "interface", "mechanism": "preserve"}],
                "preserve": "frozen evaluator", "hypothesis": "fixture only",
                "feedback_basis": state["feedback_basis"], "memory_basis": [],
                "search_intent": {"phase": "exploration" if round_id == 1 else "exploitation"},
            }
            plan_file = tmp_path / f"plan-{round_id}.json"
            plan_file.write_text(json.dumps(plan), encoding="utf-8")
            planned = actions.submit_plan(run=root, operation_id=f"plan-{round_id}", expected_state_version=state["state_version"], file=plan_file)
            context = json.loads((root / f"rounds/round_{round_id:04d}/round_context.txt").read_text(encoding="utf-8").split("\n", 1)[1])
            if round_id == 2:
                assert context["feedback_summary"]["search_progress"]["schema_version"].endswith("search-progress/v1")
            actions.execute(run=root, operation_id=f"execute-{round_id}", expected_state_version=planned["state_version"])
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                state = db.read_state(run=root)
                if state["task"] and state["task"]["state"] == "EXITED":
                    break
                time.sleep(0.1)
            assert state["task"]["state"] == "EXITED"
            collected = actions.collect(run=root, operation_id=f"collect-{round_id}", expected_state_version=state["state_version"])
            facts = actions.read_evaluation(run=root)["result"]
            assert facts["phase_budget"]["policy"]["enforce_subbudgets"] is True
            assert facts["search_progress"]["stagnation"]["status"] in {"insufficient_window", "progress", "stagnated"}
            evaluation_file = tmp_path / f"evaluation-{round_id}.json"
            evaluation_file.write_text(json.dumps({
                "plan_alignment": "aligned", "observations": [{"claim": "fixture evidence", "evidence_refs": [facts["evidence_refs"][0]]}],
                "hypotheses": [],
                "next_search_advice": {"direction": "separate the next phase from the stalled mechanism"},
                "memory_action": {"kind": "none", "reason": "fixture only"},
            }), encoding="utf-8")
            evaluated = actions.submit_evaluation(run=root, operation_id=f"evaluation-{round_id}", expected_state_version=collected["state_version"], file=evaluation_file)
            actions.finish_round(run=root, operation_id=f"finish-{round_id}", expected_state_version=evaluated["state_version"], decision="continue" if round_id == 1 else "complete")
