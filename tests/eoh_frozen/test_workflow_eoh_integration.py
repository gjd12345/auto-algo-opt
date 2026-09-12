from __future__ import annotations

import json
import os
import ast

import pytest

pytest.importorskip("eoh")

from eoh_frozen.smoke import fixture_provider
from agent_skill_loop.memory import MemoryAPI
from agent_skill_loop.workflow import WorkflowRunner


def test_workflow_runs_official_eoh_as_the_only_execute_engine(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKFLOW_FIXTURE_KEY", "fixture")

    def plan_request(prompt, **kwargs):
        payload = json.loads(prompt)
        return json.dumps({
            "round_id": payload["round_id"],
            "direction": "保持合法性并调整候选排序",
            "operations": [{"type": "replace", "target": "tie_break", "mechanism": "相对距离"}],
            "preserve": "容量约束和接口返回值",
            "feedback_basis": payload.get("feedback_reference"),
            "memory_basis": [],
            "hypothesis": "unproven",
        })

    def evaluate_request(prompt, **kwargs):
        return json.dumps({
            "plan_alignment": "aligned",
            "observations": ["读取了确定性评测摘要"],
            "causal_claim": "unproven",
            "memory_action": {"kind": "disabled"},
        })

    with fixture_provider("cvrp_construct") as (endpoint, prompts):
        result = WorkflowRunner(
            tmp_path / "workflow", model="fixture", endpoint=endpoint,
            api_key_env="WORKFLOW_FIXTURE_KEY", max_rounds=2, max_requests=14,
            count=1, size=6, pop_size=2, n_pop=1, max_sample_nums=1,
            plan_request=plan_request, evaluate_request=evaluate_request,
        ).run()

    assert result["status"] == "completed"
    assert len(result["rounds"]) == 2
    round_summary = result["rounds"][0]
    assert round_summary["status"] == "round_finished"
    eoh_summary = round_summary["eoh"]
    assert eoh_summary["search"] == "official_eoh"
    assert eoh_summary["http_requests"] > 0
    assert sum(item["eoh"]["http_requests"] for item in result["rounds"]) == len(prompts)
    assert (tmp_path / "workflow/rounds/round_0001/eoh_run/exported_skill/ref.json").is_file()
    config = json.loads((tmp_path / "workflow/rounds/round_0001/eoh_run/config_frozen.json").read_text())
    assert config["context_mode"] == "round"
    assert (tmp_path / "workflow/rounds/round_0001/plan.json").is_file()
    assert (tmp_path / "workflow/rounds/round_0001/evaluate.json").is_file()
    second_config = json.loads((tmp_path / "workflow/rounds/round_0002/eoh_run/worker_config.json").read_text(encoding="utf-8"))
    assert second_config["use_seed"] is True


def test_real_roles_select_and_consume_memory_body_around_official_eoh(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKFLOW_ROLE_FIXTURE_KEY", "fixture")
    spec = __import__("agent_skill_loop.problems.base", fromlist=["get_problem"]).get_problem("cvrp_construct")
    provider_calls: list[dict] = []

    def responder(prompt: str, call_index: int):
        try:
            payload = json.loads(prompt)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict) and payload.get("role") == "plan":
            provider_calls.append(payload)
            if payload.get("mode") == "select_memory":
                memory = payload.get("memory") or []
                return 200, json.dumps({"memory_refs": [memory[0]["reference"]] if memory else []})
            feedback = payload.get("feedback_reference")
            selected = payload.get("selected_memory") or []
            return 200, json.dumps({
                "round_id": payload["round_id"],
                "direction": "消费评测反馈后调整候选排序",
                "operations": [{"type": "replace", "target": "tie_break", "mechanism": "优先剩余容量"}],
                "preserve": "问题接口和评测器",
                "feedback_basis": feedback,
                "memory_basis": [item["reference"] for item in selected],
                "reference_skill_ref": None,
                "hypothesis": "仅作待验证假设",
            })
        if isinstance(payload, dict) and payload.get("role") == "evaluate":
            provider_calls.append(payload)
            round_id = payload["plan"]["round_id"]
            action = {"kind": "insight", "name": "role-body-consumption", "description": "角色正文消费证据", "project": "cvrp_construct", "scene": "EOH generated candidate evaluation for suite abc17e...", "body": "正文应先被角色选读。\n\n**Why:** fixture。\n\n**How to apply:** 仅作为下一轮方向参考。"} if round_id == 1 else {"kind": "none"}
            return 200, json.dumps({"plan_alignment": "unknown", "observations": ["读取了可信评测事实"], "causal_claim": "unknown", "memory_action": action})
        tree = ast.parse(spec.baseline_code)
        fn = next(node for node in tree.body if isinstance(node, ast.FunctionDef))
        fn.body.insert(0, ast.parse(f"fixture_variant = {call_index}").body[0])
        code = ast.unparse(ast.fix_missing_locations(tree))
        return 200, "2" if prompt == "1+1=?" else "{fixture}\n```python\n" + code + "\n```"

    with fixture_provider("cvrp_construct", responder=responder) as (endpoint, _prompts):
        result = WorkflowRunner(
            tmp_path / "workflow", model="fixture", endpoint=endpoint,
            api_key_env="WORKFLOW_ROLE_FIXTURE_KEY", max_rounds=2, max_requests=24,
            count=1, size=6, pop_size=2, n_pop=1, max_sample_nums=1,
            memory=MemoryAPI(tmp_path / "memory_store"),
        ).run()

    assert result["status"] == "completed"
    assert any(item.get("role") == "plan" and item.get("mode") == "select_memory" for item in provider_calls)
    round_two = tmp_path / "workflow/rounds/round_0002"
    assert (round_two / "memory_consumed.json").is_file()
    context = (round_two / "round_context.txt").read_text(encoding="utf-8")
    assert "正文应先被角色选读" in context
    prompts = sorted((round_two / "journal/prompts").glob("attempt_*.txt"))
    assert any("selected_memory" in path.read_text(encoding="utf-8") and "正文应先被角色选读" in path.read_text(encoding="utf-8") for path in prompts)
    final_plans = [item for item in provider_calls if item.get("role") == "plan" and item.get("mode") == "final"]
    assert final_plans[1]["feedback_reference"] == {
        "round_id": 1,
        "evaluation_ref": "rounds/round_0001/evaluation_facts.json",
        "suite_hash": result["rounds"][0]["state"]["suite_hash"],
    }
