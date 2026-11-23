"""Template-agnostic 5-factor slicing diagnostics restricted to dev suites."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from agent_skill_loop.benchmark.catalog import load_profile_suite
from agent_skill_loop.cvrp_workbench.solvers import evaluate_algorithm_on_instance
from agent_skill_loop.cvrp_workbench.suites import BENCHMARK_ID
from agent_skill_loop.interface_design.blind_commitment import assert_suite_allowed_for_interactive_role
from agent_skill_loop.interface_design.diagnostics import analyze_instance_records
from agent_skill_loop.interface_design.runtime import compile_hook_function, evaluate_hook_on_instance_inprocess
from agent_skill_loop.interface_design.templates import get_template_spec
from research_agent.contracts import atomic_write_json, utc_now


class DiagnosticTool:
    """Evaluate templates/hooks strictly on dev splits and emit SHA-256 bound diagnostic reports."""

    def __init__(
        self,
        run_dir: Path,
        *,
        dev_suite_id: str = "cvrp_dev_hetero_24",
        dev_split: str = "dev_train",
    ) -> None:
        self.run_dir = Path(run_dir).resolve()
        self.dev_suite_id = str(dev_suite_id)
        self.dev_split = str(dev_split)
        assert_suite_allowed_for_interactive_role(self.dev_suite_id, role="diagnostic_interactive")
        self.diag_dir = self.run_dir / "agent_artifacts" / "diagnostics"
        self.diag_dir.mkdir(parents=True, exist_ok=True)
        self._seq = 0

    def _load_dev_instances(self, max_instances: int | None = None) -> tuple[list[dict[str, Any]], str, str]:
        suite = load_profile_suite(BENCHMARK_ID, self.dev_suite_id, split=self.dev_split)
        assert_suite_allowed_for_interactive_role(self.dev_suite_id, suite, role="diagnostic_interactive")
        insts = list(suite["instances"])
        if max_instances is not None:
            insts = insts[: int(max_instances)]
        return insts, str(suite["distance_convention"]), str(suite["vehicle_limit_policy"])

    def diagnose_suite(
        self,
        *,
        template_id: str,
        template_version: str = "v1",
        hook_code: str | None = None,
        postprocess_mode: str = "none",
        time_budget_ms: float = 500.0,
        baseline_algorithm: str = "cw_parallel_merge",
        max_instances: int | None = None,
    ) -> dict[str, Any]:
        self._seq += 1
        insts, dist_conv, veh_pol = self._load_dev_instances(max_instances=max_instances)
        tpl = get_template_spec(template_id, template_version)
        code = hook_code if hook_code is not None else tpl.default_baseline_hook_code
        fn = compile_hook_function(code, hook_name=tpl.hook_name, expected_args=tpl.hook_signature)

        meta_map = {str(inst["instance_id"]): inst for inst in insts}
        cand_records: list[dict[str, Any]] = []
        base_records: list[dict[str, Any]] = []
        for inst in insts:
            cand_records.append(
                evaluate_hook_on_instance_inprocess(
                    template_id=template_id,
                    template_version=template_version,
                    hook_fn=fn,
                    instance=inst,
                    postprocess_mode=postprocess_mode,
                    distance_convention=dist_conv,
                    vehicle_limit_policy=veh_pol,
                    time_budget_ms=time_budget_ms,
                )
            )
            base_records.append(
                evaluate_algorithm_on_instance(
                    baseline_algorithm,
                    inst,
                    distance_convention=dist_conv,
                    vehicle_limit_policy=veh_pol,
                    time_budget_ms=time_budget_ms,
                    record_trace=False,
                )
            )

        analysis = analyze_instance_records(
            cand_records,
            instance_metadata=meta_map,
            baseline_records=base_records,
        )
        rel_path = f"agent_artifacts/diagnostics/diag_{self._seq:04d}.json"
        out_path = self.run_dir / rel_path
        payload = {
            "schema_version": "m3-diagnostic-report/v1",
            "generated_at": utc_now(),
            "suite_id": self.dev_suite_id,
            "template_id": template_id,
            "template_version": template_version,
            "postprocess_mode": postprocess_mode,
            "time_budget_ms": float(time_budget_ms),
            "baseline_algorithm": baseline_algorithm,
            "analysis": analysis,
            "per_instance_records": cand_records,
        }
        sha = atomic_write_json(out_path, payload)
        return {
            "artifact_ref": rel_path,
            "artifact_sha256": sha,
            "suite_id": self.dev_suite_id,
            "template_id": template_id,
            "postprocess_mode": postprocess_mode,
            "time_budget_ms": float(time_budget_ms),
            "analysis": analysis,
        }
