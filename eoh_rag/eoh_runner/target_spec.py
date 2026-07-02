from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TargetSpec:
    """A Go function that can be evolved by the EOH harness."""

    name: str
    function_name: str
    signature: str
    inputs: list[str]
    outputs: list[str]
    prompt_constraints: str
    extract_regex: str
    replace_regex_template: str
    seed_path: str | None = None
    rag_api_context: str = ""
    guard_checks: list[str] = field(default_factory=list)

