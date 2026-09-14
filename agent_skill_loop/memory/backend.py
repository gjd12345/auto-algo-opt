"""Pluggable boundary for Session memory backends."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Protocol

from .api import MemoryAPI, MemoryEntry


class MemoryBackend(Protocol):
    def read(self, query: str, *, project: str, scene: str | None = None,
             memory_type: str | None = None, limit: int = 8,
             include_cross_project: bool = False, offset: int = 0,
             include_shared: bool = True) -> dict[str, Any]: ...

    def read_version(self, reference: str, *, max_chars: int = 8000,
                     offset: int = 0) -> dict[str, Any]: ...

    def write(self, entry: MemoryEntry, *, based_on: str | None = None,
              related_refs: tuple[str, ...] = (), provenance: Mapping[str, Any] | None = None,
              operation_key: str | None = None) -> dict[str, Any]: ...


def open_memory_backend(store: Path, *, policy_id: str = "markdown-memory") -> MemoryBackend:
    """Resolve the frozen policy without coupling Session code to its class."""
    if policy_id != "markdown-memory":
        raise ValueError("memory_policy_not_supported")
    return MemoryAPI(store)
