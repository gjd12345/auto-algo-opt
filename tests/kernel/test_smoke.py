from __future__ import annotations

import json

import pytest

from agent_skill_loop.client import AuthFailTransport, FixtureTransport, ProviderFailure
from agent_skill_loop.contracts import DEFAULT_SEED
from agent_skill_loop.journal import verify_journal
from agent_skill_loop.loop import AgentLoop, prepare_output
from agent_skill_loop.problems.cvrp import build_suite
from tests.kernel.conftest import invalid_response, valid_response


def test_prepare_writes_frozen_suite(tmp_path):
    out = tmp_path / "prep"
    config = prepare_output(out, seed=DEFAULT_SEED, count=3, size=20)
    suite = json.loads((out / "dev_suite.json").read_text(encoding="utf-8"))
    assert config["suite_hash"] == suite["content_hash"]
    assert suite == build_suite(DEFAULT_SEED, count=3, size=20)


def test_smoke_valid_candidate_exports_and_consumes_feedback(tmp_path, canary):
    out = tmp_path / "ok"
    out.mkdir()
    transport = FixtureTransport([valid_response(), invalid_response(), valid_response()])
    summary = AgentLoop(out, transport=transport, execution_mode="fixture", wall_seconds=120).run()
    assert summary.loop_completed is True
    assert summary.execution_mode == "fixture"
    assert summary.generated_valid_candidates >= 1
    assert summary.feedback_consumed_count >= 1
    assert summary.status == "completed_with_valid_candidate"
    assert (out / "exported_skill" / "code.py").is_file()
    assert "baseline" not in summary.exported_skill_ids
    prompts = transport.prompts
    assert len(prompts) == 3
    assert "Dev objective:" not in prompts[0]
    assert "Failed code:" not in prompts[0]
    assert "Dev objective:" in prompts[1]
    assert "Error code:" in prompts[2]
    assert all(canary not in prompt for prompt in prompts)
    assert all("STRATEGY_CARD" not in prompt for prompt in prompts)
    verify_journal(out / "run" / "events.jsonl")
    prompt0 = (out / "run" / "prompts" / "attempt_1.txt").read_text(encoding="utf-8")
    assert prompt0 == prompts[0]


def test_all_invalid_is_no_valid_candidate(tmp_path):
    out = tmp_path / "fail"
    out.mkdir()
    transport = FixtureTransport([invalid_response(), invalid_response(), invalid_response()])
    summary = AgentLoop(out, transport=transport, execution_mode="fixture").run()
    assert summary.loop_completed is True
    assert summary.status == "no_valid_candidate"
    assert summary.generated_valid_candidates == 0
    assert summary.stop_reason == "candidate_limit"
    assert summary.feedback_consumed_count >= 1
    assert not (out / "exported_skill" / "code.py").exists()
    assert "Error code:" in transport.prompts[1]


def test_request_limit_stops(tmp_path):
    out = tmp_path / "req"
    out.mkdir()
    transport = FixtureTransport([valid_response(), valid_response(), valid_response()])
    summary = AgentLoop(out, transport=transport, max_llm_requests=1, candidate_attempts=3).run()
    assert summary.stop_reason == "request_limit"
    assert summary.llm_requests == 1
    assert summary.loop_completed is True


def test_wall_clock_injected_clock(tmp_path):
    out = tmp_path / "wall"
    out.mkdir()
    transport = FixtureTransport([valid_response(), valid_response(), valid_response()])

    class JumpingLoop(AgentLoop):
        def remaining_wall(self) -> float:
            if self.solver_calls >= 1:
                return -1.0
            return super().remaining_wall()

    summary = JumpingLoop(out, transport=transport, wall_seconds=30.0).run()
    assert summary.stop_reason == "wall_time_limit"
    assert summary.loop_completed is True
    assert summary.llm_requests == 0


def test_provider_failed_status(tmp_path):
    out = tmp_path / "auth"
    out.mkdir()
    summary = AgentLoop(out, transport=AuthFailTransport(), execution_mode="fixture").run()
    assert summary.status == "provider_failed"
    assert summary.loop_completed is False
    assert summary.stop_reason == "provider_error"


def test_live_transport_is_not_used_in_kernel(monkeypatch):
    from agent_skill_loop import client as client_mod

    def boom(*args, **kwargs):
        raise AssertionError("urlopen must not be called")

    monkeypatch.setattr(client_mod.urllib.request, "urlopen", boom)
    transport = FixtureTransport([valid_response()])
    transport.request("hello", purpose="generation", problem="cvrp_construct")
    with pytest.raises(ProviderFailure):
        AuthFailTransport().request("hello", purpose="generation", problem="cvrp_construct")
