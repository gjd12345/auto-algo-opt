"""Bridge connecting Milestone 2 dynamic interfaces into the cross-harness Skill + Session Runtime.

Allows any Coding Agent (Claude Code, Codex, OpenCode, Antigravity, Cursor, etc.) driving
``skills/algorithm-optimization/SKILL.md`` via ``session submit-plan -> execute -> collect -> finish-round``
to diagnose, validate (5 gates), switch templates at plan-time, execute EoH under Session's
durable SQLite budget/recovery/evidence ledger, and export ``FrozenInterfaceSolver`` manifests
back to the Milestone 1 Workbench — with zero changes to ``eoh_frozen/``.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import time
import uuid
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from agent_skill_loop.contracts import EOH_COMMIT, EvaluationResult, SkillVersion
from agent_skill_loop.evaluator import evaluator_source_hash
from agent_skill_loop.session_ledger import SessionRequestBudget, solver_event
from agent_skill_loop.skill_store import _atomic_write_text, save_skill

from .contracts import ALLOWED_POSTPROCESS_MODES, FrozenInterfaceSolver, InterfaceDesign, sha256_text
from .dynamic_eoh import DEFAULT_MOCK_MERGE_CANDIDATES, DynamicInterfaceProblem, MockEoHLLMServer
from .planner import KB_ROUND_CONTEXT_BY_TEMPLATE, build_design_for_template
from .templates import TEMPLATE_REGISTRY, get_template_spec
from .validator import InterfaceValidator

INTERFACE_SELECTION_KEYS = frozenset({
    "template_id",
    "template_version",
    "postprocess_mode",
    "template_options",
    "cited_kb_ids",
    "diagnostic_ref",
    "rationale",
})


def parse_interface_selection(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Strictly parse optional ``plan.interface_selection`` submitted to ``session submit-plan``."""
    if not isinstance(raw, Mapping):
        raise ValueError("interface_selection_must_be_object")
    unknown = set(raw) - INTERFACE_SELECTION_KEYS
    if unknown:
        raise ValueError(f"interface_selection_unknown_fields:{','.join(sorted(unknown))}")
    tid = raw.get("template_id")
    tver = raw.get("template_version", "v1")
    if not isinstance(tid, str) or not tid.strip():
        raise ValueError("interface_selection_template_id_required")
    if not isinstance(tver, str) or not tver.strip():
        raise ValueError("interface_selection_template_version_required")
    tid = tid.strip()
    tver = tver.strip()
    if (tid, tver) not in TEMPLATE_REGISTRY:
        raise ValueError(f"interface_selection_unknown_template:{tid}/{tver}")

    post_mode = str(raw.get("postprocess_mode", "none")).strip()
    if post_mode not in ALLOWED_POSTPROCESS_MODES:
        raise ValueError(f"interface_selection_postprocess_not_allowed:{post_mode}")

    opts = raw.get("template_options")
    if opts is None:
        opts = {}
    elif not isinstance(opts, Mapping):
        raise ValueError("interface_selection_template_options_must_be_object")
    else:
        opts = dict(opts)

    cited = raw.get("cited_kb_ids", [])
    if not isinstance(cited, list) or any(not isinstance(x, str) or not x.strip() for x in cited):
        raise ValueError("interface_selection_cited_kb_ids_must_be_string_list")

    diag_ref = raw.get("diagnostic_ref")
    if diag_ref is not None and not isinstance(diag_ref, Mapping):
        raise ValueError("interface_selection_diagnostic_ref_must_be_object")

    rationale = str(raw.get("rationale") or "").strip()
    if len(rationale) > 2048:
        raise ValueError("interface_selection_rationale_too_large")

    return {
        "template_id": tid,
        "template_version": tver,
        "postprocess_mode": post_mode,
        "template_options": opts,
        "cited_kb_ids": [x.strip() for x in cited],
        "diagnostic_ref": dict(diag_ref) if isinstance(diag_ref, Mapping) else None,
        "rationale": rationale,
    }


def validate_session_interface_selection(
    selection: Mapping[str, Any],
    *,
    round_id: int,
    candidate_timeout_s: float = 20.0,
    instance_time_budget_ms: float = 500.0,
) -> tuple[InterfaceDesign, dict[str, Any]]:
    """Build ``InterfaceDesign`` from ``plan.interface_selection`` and run all 5 behavioral gates."""
    tid = str(selection["template_id"])
    tver = str(selection.get("template_version", "v1"))
    post_mode = str(selection.get("postprocess_mode", "none"))
    design = build_design_for_template(
        tid,
        tver,
        design_id=f"session_r{round_id:04d}_{tid}_{tver}",
        postprocess_mode=post_mode,
        diagnostic_ref=selection.get("diagnostic_ref"),
        rationale=str(selection.get("rationale") or f"Session round {round_id} interface selection."),
    )
    if selection.get("cited_kb_ids") or selection.get("template_options"):
        design = InterfaceDesign(
            design_id=design.design_id,
            problem_family=design.problem_family,
            paradigm=design.paradigm,
            template_id=design.template_id,
            template_version=design.template_version,
            postprocess_mode=design.postprocess_mode,
            hook_name=design.hook_name,
            hook_signature=design.hook_signature,
            hook_task_description=design.hook_task_description,
            baseline_hook_code=design.baseline_hook_code,
            cited_kb_ids=tuple(selection.get("cited_kb_ids") or design.cited_kb_ids),
            diagnostic_ref=design.diagnostic_ref,
            rationale=design.rationale,
            template_options={**design.template_options, **dict(selection.get("template_options") or {})},
        )
    validator = InterfaceValidator(
        candidate_timeout_s=candidate_timeout_s,
        instance_time_budget_ms=instance_time_budget_ms,
    )
    report = validator.validate(design)
    return design, report.as_dict()


def _normalize_session_suite_instances(suite: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Adapt a Session dev_suite.json (CVRP) into the workbench instance dict shape."""
    out: list[dict[str, Any]] = []
    for idx, inst in enumerate(suite.get("instances") or []):
        coords = inst.get("customer_coordinates") or inst.get("coordinates")
        if coords is None:
            raise ValueError("session_suite_missing_customer_coordinates")
        depot = inst.get("depot")
        if depot is None:
            # Standard problems/cvrp.py stores depot at index 0 of coordinates
            depot = coords[0]
            cust_coords = coords[1:]
            raw_demands = list(inst["demands"])[1:] if len(inst["demands"]) == len(coords) else list(inst["demands"])
        else:
            cust_coords = coords
            raw_demands = list(inst["demands"])
        out.append({
            "instance_id": str(inst.get("instance_id") or f"session_inst_{idx:03d}"),
            "size": len(cust_coords),
            "depot": list(depot),
            "customer_coordinates": [list(pt) for pt in cust_coords],
            "demands": [float(d) for d in raw_demands],
            "capacity": float(inst["capacity"]),
        })
    return out


class _SessionTrackedDynamicProblem(DynamicInterfaceProblem):
    """DynamicInterfaceProblem that mirrors every evaluation into Session SQLite & evaluations.jsonl."""

    def __init__(
        self,
        *,
        session: dict[str, Any],
        problem_id: str,
        suite_hash: str,
        evaluator_hash: str,
        metric_spec_hash: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(suite_hash=suite_hash, **kwargs)
        self.session = session
        self.session_problem_id = problem_id
        self.session_evaluator_hash = evaluator_hash
        self.session_metric_spec_hash = metric_spec_hash
        self.origin = "generated"
        self._seq = 0

    def evaluate_detailed(self, code_string: str) -> dict[str, Any]:
        self._seq += 1
        eval_id = uuid.uuid4().hex
        code_str = str(code_string)
        code_sha = sha256_text(code_str)
        origin = self.origin
        cand_id = origin if origin in {"baseline", "explicit_parent"} else f"m2_cand_{self._seq}"

        start_payload = {
            "code": code_str,
            "code_sha256": code_sha,
            "problem": self.session_problem_id,
            "entrypoint": self.design.hook_name,
            "evaluator_hash": self.session_evaluator_hash,
            "origin": origin,
            "candidate_id": cand_id,
            "revision": "original",
            "pid": os.getpid(),
            "suite_hash": self.suite_hash,
            "evaluation_id": eval_id,
            "metric_spec_hash": self.session_metric_spec_hash,
            "evaluation": None,
        }
        solver_event(self.session, start_payload)

        resp = super().evaluate_detailed(code_str)
        inst_objs = tuple(float(x) for x in (resp.get("instance_objectives") or []))
        exact_obj = (sum(inst_objs) / len(inst_objs)) if (resp.get("valid") and inst_objs) else None
        ev_result = EvaluationResult(
            valid=bool(resp.get("valid")),
            objective=exact_obj,
            instance_objectives=inst_objs,
            suite_hash=self.suite_hash,
            error_code=resp.get("error_code"),
            error_detail=resp.get("error_detail"),
            elapsed_seconds=float(resp.get("worker_wall_ms") or 0.0) / 1000.0,
        )
        done_payload = {
            **start_payload,
            "evaluation": ev_result.as_dict(),
            "template_id": self.design.template_id,
            "template_version": self.design.template_version,
            "template_source_sha256": self.tpl.template_source_sha256,
            "design_sha256": self.design.design_sha256,
        }
        if self.evaluation_log:
            ev_path = Path(self.evaluation_log)
            ev_path.parent.mkdir(parents=True, exist_ok=True)
            with self._log_lock:
                with ev_path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(done_payload, ensure_ascii=False, allow_nan=False) + "\n")
                    handle.flush()
        solver_event(self.session, done_payload)
        return resp

    def _append_eval_log(self, code_string: str, resp: Mapping[str, Any]) -> None:
        # Handled in Session-schema format inside evaluate_detailed above
        return None


def execute_m2_session_task(
    *,
    root: Path,
    task_id: str,
    row: Mapping[str, Any],
    rd: Mapping[str, Any],
    config: Mapping[str, Any],
    plan: Mapping[str, Any],
    suite: Mapping[str, Any],
    output: Path,
    wall_seconds: float,
    policy: Mapping[str, int],
) -> None:
    """Execute one Session round using Milestone 2's validated dynamic interface inside Session authority."""
    from eoh import LLMConfig
    from eoh.config import EoHConfig
    from eoh.eoh.eoh import EOH

    from agent_skill_loop.client import ProviderFailure, load_local_env
    from eoh_frozen.llm_bridge import OpenAIPathBridge

    round_dir = root / f"rounds/round_{rd['round_id']:04d}"
    design_path = round_dir / "interface_design.json"
    design = InterfaceDesign.from_dict(json.loads(design_path.read_text(encoding="utf-8")))
    tpl = get_template_spec(design.template_id, design.template_version)

    output.mkdir(parents=True, exist_ok=True)
    results_dir = output / "results"
    for sub in ("samples", "pops", "pops_best", "evaluation_starts", "exchanges"):
        (results_dir / sub).mkdir(parents=True, exist_ok=True)

    eval_log = results_dir / "evaluations.jsonl"
    req_log = results_dir / "requests.jsonl"
    instances = _normalize_session_suite_instances(suite)
    suite_hash = str(row["suite_hash"])
    eval_hash = str(row["evaluator_hash"])
    metric_hash = row["metric_spec_hash"] if "metric_spec_hash" in row.keys() else None
    session_ref = {"root": str(root), "task_id": task_id}

    round_context_text = (root / rd["round_context_ref"]).read_text(encoding="utf-8") if rd["round_context_ref"] else ""
    kb_clue = KB_ROUND_CONTEXT_BY_TEMPLATE.get(design.template_id, "")
    combined_ctx = (round_context_text + "\n\n" + kb_clue).strip() if kb_clue else round_context_text

    task = _SessionTrackedDynamicProblem(
        session=session_ref,
        problem_id=str(row["problem"]),
        suite_hash=suite_hash,
        evaluator_hash=eval_hash,
        metric_spec_hash=metric_hash,
        design=design,
        instances=instances,
        suite_id=f"session_{row['problem']}",
        candidate_timeout_s=float(row["solver_timeout"]),
        instance_time_budget_ms=500.0,
        evaluation_log=eval_log,
        round_context=combined_ctx,
    )

    # Evaluate template baseline hook first
    task.origin = "baseline"
    baseline_resp = task.evaluate_detailed(design.baseline_hook_code)
    task.origin = "generated"

    seed_path = output / "seeds" / "baseline_seed.json"
    seed_path.parent.mkdir(parents=True, exist_ok=True)
    seed_path.write_text(
        json.dumps([{"algorithm": f"Baseline hook for {design.template_id}/{design.template_version}.", "code": design.baseline_hook_code}], indent=2) + "\n",
        encoding="utf-8",
    )

    endpoint = str(row["eoh_endpoint"])
    model = str(row["eoh_model"])
    api_key_env = str(row["eoh_api_key_env"])
    request_timeout = float(row["request_timeout"])
    use_mock = endpoint.startswith("mock://") or os.environ.get("AGENT_SKILL_M2_MOCK") == "1"

    bridge = None
    mock_srv = None
    if use_mock:
        mock_srv = MockEoHLLMServer(DEFAULT_MOCK_MERGE_CANDIDATES, request_log=req_log)
        local_url = mock_srv.start()
    else:
        class _ResilientSessionBridge(OpenAIPathBridge):
            def _forward_serial(self, prompt: str, *, purpose: str | None = None) -> str:
                last_exc: Exception | None = None
                for attempt in range(3):
                    try:
                        return super()._forward_serial(prompt, purpose=purpose)
                    except ProviderFailure as exc:
                        last_exc = exc
                        transient = (
                            exc.error_code in {"provider_connectivity_or_protocol_error", "request_deadline"}
                            or exc.status == 429
                            or (isinstance(exc.status, int) and 500 <= exc.status < 600)
                        )
                        if transient and attempt < 2:
                            self.terminal = False
                            self.last_error = None
                            time.sleep(2.0 * (attempt + 1))
                            continue
                        raise
                assert last_exc is not None
                raise last_exc

        load_local_env()
        api_key = os.environ.get(api_key_env, "").strip()
        if not api_key:
            summary = {
                "problem": str(row["problem"]),
                "status": "provider_failed",
                "stop_reason": "provider_error",
                "provider_error_code": f"missing_api_key:{api_key_env}",
                "loop_completed": False,
            }
            _atomic_write_text(output / "summary.json", json.dumps(summary, indent=2) + "\n")
            return
        budget = SessionRequestBudget(str(root), task_id)
        bridge = _ResilientSessionBridge(
            endpoint,
            api_key,
            model,
            timeout=request_timeout,
            budget=budget,
            request_log=req_log,
            wall_seconds=wall_seconds,
            problem=f"{design.template_id}/{design.template_version}",
        )
        local_url = bridge.start()

    status = "completed"
    stop_reason = "eoh_completed"
    loop_completed = True
    try:
        llm_cfg = LLMConfig(use_local=True, local_url=local_url, timeout=int(request_timeout) + 5)
        engine_cfg = EoHConfig(
            llm=llm_cfg,
            pop_size=int(policy["pop_size"]),
            n_pop=int(policy["n_pop"]),
            operators=["e1", "e2", "m1", "m2"],
            max_sample_nums=int(policy["max_sample_nums"]),
            num_samplers=1,
            num_evaluators=1,
            use_seed=True,
            seed_path=str(seed_path),
            output_dir=str(output),
        )
        engine = EOH(engine_cfg, task)
        base_seed = int(config.get("search_seed", config["suite_generation"]["seed"]))
        s_seed = base_seed + int(rd["round_id"]) - 1
        random.seed(s_seed)
        np.random.seed(s_seed % (2**32))
        engine.run()
    except Exception as exc:
        msg = str(exc)
        if "budget_exhausted" in msg or "request_limit" in msg:
            status = "stopped"
            stop_reason = "request_limit"
        else:
            status = "engine_failed"
            stop_reason = "engine_error"
            loop_completed = False
    finally:
        if mock_srv is not None:
            mock_srv.stop()
        if bridge is not None:
            bridge.stop()

    # Read durable evaluations and export best valid generated skill + FrozenInterfaceSolver manifest
    rows = [json.loads(line) for line in eval_log.read_text(encoding="utf-8").splitlines() if line.strip()] if eval_log.is_file() else []
    gen_valid = [
        r for r in rows
        if r.get("origin") == "generated"
        and isinstance(r.get("evaluation"), dict)
        and r["evaluation"].get("valid") is True
        and r["evaluation"].get("objective") is not None
    ]
    best_rel = None
    frozen_rel = None
    if gen_valid:
        best = min(gen_valid, key=lambda r: float(r["evaluation"]["objective"]))
        ev = best["evaluation"]
        skill_dir = output / "skills" / "best_generated"
        sv = SkillVersion(
            version_id=f"m2_r{rd['round_id']:04d}_{best['code_sha256'][:10]}",
            problem=str(row["problem"]),
            entrypoint=design.hook_name,
            code=str(best["code"]),
            code_sha256=str(best["code_sha256"]),
            parent_version_id=None,
            suite_hash=suite_hash,
            evaluator_hash=eval_hash,
            valid=True,
            mean_objective=float(ev["objective"]),
            instance_objectives=tuple(float(x) for x in ev.get("instance_objectives") or ()),
            source_attempt_id=None,
            description=f"Session M2 evolved {design.template_id}/{design.template_version}:{design.hook_name}",
            search_policy_id="official_eoh",
            search_policy_version=EOH_COMMIT,
            origin="generated",
            metric_spec_hash=metric_hash,
        )
        save_skill(skill_dir, sv)
        best_rel = "skills/best_generated"

        frozen = FrozenInterfaceSolver(
            solver_id=f"session_r{rd['round_id']:04d}_{design.template_id}_{best['code_sha256'][:8]}",
            display_name=f"Session R{rd['round_id']} · {design.template_id}",
            problem_family=design.problem_family,
            paradigm=design.paradigm,
            template_id=design.template_id,
            template_version=design.template_version,
            template_source_sha256=tpl.template_source_sha256,
            postprocess_mode=design.postprocess_mode,
            template_options=dict(design.template_options),
            hook_name=design.hook_name,
            hook_code=str(best["code"]),
            hook_code_sha256=str(best["code_sha256"]),
            design_sha256=design.design_sha256,
            origin_run=str(output),
            kb_release_id="20261122-main-co-workbench-m15",
            kb_entry_id=design.cited_kb_ids[0] if design.cited_kb_ids else None,
            cited_kb_ids=design.cited_kb_ids,
            diagnostic_ref=design.diagnostic_ref,
            description=sv.description,
        )
        _atomic_write_text(
            output / "frozen_solver_manifest.json",
            json.dumps(frozen.to_dict(), ensure_ascii=False, indent=2) + "\n",
        )
        frozen_rel = "frozen_solver_manifest.json"

    summary = {
        "problem": str(row["problem"]),
        "search": "official_eoh",
        "interface_mode": "m2_dynamic_interface",
        "template_id": design.template_id,
        "template_version": design.template_version,
        "template_source_sha256": tpl.template_source_sha256,
        "design_sha256": design.design_sha256,
        "eoh_commit": EOH_COMMIT,
        "suite_hash": suite_hash,
        "evaluator_hash": eval_hash,
        "status": status,
        "stop_reason": stop_reason,
        "loop_completed": loop_completed,
        "baseline": baseline_resp.get("objective"),
        "best_generated_path": best_rel,
        "exported_skill": best_rel,
        "frozen_solver_manifest": frozen_rel,
    }
    _atomic_write_text(output / "summary.json", json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
