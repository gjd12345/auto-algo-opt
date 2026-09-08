"""Adapter: official FeiLiu36/EoH on the frozen CVRP construct suite."""

from __future__ import annotations

from typing import Any

__all__ = ["FrozenCVRPConstruct"]


def __getattr__(name: str) -> Any:
    if name == "FrozenCVRPConstruct":
        from eoh_frozen.problem import FrozenCVRPConstruct

        return FrozenCVRPConstruct
    raise AttributeError(name)
