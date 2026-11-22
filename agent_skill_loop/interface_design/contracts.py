"""Data contracts for Milestone 2 interface designs, 5-gate validation, and frozen solvers."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Mapping

ALLOWED_POSTPROCESS_MODES: frozenset[str] = frozenset({
    "none",
    "intra_2opt",
    "relocate_2opt",
})

OUTCOME_COMPLETED = "completed"
OUTCOME_BUDGET_EXHAUSTED_INCUMBENT = "budget_exhausted_feasible_incumbent"
OUTCOME_TIMEOUT_OR_INFEASIBLE = "timeout_or_infeasible"


def classify_outcome(*, valid: bool, status: str, budget_exhausted: bool) -> str:
    """Classify a single instance evaluation into the 3 explicit M2 budget outcomes."""
    if valid and status == "ok":
        return OUTCOME_BUDGET_EXHAUSTED_INCUMBENT if budget_exhausted else OUTCOME_COMPLETED
    return OUTCOME_TIMEOUT_OR_INFEASIBLE


def sha256_text(text: str) -> str:
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


@dataclass(frozen=True)
class GateFailure:
    gate_id: int
    gate_name: str
    error_code: str
    line_no: int | None
    symbol: str | None
    detail: str
    fix_hint: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "gate_id": int(self.gate_id),
            "gate_name": self.gate_name,
            "error_code": self.error_code,
            "line_no": self.line_no,
            "symbol": self.symbol,
            "detail": self.detail,
            "fix_hint": self.fix_hint,
        }


@dataclass(frozen=True)
class InterfaceDesign:
    """Plan-time solver interface specification pinned to a versioned template."""

    design_id: str
    problem_family: str
    paradigm: str
    template_id: str
    template_version: str
    postprocess_mode: str
    hook_name: str
    hook_signature: tuple[str, ...]
    hook_task_description: str
    baseline_hook_code: str
    cited_kb_ids: tuple[str, ...] = ()
    diagnostic_ref: dict[str, Any] | None = None
    rationale: str = ""
    template_options: dict[str, Any] = field(default_factory=dict)

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "design_id": self.design_id,
            "problem_family": self.problem_family,
            "paradigm": self.paradigm,
            "template_id": self.template_id,
            "template_version": self.template_version,
            "postprocess_mode": self.postprocess_mode,
            "hook_name": self.hook_name,
            "hook_signature": list(self.hook_signature),
            "hook_task_description": self.hook_task_description,
            "baseline_hook_code": self.baseline_hook_code,
            "cited_kb_ids": list(self.cited_kb_ids),
            "diagnostic_ref": self.diagnostic_ref,
            "rationale": self.rationale,
            "template_options": dict(self.template_options),
        }

    @property
    def design_sha256(self) -> str:
        return sha256_text(canonical_json(self.canonical_dict()))

    @property
    def baseline_hook_sha256(self) -> str:
        return sha256_text(self.baseline_hook_code)

    def to_dict(self) -> dict[str, Any]:
        payload = self.canonical_dict()
        payload["schema_version"] = "m2-interface-design/v1"
        payload["design_sha256"] = self.design_sha256
        payload["baseline_hook_sha256"] = self.baseline_hook_sha256
        return payload

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "InterfaceDesign":
        return cls(
            design_id=str(raw["design_id"]),
            problem_family=str(raw.get("problem_family", "cvrp")),
            paradigm=str(raw["paradigm"]),
            template_id=str(raw["template_id"]),
            template_version=str(raw["template_version"]),
            postprocess_mode=str(raw.get("postprocess_mode", "none")),
            hook_name=str(raw["hook_name"]),
            hook_signature=tuple(str(x) for x in raw["hook_signature"]),
            hook_task_description=str(raw["hook_task_description"]),
            baseline_hook_code=str(raw["baseline_hook_code"]),
            cited_kb_ids=tuple(str(x) for x in raw.get("cited_kb_ids", ())),
            diagnostic_ref=dict(raw["diagnostic_ref"]) if isinstance(raw.get("diagnostic_ref"), Mapping) else None,
            rationale=str(raw.get("rationale", "")),
            template_options=dict(raw.get("template_options") or {}),
        )


@dataclass(frozen=True)
class ValidationReport:
    passed: bool
    design_id: str
    design_sha256: str
    template_id: str
    template_version: str
    template_source_sha256: str | None
    hook_code_sha256: str
    gates: tuple[dict[str, Any], ...]
    failures: tuple[GateFailure, ...]
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "m2-interface-validation-report/v1",
            "passed": self.passed,
            "design_id": self.design_id,
            "design_sha256": self.design_sha256,
            "template_id": self.template_id,
            "template_version": self.template_version,
            "template_source_sha256": self.template_source_sha256,
            "hook_code_sha256": self.hook_code_sha256,
            "gates": list(self.gates),
            "failures": [f.as_dict() for f in self.failures],
            "diagnostics": self.diagnostics,
        }


@dataclass(frozen=True)
class FrozenInterfaceSolver:
    """Frozen M2 solver manifest consumable by both EoH verification and M1 Workbench."""

    solver_id: str
    display_name: str
    problem_family: str
    paradigm: str
    template_id: str
    template_version: str
    template_source_sha256: str
    postprocess_mode: str
    template_options: dict[str, Any]
    hook_name: str
    hook_code: str
    hook_code_sha256: str
    design_sha256: str
    origin_run: str
    kb_release_id: str
    kb_entry_id: str | None = None
    cited_kb_ids: tuple[str, ...] = ()
    diagnostic_ref: dict[str, Any] | None = None
    description: str = ""
    default_budget_ms: float = 500.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "m2-frozen-interface-solver/v1",
            "solver_id": self.solver_id,
            "display_name": self.display_name,
            "problem_family": self.problem_family,
            "paradigm": self.paradigm,
            "interface": f"{self.template_id}/{self.template_version}:{self.hook_name}",
            "template_id": self.template_id,
            "template_version": self.template_version,
            "template_source_sha256": self.template_source_sha256,
            "postprocess_mode": self.postprocess_mode,
            "template_options": dict(self.template_options),
            "hook_name": self.hook_name,
            "hook_code": self.hook_code,
            "hook_code_sha256": self.hook_code_sha256,
            "design_sha256": self.design_sha256,
            "origin_run": self.origin_run,
            "kb_release_id": self.kb_release_id,
            "kb_entry_id": self.kb_entry_id,
            "cited_kb_ids": list(self.cited_kb_ids),
            "diagnostic_ref": self.diagnostic_ref,
            "description": self.description,
            "default_budget_ms": float(self.default_budget_ms),
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "FrozenInterfaceSolver":
        hook_code = str(raw["hook_code"])
        hook_sha = str(raw.get("hook_code_sha256") or sha256_text(hook_code))
        if hook_sha != sha256_text(hook_code):
            raise ValueError("frozen_solver_hook_sha256_mismatch")
        return cls(
            solver_id=str(raw["solver_id"]),
            display_name=str(raw.get("display_name") or raw["solver_id"]),
            problem_family=str(raw.get("problem_family", "cvrp")),
            paradigm=str(raw["paradigm"]),
            template_id=str(raw["template_id"]),
            template_version=str(raw["template_version"]),
            template_source_sha256=str(raw["template_source_sha256"]),
            postprocess_mode=str(raw.get("postprocess_mode", "none")),
            template_options=dict(raw.get("template_options") or {}),
            hook_name=str(raw["hook_name"]),
            hook_code=hook_code,
            hook_code_sha256=hook_sha,
            design_sha256=str(raw["design_sha256"]),
            origin_run=str(raw["origin_run"]),
            kb_release_id=str(raw["kb_release_id"]),
            kb_entry_id=str(raw["kb_entry_id"]) if raw.get("kb_entry_id") else None,
            cited_kb_ids=tuple(str(x) for x in raw.get("cited_kb_ids", ())),
            diagnostic_ref=dict(raw["diagnostic_ref"]) if isinstance(raw.get("diagnostic_ref"), Mapping) else None,
            description=str(raw.get("description", "")),
            default_budget_ms=float(raw.get("default_budget_ms", 500.0)),
        )
