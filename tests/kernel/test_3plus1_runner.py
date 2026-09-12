from __future__ import annotations

import json

from agent_skill_loop.memory import MemoryAPI
from agent_skill_loop.workflow import WorkflowRunner


def test_runner_consumes_memory_on_next_round_without_second_search_engine(tmp_path):
    observed_memory: list[list[dict]] = []

    def plan_request(prompt, **kwargs):
        payload = json.loads(prompt)
        memory = payload["memory"]
        observed_memory.append(memory)
        if payload.get("mode") == "select_memory":
            return json.dumps({"memory_refs": [item["reference"] for item in memory]})
        return json.dumps({
            "round_id": payload["round_id"],
            "direction": "改变候选排序",
            "operations": [{"type": "replace", "target": "tie_break", "mechanism": "相对距离"}],
            "preserve": "接口和容量约束",
            "feedback_basis": payload.get("feedback_reference"),
            "memory_basis": [item["reference"] for item in payload.get("selected_memory", [])],
            "hypothesis": "仍未证明因果关系",
        })

    def evaluate_request(prompt, **kwargs):
        return json.dumps({
                "plan_alignment": "aligned",
            "observations": ["本轮没有修改确定性事实"],
            "causal_claim": "unproven",
            "memory_action": {
                "kind": "insight",
                "name": "round-feedback",
                "description": "记录一轮 workflow 的反馈消费方式",
                "project": "cvrp_construct",
                "scene": "EOH generated candidate evaluation for suite abc17e...",
                "body": "反馈应进入下一轮计划。\n\n**Why:** fixture runner。\n\n**How to apply:** 只作为方向参考。",
            },
        })

    def execute(**kwargs):
        return {"status": "completed", "http_requests": 0, "suite_hash": "fixture"}

    result = WorkflowRunner(
        tmp_path / "workflow", model="fixture", max_rounds=2, max_requests=4,
        plan_request=plan_request, evaluate_request=evaluate_request, execute=execute,
        memory=MemoryAPI(tmp_path / "memory_store"),
    ).run()
    assert result["status"] == "completed"
    assert len(result["rounds"]) == 2
    assert observed_memory[0] == []
    assert observed_memory[1][0]["reference"] == "cvrp_construct/insight_round-feedback@v0001"
    assert observed_memory[1][0]["scene"] == "select_next_node"
    memory_body = MemoryAPI(tmp_path / "memory_store").read_version(observed_memory[1][0]["reference"])["body"]
    assert "Model-proposed scene label" in memory_body and "suite_hash=" in memory_body
    manifest = json.loads((tmp_path / "workflow/rounds/round_0002/manifest.json").read_text())
    assert manifest["memory_refs"] == ["cvrp_construct/insight_round-feedback@v0001"]
