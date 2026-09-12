"""Plan role: strict JSON advisory direction, never executable code."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from typing import Any, Callable, Mapping

from agent_skill_loop.contracts_3plus1 import PlanDocument, strict_json_object, _strict_keys


@dataclass(frozen=True)
class MemorySelection:
    memory_refs: tuple[str, ...]

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any], *, available: set[str]) -> "MemorySelection":
        _strict_keys(raw, frozenset({"memory_refs"}), "memory_selection")
        refs = raw.get("memory_refs")
        if not isinstance(refs, list) or len(refs) > 2 or any(not isinstance(ref, str) or not ref.strip() for ref in refs):
            raise ValueError("memory_selection_invalid")
        values = tuple(ref.strip() for ref in refs)
        if not set(values).issubset(available):
            raise ValueError("memory_reference_not_found")
        return cls(values)


@dataclass(frozen=True)
class PlanPrompt:
    problem: str
    suite_hash: str
    round_id: int
    incumbent: Mapping[str, Any] | None
    feedback: Mapping[str, Any] | None
    feedback_reference: Mapping[str, Any] | None = None
    memory: tuple[Mapping[str, Any], ...] = ()
    problem_contract: Mapping[str, Any] | None = None
    mode: str = "final"
    selected_memory: tuple[Mapping[str, Any], ...] = ()

    def render(self) -> str:
        if self.mode == "select_memory":
            payload = {
                "role": "plan",
                "mode": "select_memory",
                "instruction": "Select at most two relevant memory references. Return JSON only; do not write a plan or code.",
                "output_schema": {"memory_refs": ["project/insight_name@v0001"]},
                "problem_contract": self.problem_contract,
                "problem": self.problem,
                "suite_hash": self.suite_hash,
                "round_id": self.round_id,
                "feedback_reference": self.feedback_reference,
                "memory_index": list(self.memory),
                "memory": list(self.memory),
            }
            return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        payload = {
            "role": "plan",
            "mode": "final",
            "instruction": "Return one JSON object only. Follow the exact schema. This is advisory planning: never emit executable code, budget, model, operator, evaluator, or stop fields.",
            "output_schema": {
                "round_id": "integer for this round",
                "direction": "non-empty string",
                "operations": [{"type": "add|remove|replace|preserve", "target": "heuristic concept", "mechanism": "non-empty string"}],
                "preserve": "interface and evaluator invariants",
                "feedback_basis": "null on round 1; on later rounds copy feedback_reference exactly",
                "memory_basis": ["exact versioned memory references selected from the index"],
                "reference_skill_ref": "null or the exact supplied incumbent/parent skill reference",
                "hypothesis": "testable but non-authoritative explanation",
            },
            "problem": self.problem,
            "suite_hash": self.suite_hash,
            "round_id": self.round_id,
            "problem_contract": self.problem_contract,
            "incumbent": self.incumbent,
            "feedback": self.feedback,
            "feedback_reference": self.feedback_reference,
            "memory": list(self.memory),
            "selected_memory": list(self.selected_memory),
        }
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


class PlanRole:
    def __init__(self, request: Callable[..., str]) -> None:
        self._request = request

    def run(self, prompt: PlanPrompt, *, read_memory: Callable[[str], Mapping[str, Any]] | None = None, **validation: Any) -> PlanDocument:
        if prompt.mode == "select_memory" and prompt.memory:
            response = self._request(prompt.render(), purpose="plan", problem=prompt.problem)
            raw = strict_json_object(response)
            # A fixture may still return the final plan in one call. Production
            # models are expected to follow the explicit selection contract.
            if "round_id" not in raw:
                selection = MemorySelection.from_dict(raw, available=set(validation.get("available_memory_refs") or set()))
                if read_memory is None:
                    raise ValueError("memory_reader_required")
                selected = tuple(read_memory(ref) for ref in selection.memory_refs)
                prompt = replace(prompt, mode="final", selected_memory=selected)
                response = self._request(prompt.render(), purpose="plan", problem=prompt.problem)
                validation = {**validation, "available_memory_refs": set(selection.memory_refs)}
        else:
            response = self._request(prompt.render(), purpose="plan", problem=prompt.problem)
        return PlanDocument.from_dict(strict_json_object(response), **validation)
