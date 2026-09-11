"""Search policy abstraction.

Extracts the deterministic operator / parent / edit-target / acceptance /
stagnation decisions that the loop used to make inline into a small,
swappable SearchPolicy. ``FixedSearchPolicy`` reproduces the pre-refactor
behavior exactly (choose_operator, e1-parent selection, m1 raw_reply/failed_code
edit target, better_objective acceptance, and the STAGNATION_E1_STREAK rule).
No model controller is added at this stage.
"""

from __future__ import annotations

from typing import Any

from agent_skill_loop.contracts import STAGNATION_E1_STREAK, better_objective, choose_operator

POLICY_ID = "fixed"
POLICY_VERSION = "v1"


def search_policy_identity() -> dict[str, Any]:
    return {
        "id": POLICY_ID,
        "version": POLICY_VERSION,
        "params": {"stagnation_e1_streak": STAGNATION_E1_STREAK},
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
        }


class FixedSearchPolicy(SearchPolicy):
    """Deterministic policy matching the pre-refactor loop exactly."""

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
