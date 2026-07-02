from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


Evaluator = Callable[..., dict[str, Any]]


@dataclass(frozen=True)
class ProblemSpec:
    """A benchmark problem/evaluator boundary for the C+L+V harness."""

    name: str
    language: str
    source_files: list[str]
    main_binary: str
    objective_direction: str
    evaluator: Evaluator | None = None
    benchmark_data: list[dict[str, Any]] = field(default_factory=list)
    default_metrics: dict[str, str] = field(default_factory=lambda: {"primary": "cost", "secondary": "valid_rate"})

    def resolve_source_files(self, root: str | Path) -> list[Path]:
        root_path = Path(root).resolve()
        return [(root_path / path).resolve() for path in self.source_files]

