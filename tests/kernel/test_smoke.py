from __future__ import annotations

import json

import pytest

from agent_skill_loop.client import AuthFailTransport, FixtureTransport, ProviderFailure, UsageReceipt
from agent_skill_loop.contracts import DEFAULT_SEED
from agent_skill_loop.journal import verify_journal
from agent_skill_loop.loop import AgentLoop, prepare_output
from agent_skill_loop.problems.cvrp import BASELINE_CODE, build_suite
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
    assert "Last candidate objective:" in prompts[1]
    assert "argmax" in prompts[1]
    assert "argmin" in prompts[1]
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


PROSE_ONLY_REPLY = (
    "The heuristic should prefer nearby customers with leftover capacity. "
    "I will not write any function."
)


def _attempt_results(output_dir):
    events = [
        json.loads(line)
        for line in (output_dir / "run" / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    return [event["payload"] for event in events if event["kind"] == "attempt_result"]


def test_prose_only_reply_consumes_parse_error(tmp_path):
    out = tmp_path / "prose"
    out.mkdir()
    transport = FixtureTransport([PROSE_ONLY_REPLY, valid_response(), valid_response()])
    summary = AgentLoop(out, transport=transport, execution_mode="fixture").run()
    assert (out / "summary.json").is_file()
    assert summary.loop_completed is True
    assert summary.stop_reason == "candidate_limit"
    results = _attempt_results(out)
    assert results[0]["evaluation"]["error_code"] == "generation_parse_error"
    assert results[0]["evaluation"]["valid"] is False
    assert "Previous model reply (no executable code extracted):" in transport.prompts[1]
    assert "Error code: generation_parse_error" in transport.prompts[1]
    assert PROSE_ONLY_REPLY in transport.prompts[1]
    verify_journal(out / "run" / "events.jsonl")


def test_delayed_auth_failure_is_not_wall_time_limit(tmp_path):
    out = tmp_path / "auth_wall"
    out.mkdir()

    class Clock:
        def __init__(self) -> None:
            self.t = 0.0

        def __call__(self) -> float:
            return self.t

    clock = Clock()

    class DelayedAuthTransport:
        def request(self, prompt, *, purpose, problem, timeout=None):
            clock.t += 20.0
            raise ProviderFailure("provider_auth_invalid", 401, retryable=False)

    summary = AgentLoop(
        out,
        transport=DelayedAuthTransport(),
        execution_mode="fixture",
        wall_seconds=10.0,
        monotonic=clock,
    ).run()
    assert summary.status == "provider_failed"
    assert summary.loop_completed is False
    assert summary.stop_reason == "provider_error"
    payload = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert payload["provider_error_code"] == "provider_auth_invalid"
    assert payload["stop_reason"] != "wall_time_limit"


def test_request_deadline_stops_as_wall_when_wall_is_binding(tmp_path):
    out = tmp_path / "deadline_wall"
    out.mkdir()

    class DeadlineTransport:
        def request(self, prompt, *, purpose, problem, timeout=None):
            raise ProviderFailure("request_deadline", retryable=True)

    summary = AgentLoop(
        out,
        transport=DeadlineTransport(),
        execution_mode="fixture",
        wall_seconds=10.0,
        request_timeout=90.0,
    ).run()
    assert summary.stop_reason == "wall_time_limit"
    assert summary.loop_completed is True
    results = _attempt_results(out)
    assert results[-1]["evaluation"]["error_code"] == "wall_time_limit"


def test_request_deadline_stays_provider_failed_when_request_timeout_binds(tmp_path):
    out = tmp_path / "deadline_req"
    out.mkdir()

    class DeadlineTransport:
        def request(self, prompt, *, purpose, problem, timeout=None):
            raise ProviderFailure("request_deadline", retryable=True)

    summary = AgentLoop(
        out,
        transport=DeadlineTransport(),
        execution_mode="fixture",
        wall_seconds=420.0,
        request_timeout=1.0,
    ).run()
    assert summary.status == "provider_failed"
    assert summary.loop_completed is False
    assert summary.stop_reason == "provider_error"
    payload = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert payload["provider_error_code"] == "request_deadline"


def test_wall_clock_bounds_in_flight_request(tmp_path):
    out = tmp_path / "wall_inflight"
    out.mkdir()

    class Clock:
        def __init__(self) -> None:
            self.t = 0.0

        def __call__(self) -> float:
            return self.t

    clock = Clock()

    class SlowTransport(FixtureTransport):
        def request(self, prompt, *, purpose, problem, timeout=None):
            clock.t += 20.0
            return super().request(prompt, purpose=purpose, problem=problem, timeout=timeout)

    transport = SlowTransport([valid_response(), valid_response(), valid_response()])
    summary = AgentLoop(
        out,
        transport=transport,
        execution_mode="fixture",
        wall_seconds=10.0,
        monotonic=clock,
        candidate_attempts=3,
        max_llm_requests=3,
    ).run()
    assert (out / "summary.json").is_file()
    assert summary.stop_reason == "wall_time_limit"
    assert summary.loop_completed is True
    assert summary.llm_requests == 1
    assert summary.solver_calls == 1
    assert summary.generated_valid_candidates == 0
    assert transport.timeouts and transport.timeouts[0] is not None
    assert transport.timeouts[0] <= 10.0
    results = _attempt_results(out)
    assert len(results) == 1
    assert results[0]["evaluation"]["error_code"] == "wall_time_limit"
    verify_journal(out / "run" / "events.jsonl")


def test_e1_keeps_non_improving_candidate_feedback(tmp_path):
    out = tmp_path / "e1_last"
    out.mkdir()
    transport = FixtureTransport([valid_response(), valid_response()])
    summary = AgentLoop(
        out,
        transport=transport,
        execution_mode="fixture",
        candidate_attempts=2,
        max_llm_requests=2,
    ).run()
    assert summary.loop_completed is True
    assert summary.feedback_consumed_count >= 1
    assert summary.incumbent_version_id == "baseline"
    assert "Last candidate objective:" in transport.prompts[1]
    assert "argmax" in transport.prompts[1]
    assert "argmin" in transport.prompts[1]
    assert BASELINE_CODE.strip() in transport.prompts[1]
    results = _attempt_results(out)
    assert results[0]["accepted_as_incumbent"] is False
    assert results[0]["evaluation"]["valid"] is True
    last_obj = results[0]["evaluation"]["objective"]
    assert last_obj is not None and last_obj > 10
    assert "Last candidate objective:" in transport.prompts[1]


def test_attempt_result_records_usage_nulls(tmp_path):
    out = tmp_path / "usage_null"
    out.mkdir()
    transport = FixtureTransport([valid_response()])
    AgentLoop(out, transport=transport, max_llm_requests=1, candidate_attempts=1).run()
    payload = _attempt_results(out)[0]
    assert "model" in payload
    assert "input_tokens" in payload
    assert "output_tokens" in payload
    assert "request_elapsed_seconds" in payload
    assert payload["model"] is None
    assert payload["input_tokens"] is None
    assert payload["output_tokens"] is None
    assert payload["request_elapsed_seconds"] == 0.0
    raw = (out / "run" / "events.jsonl").read_text(encoding="utf-8")
    assert '"model": null' in raw
    assert '"input_tokens": null' in raw
    assert '"output_tokens": null' in raw


def test_attempt_result_records_known_usage(tmp_path):
    out = tmp_path / "usage_known"
    out.mkdir()

    class TokenTransport(FixtureTransport):
        def request(self, prompt, *, purpose, problem, timeout=None):
            text = super().request(prompt, purpose=purpose, problem=problem, timeout=timeout)
            last = self.usage[-1]
            self.usage[-1] = UsageReceipt(
                purpose=last.purpose,
                problem=last.problem,
                prompt_hash=last.prompt_hash,
                ok=True,
                error_code=None,
                input_tokens=11,
                output_tokens=22,
                elapsed_seconds=1.5,
                network_request=False,
                model="deepseek-v4-flash",
            )
            return text

    transport = TokenTransport([valid_response()])
    AgentLoop(out, transport=transport, max_llm_requests=1, candidate_attempts=1).run()
    payload = _attempt_results(out)[0]
    assert payload["model"] == "deepseek-v4-flash"
    assert payload["input_tokens"] == 11
    assert payload["output_tokens"] == 22
    assert payload["request_elapsed_seconds"] == 1.5
