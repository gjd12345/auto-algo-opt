from __future__ import annotations

import pytest

from agent_skill_loop.contracts import choose_operator
from agent_skill_loop.generator import build_prompt
from agent_skill_loop.problems.cvrp import BASELINE_CODE, TASK_DESCRIPTION


def test_operator_state_machine():
    assert choose_operator(attempts_done=0, has_explicit_parent=False, last_valid=None) == "i1"
    assert choose_operator(attempts_done=0, has_explicit_parent=True, last_valid=None) == "e1"
    assert choose_operator(attempts_done=1, has_explicit_parent=False, last_valid=False) == "m1"
    assert choose_operator(attempts_done=1, has_explicit_parent=False, last_valid=True) == "e1"


def test_i1_prompt_has_no_parent_or_failure(canary):
    prompt = build_prompt("i1")
    assert TASK_DESCRIPTION in prompt
    assert "Dev objective:" not in prompt
    assert "Failed code:" not in prompt
    assert "Error code:" not in prompt
    assert canary not in prompt
    with pytest.raises(ValueError, match="i1_must_not"):
        build_prompt("i1", parent_code=BASELINE_CODE)


def test_e1_prompt_contains_single_parent_and_score(canary):
    prompt = build_prompt("e1", parent_code=BASELINE_CODE, parent_objective=12.5)
    assert "Dev objective: 12.5" in prompt
    assert BASELINE_CODE.strip() in prompt
    assert "I have one existing algorithm" in prompt
    assert "Failed code:" not in prompt
    assert "Last candidate" not in prompt
    assert canary not in prompt
    with pytest.raises(ValueError, match="e1_must_not"):
        build_prompt("e1", parent_code=BASELINE_CODE, parent_objective=1.0, failed_code="x")


def test_e1_prompt_keeps_last_non_incumbent_candidate():
    last = "def select_next_node(*args):\n    return 0\n"
    prompt = build_prompt(
        "e1",
        parent_code=BASELINE_CODE,
        parent_objective=6.95,
        last_code=last,
        last_objective=14.044767,
    )
    assert "Dev objective: 6.95" in prompt
    assert BASELINE_CODE.strip() in prompt
    assert "Last candidate objective: 14.044767" in prompt
    assert last in prompt
    assert "Failed code:" not in prompt


def test_m1_prompt_contains_failed_code_and_error(canary):
    failed = "def select_next_node(*args):\n    return 'nope'\n"
    prompt = build_prompt(
        "m1",
        failed_code=failed,
        error_code="invalid_return",
        incumbent_code=BASELINE_CODE,
        incumbent_objective=9.0,
    )
    assert "Error code: invalid_return" in prompt
    assert failed in prompt
    assert "do not treat it as the code to repair" in prompt
    assert canary not in prompt
    with pytest.raises(ValueError, match="m1_requires"):
        build_prompt("m1", failed_code=failed)


def test_m1_prompt_accepts_empty_failed_code_with_raw_reply():
    reply = "The heuristic should prefer nearby customers. No function is provided."
    prompt = build_prompt(
        "m1",
        failed_code="",
        error_code="generation_parse_error",
        raw_reply=reply,
        incumbent_code=BASELINE_CODE,
        incumbent_objective=6.95,
    )
    assert "Error code: generation_parse_error" in prompt
    assert "Previous model reply (no executable code extracted):" in prompt
    assert reply in prompt
    assert "Failed code:" not in prompt
