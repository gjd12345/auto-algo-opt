"""Adapter for the pinned official FeiLiu36/EoH engine and problem contracts."""

from __future__ import annotations

from typing import Any

__all__ = ["FrozenProblem", "FrozenCVRPConstruct"]


def __getattr__(name: str) -> Any:
    if name == "FrozenCVRPConstruct":
        from eoh_frozen.problem import FrozenCVRPConstruct

        return FrozenCVRPConstruct
    if name == "FrozenProblem":
        from eoh_frozen.problem import FrozenProblem

        return FrozenProblem
    raise AttributeError(name)
