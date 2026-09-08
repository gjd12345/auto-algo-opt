from __future__ import annotations

import pytest

from agent_skill_loop.contracts import choose_operator
from agent_skill_loop.generator import PromptFeedback, build_prompt
from agent_skill_loop.problems.cvrp import BASELINE_CODE, TASK_DESCRIPTION


def test_operator_state_machine():
    assert choose_operator(attempts_done=0, has_explicit_parent=False, last_valid=None) == "i1"
    assert choose_operator(attempts_done=0, has_explicit_parent=True, last_valid=None) == "e1"
    assert choose_operator(attempts_done=1, has_explicit_parent=False, last_valid=False) == "m1"
    assert choose_operator(attempts_done=1, has_explicit_parent=False, last_valid=True) == "e1"


def test_i1_prompt_has_no_parent_or_failure(canary):
    prompt = build_prompt("i1")
    assert TASK_DESCRIPTION in prompt
    assert "INCUMBENT:" not in prompt
    assert "LAST CANDIDATE:" not in prompt
    assert "error_code:" not in prompt
    assert canary not in prompt
    with pytest.raises(ValueError, match="i1_must_not"):
        build_prompt("i1", PromptFeedback(incumbent_code=BASELINE_CODE, incumbent_objective=1.0))


def test_e1_prompt_contains_single_parent_and_score(canary):
    prompt = build_prompt(
        "e1",
        PromptFeedback(
            incumbent_id="baseline",
            incumbent_code=BASELINE_CODE,
            incumbent_objective=12.5,
            incumbent_instances=(4.0, 4.0, 4.5),
            edit_target="incumbent",
        ),
    )
    assert "mean_objective: 12.5" in prompt
    assert BASELINE_CODE.strip() in prompt
    assert "INCUMBENT:" in prompt
    assert "EDIT TARGET: incumbent" in prompt
    assert "LAST CANDIDATE:" not in prompt
    assert canary not in prompt
    with pytest.raises(ValueError, match="e1_must_not"):
        build_prompt(
            "e1",
            PromptFeedback(
                incumbent_code=BASELINE_CODE,
                incumbent_objective=1.0,
                failed_code="x",
                error_code="invalid_return",
            ),
        )


def test_e1_prompt_keeps_last_non_incumbent_candidate():
    last = "def select_next_node(*args):\n    return 0\n"
    prompt = build_prompt(
        "e1",
        PromptFeedback(
            incumbent_id="baseline",
            incumbent_code=BASELINE_CODE,
            incumbent_objective=6.95,
            incumbent_instances=(6.2, 7.1, 7.4),
            last_attempt_id=1,
            last_code=last,
            last_code_hash="abc",
            last_valid=True,
            last_objective=14.044767,
            last_instances=(12.0, 14.0, 16.0),
            delta_vs_incumbent=7.094767,
            accepted=False,
            accept_reason="rejected_not_better",
            edit_target="incumbent",
        ),
    )
    assert "mean_objective: 6.95" in prompt
    assert BASELINE_CODE.strip() in prompt
    assert "LAST CANDIDATE:" in prompt
    assert "mean_objective: 14.044767" in prompt
    assert "delta_vs_incumbent: 7.094767" in prompt
    assert "accept_reason: rejected_not_better" in prompt
    assert last in prompt
    assert "STAGNATION:" not in prompt


def test_e1_stagnation_asks_for_structural_change():
    prompt = build_prompt(
        "e1",
        PromptFeedback(
            incumbent_code=BASELINE_CODE,
            incumbent_objective=6.95,
            last_code="def select_next_node(*args):\n    return 0\n",
            last_objective=14.0,
            last_valid=True,
            accept_reason="rejected_not_better",
            edit_target="incumbent",
            structural_explore=True,
        ),
    )
    assert "STAGNATION:" in prompt
    assert "structural" in prompt.lower() or "Change one structural" in prompt


def test_m1_prompt_contains_failed_code_and_error(canary):
    failed = "def select_next_node(*args):\n    return 'nope'\n"
    prompt = build_prompt(
        "m1",
        PromptFeedback(
            incumbent_id="baseline",
            incumbent_code=BASELINE_CODE,
            incumbent_objective=9.0,
            last_attempt_id=1,
            last_code=failed,
            last_valid=False,
            error_code="invalid_return",
            error_detail=None,
            accept_reason="rejected_invalid",
            edit_target="failed_code",
        ),
    )
    assert "error_code: invalid_return" in prompt
    assert failed in prompt
    assert "do not treat it as the code to repair" in prompt
    assert "EDIT TARGET: failed_code" in prompt
    assert canary not in prompt
    with pytest.raises(ValueError, match="m1_requires"):
        build_prompt("m1", PromptFeedback(last_code=failed))


def test_m1_prompt_accepts_empty_failed_code_with_raw_reply():
    reply = "The heuristic should prefer nearby customers. No function is provided."
    prompt = build_prompt(
        "m1",
        PromptFeedback(
            incumbent_code=BASELINE_CODE,
            incumbent_objective=6.95,
            last_valid=False,
            error_code="generation_parse_error",
            raw_reply=reply,
            edit_target="raw_reply",
        ),
    )
    assert "error_code: generation_parse_error" in prompt
    assert "Previous model reply (no executable code extracted):" in prompt
    assert reply in prompt
    assert "EDIT TARGET: raw_reply" in prompt


def test_m1_prompt_includes_error_detail():
    prompt = build_prompt(
        "m1",
        PromptFeedback(
            incumbent_code=BASELINE_CODE,
            incumbent_objective=6.95,
            last_code="import numpy as np\nx = np.ix_([0],[0])\n",
            last_valid=False,
            error_code="forbidden_attribute",
            error_detail="ix_",
            edit_target="failed_code",
        ),
    )
    assert "error_detail: ix_" in prompt
