from __future__ import annotations

import json

import pytest

from agent_skill_loop.client import AuthFailTransport, FixtureTransport, ProviderFailure, UsageReceipt
from agent_skill_loop.contracts import DEFAULT_SEED
from agent_skill_loop.journal import verify_journal
from agent_skill_loop.loop import AgentLoop, prepare_output
from agent_skill_loop.problems.cvrp import BASELINE_CODE, build_suite
from agent_skill_loop.skill_store import load_skill
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
    assert (out / "exported_skill" / "ref.json").is_file()
    assert not (out / "exported_skill" / "skill.json").exists()
    assert load_skill(out / "exported_skill").code
    assert "baseline" not in summary.exported_skill_ids
    prompts = transport.prompts
    assert len(prompts) == 3
    assert "INCUMBENT:" not in prompts[0]
    assert "LAST CANDIDATE:" not in prompts[0]
    assert "INCUMBENT:" in prompts[1]
    assert "LAST CANDIDATE:" in prompts[1]
    assert "argmax" in prompts[1]
    assert "argmin" in prompts[1]
    assert "error_code:" in prompts[2]
    assert (out / "report.md").is_file()
    assert summary.best_generated_version_id is not None
    assert summary.feedback_then_regenerated is True
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
    assert not (out / "exported_skill" / "ref.json").exists()
    assert "error_code:" in transport.prompts[1]


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
    assert "error_code: generation_parse_error" in transport.prompts[1]
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
    assert "LAST CANDIDATE:" in transport.prompts[1]
    assert "accept_reason:" in transport.prompts[1]
    assert "delta_vs_incumbent:" in transport.prompts[1]
    assert "argmax" in transport.prompts[1]
    assert "argmin" in transport.prompts[1]
    assert BASELINE_CODE.strip() in transport.prompts[1]
    results = _attempt_results(out)
    assert results[0]["accepted_as_incumbent"] is False
    assert results[0]["evaluation"]["valid"] is True
    last_obj = results[0]["evaluation"]["objective"]
    assert last_obj is not None and last_obj > 10
    assert "LAST CANDIDATE:" in transport.prompts[1]


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


def _started_events(output_dir):
    events = [
        json.loads(line)
        for line in (output_dir / "run" / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    return [event["payload"] for event in events if event["kind"] == "attempt_started"]


def test_i1_has_no_parent_and_m1_points_at_failed_attempt(tmp_path):
    out = tmp_path / "lineage"
    out.mkdir()
    transport = FixtureTransport([invalid_response(), valid_response()])
    summary = AgentLoop(out, transport=transport, candidate_attempts=2, max_llm_requests=2).run()
    started = _started_events(out)
    assert started[0]["operator"] == "i1"
    assert started[0]["parent_version_id"] is None
    assert started[1]["operator"] == "m1"
    assert started[1]["parent_version_id"] is None
    assert started[1]["repair_of_attempt_id"] == 1
    assert started[1]["feedback_attempt_id"] == 1
    assert started[1]["edit_target"] == "failed_code"
    assert summary.feedback_consumed_count == 1
    assert "error_detail:" in transport.prompts[1] or "error_code:" in transport.prompts[1]


def test_worse_generated_does_not_overwrite_best_export(tmp_path):
    out = tmp_path / "export_best"
    out.mkdir()
    nn = BASELINE_CODE.replace(
        "return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]",
        "idx = np.argmin(distance_matrix[current_node][unvisited_nodes])\n    return unvisited_nodes[idx]",
    )
    better = "{Nearest neighbor with named index}\n```python\n" + nn.strip() + "\n```\n"
    transport = FixtureTransport([better, valid_response()])
    summary = AgentLoop(out, transport=transport, candidate_attempts=2, max_llm_requests=2).run()
    assert summary.best_generated_version_id == "generated_1"
    assert summary.exported_skill_ids == ["generated_1"]
    exported = load_skill(out / "exported_skill").code
    assert "argmin" in exported
    assert (out / "skills" / "generated_1" / "code.py").is_file()
    assert json.loads((out / "exported_skill" / "ref.json").read_text(encoding="utf-8"))["skill_dir"] == "skills/generated_1"
    assert summary.incumbent_is_generated is False or summary.incumbent_version_id in {"baseline", "generated_1"}


def test_stagnation_rule_on_third_e1(tmp_path):
    out = tmp_path / "stagnate"
    out.mkdir()
    transport = FixtureTransport([valid_response(), valid_response(), valid_response(), valid_response()])
    AgentLoop(out, transport=transport, candidate_attempts=4, max_llm_requests=4).run()
    started = _started_events(out)
    assert started[0]["operator"] == "i1"
    assert started[1]["operator"] == "e1"
    assert started[2]["operator"] == "e1"
    assert started[3]["operator"] == "e1"
    assert started[3]["structural_explore"] is True
    assert "STAGNATION:" in transport.prompts[3]


def test_explicit_parent_continue_re_evaluates(tmp_path):
    first = tmp_path / "first"
    first.mkdir()
    AgentLoop(first, transport=FixtureTransport([valid_response()]), candidate_attempts=1, max_llm_requests=1).run()
    parent = load_skill(first / "exported_skill")
    second = tmp_path / "second"
    second.mkdir()
    transport = FixtureTransport([valid_response()])
    summary = AgentLoop(
        second,
        transport=transport,
        parent_skill=parent,
        candidate_attempts=1,
        max_llm_requests=1,
    ).run()
    started = _started_events(second)
    assert started[0]["operator"] == "e1"
    assert "INCUMBENT:" in transport.prompts[0]
    assert parent.description not in transport.prompts[0]
    assert (second / "skills" / "parent_reloaded" / "skill.json").is_file()
    assert summary.solver_calls >= 2


def test_invalid_parent_is_input_failure(tmp_path):
    from agent_skill_loop.skill_store import make_skill

    suite = build_suite(DEFAULT_SEED, count=3, size=20)
    bad = make_skill(
        version_id="bad_parent",
        code="def select_next_node(*args):\n    return 'nope'\n",
        suite_hash=suite["content_hash"],
        valid=True,
        mean_objective=1.0,
        instance_objectives=(1.0, 1.0, 1.0),
        parent_version_id=None,
        source_attempt_id=1,
        problem="cvrp_construct",
        entrypoint="select_next_node",
    )
    out = tmp_path / "bad_parent_run"
    out.mkdir()
    summary = AgentLoop(out, transport=FixtureTransport([valid_response()]), parent_skill=bad).run()
    assert summary.status == "parent_invalid"
    assert summary.loop_completed is False
    assert summary.stop_reason == "invalid_parent"
