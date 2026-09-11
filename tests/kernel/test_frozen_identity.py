from __future__ import annotations

import json

from agent_skill_loop import client as client_mod
from agent_skill_loop.client import FixtureTransport, LiveTransport
from agent_skill_loop.contracts import DEFAULT_SEED
from agent_skill_loop.evaluator import evaluator_source_hash
from agent_skill_loop.loop import AgentLoop, prepare_output
from agent_skill_loop.problems.cvrp import BASELINE_CODE
from agent_skill_loop.request_budget import RequestBudget


def test_prepare_config_has_identity_fields(tmp_path):
    out = tmp_path / "prep"
    config = prepare_output(out, seed=DEFAULT_SEED, count=3, size=20)
    assert config["interface_version"] == "v1"
    assert config["entrypoint"] == "select_next_node"
    assert config["evaluator_hash"] == evaluator_source_hash()
    assert config["provider_endpoint"] is None
    assert config["search_policy"]["params"]["stagnation_e1_streak"] == 2
    assert "source_version" in config


def test_fixture_run_config_and_summary_identity(tmp_path):
    from tests.kernel.conftest import valid_response

    out = tmp_path / "run"
    out.mkdir()
    transport = FixtureTransport([valid_response()])
    AgentLoop(out, transport=transport, candidate_attempts=1, max_llm_requests=1).run()
    config = json.loads((out / "config_frozen.json").read_text(encoding="utf-8"))
    assert config["interface_version"] == "v1"
    assert config["evaluator_hash"] == evaluator_source_hash()
    assert config["provider_endpoint"] is None
    assert config["request_budget"] is None
    payload = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert "http_requests" not in payload
    assert "request_rejected" not in payload


def test_live_run_reports_request_budget(tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_KEY", "x")
    body = json.dumps({
        "choices": [{"message": {"content": "```python\n" + BASELINE_CODE + "```"}}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 7},
    }).encode("utf-8")
    monkeypatch.setattr(client_mod, "http_post_with_deadline", lambda *a, **k: (200, body))

    budget = RequestBudget(1)
    transport = LiveTransport(
        "test-model",
        endpoint="https://opencode.ai/v1/chat/completions",
        api_key_env="TEST_KEY",
        budget=budget,
    )
    out = tmp_path / "live"
    out.mkdir()
    AgentLoop(
        out,
        transport=transport,
        execution_mode="live",
        candidate_attempts=1,
        max_llm_requests=1,
    ).run()
    payload = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert payload["http_requests"] == 1
    assert payload["request_rejected"] == 0
    config = json.loads((out / "config_frozen.json").read_text(encoding="utf-8"))
    assert config["request_budget"] == 1
    assert config["provider_endpoint"] == "https://opencode.ai/v1/chat/completions"
    assert config["model"] == "test-model"
