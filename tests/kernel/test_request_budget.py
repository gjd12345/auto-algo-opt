from __future__ import annotations

import json
import threading

import pytest

from agent_skill_loop import client as client_mod
from agent_skill_loop.client import LiveTransport, ProviderFailure
from agent_skill_loop.request_budget import BudgetExhausted, RequestBudget
from eoh_frozen.llm_bridge import OpenAIPathBridge

REQUIRED_EVENT_FIELDS = (
    "state",
    "purpose",
    "problem",
    "attempt",
    "index",
    "model",
    "elapsed_seconds",
    "status",
    "error_code",
    "input_tokens",
    "output_tokens",
)


def test_reserve_counts_and_exhausts():
    budget = RequestBudget(2)
    slot1 = budget.reserve(purpose="generation", problem="cvrp_construct")
    slot2 = budget.reserve(purpose="generation", problem="cvrp_construct")
    assert slot1 is not None and slot1.index == 1
    assert slot2 is not None and slot2.index == 2
    assert budget.used == 2
    assert budget.reserve(purpose="generation", problem="cvrp_construct") is None
    assert budget.rejected == 1
    assert budget.used == 2


def test_max_requests_none_never_exhausts():
    budget = RequestBudget(None)
    for _ in range(100):
        assert budget.reserve(purpose="generation", problem="cvrp_construct") is not None
    assert budget.rejected == 0


def test_events_grow_and_carry_all_fields():
    budget = RequestBudget(10)
    slot = budget.reserve(purpose="generation", problem="cvrp_construct", attempt=3, model="m")
    assert slot is not None
    budget.finish(
        slot,
        "complete",
        status=200,
        error_code=None,
        elapsed_seconds=1.5,
        input_tokens=10,
        output_tokens=20,
    )
    assert len(budget.events) == 2
    reserved, complete = budget.events
    for event in (reserved, complete):
        for key in REQUIRED_EVENT_FIELDS:
            assert key in event
    assert reserved["state"] == "reserved"
    assert reserved["index"] == 1
    assert reserved["attempt"] == 3
    assert complete["state"] == "complete"
    assert complete["status"] == 200
    assert complete["input_tokens"] == 10
    assert complete["output_tokens"] == 20
    assert slot.state == "complete"


def test_killed_unknown_tokens_are_none():
    budget = RequestBudget(10)
    slot = budget.reserve(purpose="generation", problem="cvrp_construct")
    assert slot is not None
    budget.finish(slot, "killed_unknown", error_code="request_deadline", input_tokens=0, output_tokens=0)
    event = budget.events[-1]
    assert event["state"] == "killed_unknown"
    assert event["input_tokens"] is None
    assert event["output_tokens"] is None


def test_thread_safety_smoke():
    budget = RequestBudget(100)
    errors: list[BaseException] = []

    def worker() -> None:
        try:
            for _ in range(50):
                slot = budget.reserve(purpose="generation", problem="cvrp_construct")
                assert slot is not None
                budget.finish(slot, "complete", status=200, elapsed_seconds=0.1)
        except BaseException as exc:  # pragma: no cover - failure path
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert not errors
    assert budget.used == 100
    assert len(budget.events) == 200


def _live_transport(budget):
    return LiveTransport(
        "deepseek-v4-flash",
        endpoint="https://opencode.ai/v1/chat/completions",
        api_key_env="TEST_KEY",
        budget=budget,
    )


def test_live_transport_budget_complete_then_exhausted(monkeypatch):
    def fake_post(url, headers, data, timeout, max_bytes=4 * 1024 * 1024):
        return 200, b'{"choices":[{"message":{"content":"ok"}}],"usage":{"prompt_tokens":1,"completion_tokens":2}}'

    monkeypatch.setattr(client_mod, "http_post_with_deadline", fake_post)
    monkeypatch.setenv("TEST_KEY", "x")
    budget = RequestBudget(1)
    transport = _live_transport(budget)
    text = transport.request("prompt", purpose="generation", problem="cvrp_construct")
    assert text == "ok"
    assert budget.used == 1
    assert budget.events[-1]["state"] == "complete"
    assert budget.events[-1]["input_tokens"] == 1
    assert budget.events[-1]["output_tokens"] == 2
    with pytest.raises(ProviderFailure) as raised:
        transport.request("prompt2", purpose="generation", problem="cvrp_construct")
    assert raised.value.error_code == "request_budget_exhausted"
    assert raised.value.retryable is False
    assert budget.rejected == 1


def test_live_transport_budget_killed_unknown(monkeypatch):
    def fake_post(url, headers, data, timeout, max_bytes=4 * 1024 * 1024):
        raise ProviderFailure("request_deadline", retryable=True)

    monkeypatch.setattr(client_mod, "http_post_with_deadline", fake_post)
    monkeypatch.setenv("TEST_KEY", "x")
    budget = RequestBudget(1)
    transport = _live_transport(budget)
    with pytest.raises(ProviderFailure) as raised:
        transport.request("prompt", purpose="generation", problem="cvrp_construct")
    assert raised.value.error_code == "request_deadline"
    assert budget.used == 1
    event = budget.events[-1]
    assert event["state"] == "killed_unknown"
    assert event["input_tokens"] is None
    assert event["output_tokens"] is None


def test_live_transport_no_budget_keeps_behavior(monkeypatch):
    def fake_post(url, headers, data, timeout, max_bytes=4 * 1024 * 1024):
        return 200, b'{"choices":[{"message":{"content":"ok"}}]}'

    monkeypatch.setattr(client_mod, "http_post_with_deadline", fake_post)
    monkeypatch.setenv("TEST_KEY", "x")
    transport = _live_transport(None)
    assert transport.request("prompt", purpose="generation", problem="cvrp_construct") == "ok"


def _bridge(tmp_path, budget, *, wall_seconds=None):
    return OpenAIPathBridge(
        "https://opencode.ai/zen/go/v1/chat/completions",
        "secret-key-123",
        "deepseek-v4-flash",
        budget=budget,
        request_log=tmp_path / "results" / "requests.jsonl",
        wall_seconds=wall_seconds,
    )


def test_bridge_budget_reserve_and_log(monkeypatch, tmp_path):
    budget = RequestBudget(1)
    bridge = _bridge(tmp_path, budget)
    calls = []

    def fake_post(url, headers, data, timeout, *, max_bytes=None):
        calls.append((url, timeout))
        return 200, b'{"choices":[{"message":{"content":"ok"}}],"usage":{"prompt_tokens":1,"completion_tokens":2}}'

    monkeypatch.setattr("eoh_frozen.llm_bridge.http_post_with_deadline", fake_post)
    assert bridge._forward("hello") == "ok"
    assert budget.used == 1
    assert len(calls) == 1
    with pytest.raises(BudgetExhausted):
        bridge._forward("hello again")
    assert budget.rejected == 1
    assert len(calls) == 1  # a rejected call is never forwarded
    log_path = tmp_path / "results" / "requests.jsonl"
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    reserved = json.loads(lines[0])
    complete = json.loads(lines[1])
    assert reserved["state"] == "reserved"
    assert complete["state"] == "complete"
    assert complete["status"] == 200
    assert complete["input_tokens"] == 1
    assert complete["output_tokens"] == 2
    for key in REQUIRED_EVENT_FIELDS:
        assert key in reserved
        assert key in complete
    raw = log_path.read_text(encoding="utf-8")
    assert "secret-key-123" not in raw


def test_bridge_budget_http_error(monkeypatch, tmp_path):
    budget = RequestBudget(2)
    bridge = _bridge(tmp_path, budget)

    def fake_post(url, headers, data, timeout, *, max_bytes=None):
        raise ProviderFailure("provider_auth_invalid", 401)

    monkeypatch.setattr("eoh_frozen.llm_bridge.http_post_with_deadline", fake_post)
    with pytest.raises(ProviderFailure):
        bridge._forward("hello")
    log_path = tmp_path / "results" / "requests.jsonl"
    event = json.loads(log_path.read_text(encoding="utf-8").splitlines()[-1])
    assert event["state"] == "http_error"
    assert event["status"] == 401
    assert event["error_code"] == "provider_auth_invalid"
    assert bridge.last_error == "provider_auth_invalid"


def test_bridge_budget_timeout_is_killed_unknown(monkeypatch, tmp_path):
    budget = RequestBudget(2)
    bridge = _bridge(tmp_path, budget)

    def fake_post(url, headers, data, timeout, *, max_bytes=None):
        raise ProviderFailure("request_deadline", retryable=True)

    monkeypatch.setattr("eoh_frozen.llm_bridge.http_post_with_deadline", fake_post)
    with pytest.raises(ProviderFailure):
        bridge._forward("hello")
    log_path = tmp_path / "results" / "requests.jsonl"
    event = json.loads(log_path.read_text(encoding="utf-8").splitlines()[-1])
    assert event["state"] == "killed_unknown"
    assert event["error_code"] == "request_deadline"
    assert event["input_tokens"] is None
    assert event["output_tokens"] is None


def test_bridge_wall_deadline_refuses_without_outbound(monkeypatch, tmp_path):
    budget = RequestBudget(10)
    bridge = _bridge(tmp_path, budget, wall_seconds=0.0)
    calls = []

    def fake_post(url, headers, data, timeout, *, max_bytes=None):
        calls.append(url)
        return 200, b'{"choices":[{"message":{"content":"ok"}}]}'

    monkeypatch.setattr("eoh_frozen.llm_bridge.http_post_with_deadline", fake_post)
    with pytest.raises(BudgetExhausted):
        bridge._forward("hello")
    assert calls == []
    assert budget.used == 0
    assert bridge.last_error == "wall_time_exhausted"