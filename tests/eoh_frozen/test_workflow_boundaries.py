"""Workflow boundary checks that launch the optional official EoH worker."""

from __future__ import annotations

import json
import time

import pytest

pytest.importorskip("eoh")

from agent_skill_loop.workflow import WorkflowRunner
from eoh_frozen.smoke import fixture_provider


def _plan(prompt: str, **_kwargs: object) -> str:
    payload = json.loads(prompt)
    return json.dumps({
        "round_id": payload["round_id"],
        "direction": "保持接口并调整启发式排序",
        "operations": [{"type": "replace", "target": "tie_break", "mechanism": "按剩余容量排序"}],
        "preserve": "接口、容量约束、确定性评测",
        "feedback_basis": None,
        "memory_basis": [],
        "reference_skill_ref": None,
        "hypothesis": "unknown",
    })


def test_provider_terminal_stops_before_evaluate_and_accounts_request(tmp_path, monkeypatch):
    monkeypatch.setenv("REPAIR_FIXTURE_KEY", "fixture")
    evaluate_calls: list[str] = []

    def evaluate_request(prompt: str, **_kwargs: object) -> str:
        evaluate_calls.append(prompt)
        return json.dumps({
            "plan_alignment": "unknown",
            "observations": [],
            "causal_claim": "unknown",
            "memory_action": {"kind": "disabled"},
        })

    with fixture_provider("cvrp_construct", responder=lambda _prompt, _index: (401, "bad key")) as (endpoint, prompts):
        result = WorkflowRunner(
            tmp_path / "workflow", model="fixture", endpoint=endpoint, api_key_env="REPAIR_FIXTURE_KEY",
            max_rounds=1, max_requests=5, count=1, size=6, pop_size=2, n_pop=1, max_sample_nums=1,
            plan_request=_plan, evaluate_request=evaluate_request,
        ).run()
    assert result["status"] == "provider_failed"
    assert result["request_used"] == len(prompts) == 1
    assert result["rounds"][0]["eoh"]["status"] == "provider_failed"
    assert not evaluate_calls
    skipped = json.loads((tmp_path / "workflow/rounds/round_0001/evaluate_skipped.json").read_text())
    assert skipped["agent_evaluate"] == "skipped" and skipped["memory_decision"] == "not_run"


def test_deadline_reconciles_child_and_writes_recovered_summary(tmp_path, monkeypatch):
    monkeypatch.setenv("REPAIR_SLOW_KEY", "fixture")

    def slow_response(_prompt: str, _index: int):
        time.sleep(4.0)
        return 200, "{}"

    with fixture_provider("cvrp_construct", responder=slow_response) as (endpoint, prompts):
        result = WorkflowRunner(
            tmp_path / "workflow", model="fixture", endpoint=endpoint, api_key_env="REPAIR_SLOW_KEY",
            max_rounds=1, max_requests=5, wall_seconds=3.0, request_timeout=5.0,
            count=1, size=6, pop_size=2, n_pop=1, max_sample_nums=1, plan_request=_plan,
            evaluate_request=lambda **_kwargs: json.dumps({
                "plan_alignment": "unknown", "observations": [], "causal_claim": "unknown",
                "memory_action": {"kind": "disabled"},
            }),
        ).run()
    eoh = result["rounds"][0]["eoh"]
    assert result["status"] == "stopped"
    assert eoh["status"] == "stopped" and eoh["stop_reason"] == "wall_time_limit"
    assert result["request_used"] == len(prompts) == 1
    terminal = result["budget_events"][-1]
    assert terminal["state"] == "killed_unknown"
    assert terminal["input_tokens"] is None and terminal["output_tokens"] is None
    assert (tmp_path / "workflow/rounds/round_0001/eoh_run/summary.json").is_file()
    assert (tmp_path / "workflow/rounds/round_0001/evaluate_skipped.json").is_file()
