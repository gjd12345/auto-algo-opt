"""Data contracts for Milestone 2 interface designs, 5-gate validation, and frozen solvers."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from keyword import iskeyword
from typing import Any, Mapping, Sequence

ALLOWED_POSTPROCESS_MODES: frozenset[str] = frozenset({
    "none",
    "intra_2opt",
    "relocate_2opt",
})

OUTCOME_COMPLETED = "completed"
OUTCOME_BUDGET_EXHAUSTED_INCUMBENT = "budget_exhausted_feasible_incumbent"
OUTCOME_TIMEOUT_OR_INFEASIBLE = "timeout_or_infeasible"
LEGACY_CVRP_PROTOCOL_ID = "cvrp/v1"


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
class HookSpec:
    """Named hook signature and strict numeric output contract.

    A missing output_shape_arg means scalar. A named argument means one score
    per element of that argument, in a one-dimensional vector.
    """

    name: str
    signature: tuple[str, ...]
    output_shape_arg: str | None = None

    def __post_init__(self) -> None:
        names = (self.name, *self.signature)
        if any(not name.isidentifier() or iskeyword(name) for name in names):
            raise ValueError("invalid_hook_identifier")
        if len(set(self.signature)) != len(self.signature):
            raise ValueError("duplicate_hook_parameter")
        if self.output_shape_arg is not None and self.output_shape_arg not in self.signature:
            raise ValueError("unknown_hook_output_shape_arg")

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "signature": list(self.signature), "output_shape_arg": self.output_shape_arg}

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "HookSpec":
        return cls(raw["name"], tuple(raw["signature"]), raw.get("output_shape_arg"))


def hook_bundle_metadata(
    hook_specs: Sequence[HookSpec], hook_implementations: Mapping[str, str],
) -> dict[str, Any]:
    """Hash named implementations in contract order, binding names and signatures."""
    names = [spec.name for spec in hook_specs]
    if not names or len(names) != len(set(names)) or set(names) != set(hook_implementations):
        raise ValueError("hook_bundle_names_mismatch")
    if any(not isinstance(code, str) or not code.strip() for code in hook_implementations.values()):
        raise ValueError("invalid_hook_implementation")
    contract_hash = sha256_text(canonical_json([spec.to_dict() for spec in hook_specs]))
    hook_hashes = {name: sha256_text(hook_implementations[name]) for name in names}
    bundle_hash = sha256_text(canonical_json({
        "schema_version": "interface-hook-bundle/v1",
        "hook_contract_sha256": contract_hash,
        "implementations": [[name, hook_hashes[name]] for name in names],
    }))
    return {"hook_hashes": hook_hashes, "bundle_hash": bundle_hash, "hook_contract_sha256": contract_hash}


def _bundle_fields(
    hook_specs: Sequence[HookSpec], implementations: Mapping[str, str],
    hook_name: str, hook_code: str,
) -> dict[str, Any]:
    if not hook_specs and not implementations:
        return {}
    metadata = hook_bundle_metadata(hook_specs, implementations)
    if hook_specs[0].name != hook_name or implementations[hook_name] != hook_code:
        raise ValueError("primary_hook_mismatch")
    return {
        "hook_specs": [spec.to_dict() for spec in hook_specs],
        "hook_implementations": dict(implementations),
        **metadata,
    }


def _read_bundle_fields(raw: Mapping[str, Any]) -> dict[str, Any]:
    specs = tuple(HookSpec.from_dict(spec) for spec in raw.get("hook_specs", ()))
    implementations = dict(raw.get("hook_implementations", {}))
    if specs or implementations or any(key in raw for key in ("hook_hashes", "bundle_hash", "hook_contract_sha256")):
        metadata = hook_bundle_metadata(specs, implementations)
        for key, expected in metadata.items():
            if raw.get(key) != expected:
                raise ValueError(f"{key}_mismatch")
    return {"hook_specs": specs, "hook_implementations": implementations, "protocol_id": raw.get("protocol_id")}


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
    protocol_id: str | None = None
    hook_specs: tuple[HookSpec, ...] = ()
    hook_implementations: dict[str, str] = field(default_factory=dict)

    def canonical_dict(self) -> dict[str, Any]:
        payload = {
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
        if self.protocol_id is not None:
            payload["protocol_id"] = self.protocol_id
        if self.hook_specs and self.hook_signature != self.hook_specs[0].signature:
            raise ValueError("primary_hook_signature_mismatch")
        payload.update(_bundle_fields(
            self.hook_specs, self.hook_implementations, self.hook_name, self.baseline_hook_code,
        ))
        return payload

    @property
    def design_sha256(self) -> str:
        return sha256_text(canonical_json(self.canonical_dict()))

    @property
    def baseline_hook_sha256(self) -> str:
        return sha256_text(self.baseline_hook_code)

    def to_dict(self) -> dict[str, Any]:
        payload = self.canonical_dict()
        payload["schema_version"] = (
            "interface-design/v2" if self.protocol_id is not None or self.hook_specs else "m2-interface-design/v1"
        )
        payload["design_sha256"] = self.design_sha256
        payload["baseline_hook_sha256"] = self.baseline_hook_sha256
        return payload

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "InterfaceDesign":
        design = cls(
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
            **_read_bundle_fields(raw),
        )
        if design.protocol_id is not None or design.hook_specs:
            if raw.get("design_sha256") != design.design_sha256:
                raise ValueError("design_sha256_mismatch")
            if raw.get("baseline_hook_sha256") != design.baseline_hook_sha256:
                raise ValueError("baseline_hook_sha256_mismatch")
        return design


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
    protocol_id: str | None = None
    hook_specs: tuple[HookSpec, ...] = ()
    hook_implementations: dict[str, str] = field(default_factory=dict)
    hook_hashes: dict[str, str] = field(default_factory=dict)
    bundle_hash: str | None = None
    hook_contract_sha256: str | None = None

    def __post_init__(self) -> None:
        if self.hook_specs or self.hook_implementations or self.hook_hashes or self.bundle_hash or self.hook_contract_sha256:
            metadata = _bundle_fields(self.hook_specs, self.hook_implementations, self.hook_name, self.hook_code)
            for key in ("hook_hashes", "bundle_hash", "hook_contract_sha256"):
                actual = getattr(self, key)
                if actual not in (None, {}) and actual != metadata.get(key):
                    raise ValueError(f"{key}_mismatch")
                if key not in metadata:
                    raise ValueError("hook_bundle_names_mismatch")
                object.__setattr__(self, key, metadata[key])

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "schema_version": (
                "frozen-interface-solver/v2" if self.protocol_id is not None or self.hook_specs else "m2-frozen-interface-solver/v1"
            ),
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
        if self.protocol_id is not None:
            payload["protocol_id"] = self.protocol_id
        metadata = _bundle_fields(self.hook_specs, self.hook_implementations, self.hook_name, self.hook_code)
        for key in ("hook_hashes", "bundle_hash", "hook_contract_sha256"):
            if metadata and getattr(self, key) != metadata[key]:
                raise ValueError(f"{key}_mismatch")
        payload.update(metadata)
        return payload

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
            **_read_bundle_fields(raw),
        )
