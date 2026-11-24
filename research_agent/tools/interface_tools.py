"""Template discovery and 5-gate behavioral validation tool for Research Agent."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from agent_skill_loop.interface_design.dynamic_eoh import derive_effective_batch_timeout_s
from agent_skill_loop.interface_design.planner import KB_ROUND_CONTEXT_BY_TEMPLATE, build_design_for_template
from agent_skill_loop.interface_design.templates import TEMPLATE_REGISTRY
from agent_skill_loop.interface_design.validator import InterfaceValidator
from research_agent.contracts import atomic_write_json, utc_now


class InterfaceTool:
    """List permitted templates and validate plan-time interface switches through all 5 gates."""

    def __init__(
        self,
        run_dir: Path,
        *,
        problem_family: str = "cvrp",
        allowed_templates: Sequence[str] = (),
        allowed_postprocess_modes: Sequence[str] = ("none", "intra_2opt", "relocate_2opt"),
        candidate_timeout_s: float = 20.0,
        default_time_budget_ms: float = 500.0,
    ) -> None:
        self.run_dir = Path(run_dir).resolve()
        self.problem_family = str(problem_family)
        self.allowed_templates = tuple(str(x) for x in allowed_templates)
        self.allowed_postprocess_modes = tuple(str(x) for x in allowed_postprocess_modes)
        self.candidate_timeout_s = float(candidate_timeout_s)
        self.default_time_budget_ms = float(default_time_budget_ms)
        self.val_dir = self.run_dir / "agent_artifacts" / "validations"
        self.val_dir.mkdir(parents=True, exist_ok=True)
        self._seq = 0

    def list_interfaces(self) -> dict[str, Any]:
        items: list[dict[str, Any]] = []
        for (tid, tver), spec in TEMPLATE_REGISTRY.items():
            if spec.problem_family != self.problem_family:
                continue
            if self.allowed_templates and tid not in self.allowed_templates:
                continue
            item = {
                "template_id": tid,
                "template_version": tver,
                "paradigm": spec.paradigm,
                "hook_name": spec.hook_name,
                "hook_signature": list(spec.hook_signature),
                "template_source_sha256": spec.template_source_sha256,
                "kb_clue_available": tid in KB_ROUND_CONTEXT_BY_TEMPLATE,
            }
            if spec.hook_specs:
                item["hook_specs"] = [
                    {
                        "hook_name": hs.hook_name,
                        "hook_signature": list(hs.hook_signature),
                        "role": hs.role,
                    }
                    for hs in spec.hook_specs
                ]
            items.append(item)
        return {
            "problem_family": self.problem_family,
            "allowed_postprocess_modes": list(self.allowed_postprocess_modes),
            "templates": items,
        }

    def propose_and_validate(
        self,
        *,
        template_id: str,
        template_version: str = "v1",
        postprocess_mode: str = "none",
        time_budget_ms: float | None = None,
        diagnostic_ref: Mapping[str, Any] | None = None,
        rationale: str = "",
    ) -> dict[str, Any]:
        if self.allowed_templates and template_id not in self.allowed_templates:
            raise ValueError(f"template_not_allowed_in_arm:{template_id}")
        if postprocess_mode not in self.allowed_postprocess_modes:
            raise ValueError(f"postprocess_not_allowed_in_arm:{postprocess_mode}")
        budget_ms = float(time_budget_ms if time_budget_ms is not None else self.default_time_budget_ms)
        design = build_design_for_template(
            template_id,
            template_version,
            postprocess_mode=postprocess_mode,
            diagnostic_ref=dict(diagnostic_ref) if diagnostic_ref else None,
            rationale=rationale or f"Validated {template_id}/{template_version} under {budget_ms} ms.",
        )
        eff_timeout_s = derive_effective_batch_timeout_s(12, budget_ms, floor_s=self.candidate_timeout_s)
        validator = InterfaceValidator(
            candidate_timeout_s=eff_timeout_s,
            instance_time_budget_ms=budget_ms,
        )
        report = validator.validate(design)
        self._seq += 1
        rel_path = f"agent_artifacts/validations/val_{self._seq:04d}.json"
        payload = {
            "validated_at": utc_now(),
            "time_budget_ms": budget_ms,
            "report": report.as_dict(),
        }
        sha = atomic_write_json(self.run_dir / rel_path, payload)
        return {
            "passed": report.passed,
            "artifact_ref": rel_path,
            "artifact_sha256": sha,
            "template_id": template_id,
            "postprocess_mode": postprocess_mode,
            "time_budget_ms": budget_ms,
            "failures": [f.as_dict() for f in report.failures],
            "gate5": report.diagnostics.get("gate5"),
        }
