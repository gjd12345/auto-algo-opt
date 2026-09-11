from __future__ import annotations

from agent_skill_loop.contracts import STAGNATION_E1_STREAK
from agent_skill_loop.policy import FixedSearchPolicy, SearchPolicy, search_policy_identity


class _Last:
    def __init__(self, code: str | None) -> None:
        self.code = code


def test_fixed_policy_choose_operator_matches_contract():
    policy = FixedSearchPolicy()
    assert policy.choose_operator(attempts_done=0, has_explicit_parent=False, last_valid=None) == "i1"
    assert policy.choose_operator(attempts_done=0, has_explicit_parent=True, last_valid=None) == "e1"
    assert policy.choose_operator(attempts_done=1, has_explicit_parent=False, last_valid=False) == "m1"
    assert policy.choose_operator(attempts_done=1, has_explicit_parent=False, last_valid=True) == "e1"


def test_fixed_policy_parent_selection():
    policy = FixedSearchPolicy()

    class Incumbent:
        version_id = "baseline"

    assert policy.select_parent(operator="i1", incumbent=Incumbent(), last=None) is None
    assert policy.select_parent(operator="e1", incumbent=Incumbent(), last=None) == "baseline"
    assert policy.select_parent(operator="e1", incumbent=None, last=None) is None
    assert policy.select_parent(operator="m1", incumbent=Incumbent(), last=None) is None


def test_fixed_policy_edit_target():
    policy = FixedSearchPolicy()
    assert policy.edit_target(operator="e1", last=_Last("def f():\n    pass")) == "incumbent"
    assert policy.edit_target(operator="e1", last=None) == "incumbent"
    assert policy.edit_target(operator="m1", last=_Last("def f():\n    pass")) == "failed_code"
    assert policy.edit_target(operator="m1", last=_Last("")) == "raw_reply"
    assert policy.edit_target(operator="m1", last=None) == "raw_reply"


def test_fixed_policy_acceptance_is_better_objective():
    policy = FixedSearchPolicy()
    assert policy.accept(5.0, 6.0) is True
    assert policy.accept(6.0, 5.0) is False
    assert policy.accept(6.0, 6.0) is False
    assert policy.accept(None, 5.0) is False
    assert policy.accept(5.0, None) is True


def test_fixed_policy_stagnation_streak():
    policy = FixedSearchPolicy()
    assert policy.stagnation_e1_streak == STAGNATION_E1_STREAK
    assert policy.structural_explore(operator="e1", non_improving_e1=STAGNATION_E1_STREAK - 1) is False
    assert policy.structural_explore(operator="e1", non_improving_e1=STAGNATION_E1_STREAK) is True
    assert policy.structural_explore(operator="e1", non_improving_e1=STAGNATION_E1_STREAK + 1) is True
    assert policy.structural_explore(operator="m1", non_improving_e1=STAGNATION_E1_STREAK) is False
    assert policy.structural_explore(operator="i1", non_improving_e1=STAGNATION_E1_STREAK) is False


def test_fixed_policy_identity_is_stable():
    policy = FixedSearchPolicy()
    expected = {
        "id": "fixed",
        "version": "v1",
        "params": {"stagnation_e1_streak": STAGNATION_E1_STREAK},
    }
    assert policy.identity() == expected
    assert search_policy_identity() == expected


def test_search_policy_base_requires_implementation():
    policy = SearchPolicy()
    try:
        policy.choose_operator(attempts_done=0, has_explicit_parent=False, last_valid=None)
        raise AssertionError("expected NotImplementedError")
    except NotImplementedError:
        pass