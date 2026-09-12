"""Fixture-only deterministic search policy (legacy main loop).

Reproduces the pre-refactor loop: ``choose_operator``, e1-parent selection,
m1 raw_reply/failed_code edit target, better_objective acceptance, and the
STAGNATION_E1_STREAK rule. Never used by production runs; its identity is
marked ``fixture_only`` so it cannot share defaults with production skills.
"""

from __future__ import annotations

from typing import Any

from tests.fixtures.contracts import STAGNATION_E1_STREAK, better_objective

POLICY_ID = "fixture_legacy"
POLICY_VERSION = "fixed/v1"


def choose_operator(
    *,
    attempts_done: int,
    has_explicit_parent: bool,
    last_valid: bool | None,
) -> str:
    """Fixed policy: i1 cold start, e1 after success, m1 after failure."""
    if attempts_done == 0:
        return "e1" if has_explicit_parent else "i1"
    if last_valid is False:
        return "m1"
    return "e1"


def fixture_policy_identity() -> dict[str, Any]:
    return {
        "id": POLICY_ID,
        "version": POLICY_VERSION,
        "params": {"stagnation_e1_streak": STAGNATION_E1_STREAK},
        "fixture_only": True,
    }


class SearchPolicy:
    """Base contract for operator/parent/accept decisions."""

    policy_id: str = POLICY_ID
    policy_version: str = POLICY_VERSION
    stagnation_e1_streak: int = STAGNATION_E1_STREAK

    def choose_operator(self, *, attempts_done: int, has_explicit_parent: bool, last_valid: bool | None) -> str:
        raise NotImplementedError

    def select_parent(self, *, operator: str, incumbent: Any, last: Any) -> str | None:
        raise NotImplementedError

    def edit_target(self, *, operator: str, last: Any) -> str:
        raise NotImplementedError

    def accept(self, candidate: float | None, incumbent: float | None) -> bool:
        raise NotImplementedError

    def structural_explore(self, *, operator: str, non_improving_e1: int) -> bool:
        raise NotImplementedError

    def identity(self) -> dict[str, Any]:
        return {
            "id": self.policy_id,
            "version": self.policy_version,
            "params": {"stagnation_e1_streak": self.stagnation_e1_streak},
            "fixture_only": True,
        }


class FixedSearchPolicy(SearchPolicy):
    """Deterministic legacy policy matching the pre-refactor loop exactly."""

    policy_id: str = POLICY_ID
    policy_version: str = POLICY_VERSION

    def choose_operator(self, *, attempts_done: int, has_explicit_parent: bool, last_valid: bool | None) -> str:
        return choose_operator(
            attempts_done=attempts_done,
            has_explicit_parent=has_explicit_parent,
            last_valid=last_valid,
        )

    def select_parent(self, *, operator: str, incumbent: Any, last: Any) -> str | None:
        if operator == "e1":
            return incumbent.version_id if incumbent is not None else None
        return None

    def edit_target(self, *, operator: str, last: Any) -> str:
        if operator == "m1":
            return "raw_reply" if (last is None or not last.code) else "failed_code"
        return "incumbent"

    def accept(self, candidate: float | None, incumbent: float | None) -> bool:
        return better_objective(candidate, incumbent)

    def structural_explore(self, *, operator: str, non_improving_e1: int) -> bool:
        return operator == "e1" and non_improving_e1 >= self.stagnation_e1_streak
