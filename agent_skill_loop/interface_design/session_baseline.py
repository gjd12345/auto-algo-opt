"""Unified Session baseline freeze & fresh-worker re-evaluation across CVRP/TSP/OBP/BPP."""

from __future__ import annotations

import hashlib
import json
import math
import uuid
from pathlib import Path
from typing import Any, Mapping, Sequence

from agent_skill_loop import session_runtime as db
from agent_skill_loop.benchmark.catalog import load_profile_suite
from agent_skill_loop.cvrp_workbench import m31_suites as m31
from agent_skill_loop.cvrp_workbench.suites import BENCHMARK_ID, load_m31_suite
from agent_skill_loop.interface_design.blind_eval_m32 import (
    assert_milestone_suite_allowed_for_interactive_role,
    assert_milestone_suite_not_blind,
)
from agent_skill_loop.interface_design.contracts import FrozenInterfaceSolver, sha256_text
from agent_skill_loop.interface_design.planner import build_design_for_template
from agent_skill_loop.interface_design.runtime import (
    derive_outer_timeout_s,
    evaluate_frozen_interface_solver,
    resolve_problem_adapter,
)
from agent_skill_loop.interface_design.templates import get_template_spec


_DEFAULT_TEMPLATE_BY_PROBLEM: dict[str, tuple[str, str]] = {
    "cvrp_construct": ("cvrp_parallel_merge_static", "v1"),
    "tsp_construct": ("tsp_constructive_step", "v1"),
    "obp_online": ("obp_online_priority", "v1"),
    "bpp_offline": ("bpp_offline_reorder_repack", "v1"),
}

_PROBLEM_FAMILY_TO_PROBLEM_ID = {
    "cvrp": "cvrp_construct",
    "tsp": "tsp_construct",
    "obp": "obp_online",
    "bpp": "bpp_offline",
}


def load_dev_or_public_suite(
    suite_id: str,
    *,
    split: str = "dev_train",
    role: str = "interactive_sandbox",
) -> dict[str, Any]:
    """Load any registered public workbench/M3.1 suite after role & blind checks."""
    assert_milestone_suite_not_blind(suite_id)
    assert_milestone_suite_allowed_for_interactive_role(suite_id, role=role)
    if suite_id in m31.M31_SUITE_KEYS:
        suite = load_m31_suite(suite_id, role=role)
        family, m31_split = m31.M31_SUITE_KEYS[suite_id]
        problem_id = m31.M31_PROBLEM_IDS[family]
        return {
            **suite,
            "problem": problem_id,
            "suite_id": suite_id,
            "split": "dev_train" if m31_split == "dev" else m31_split,
            "content_hash": m31.m31_sha256(suite["instances"]),
        }
    target_split = split
    if suite_id in {"tsp_ext_tsplib_euc2d", "obp_ext_bpplib"} and target_split == "dev_train":
        target_split = "heldout"
    suite = load_profile_suite(BENCHMARK_ID, suite_id, split=target_split)
    assert_milestone_suite_allowed_for_interactive_role(suite_id, suite, role=role)
    return {**suite, "suite_id": suite_id}


def ensure_baseline_tables(con) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS session_baselines (
            baseline_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            round_id INTEGER,
            problem_family TEXT NOT NULL,
            protocol_id TEXT NOT NULL,
            template_id TEXT NOT NULL,
            template_version TEXT NOT NULL,
            template_source_sha256 TEXT NOT NULL,
            bundle_hash TEXT,
            suite_id TEXT NOT NULL,
            suite_content_sha256 TEXT NOT NULL,
            solve_deadline_ms REAL NOT NULL,
            manifest_ref TEXT NOT NULL,
            manifest_sha256 TEXT NOT NULL,
            created_at_utc TEXT NOT NULL
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS baseline_re_evals (
            re_eval_id TEXT PRIMARY KEY,
            baseline_id TEXT NOT NULL,
            run_id TEXT NOT NULL,
            operation_id TEXT NOT NULL UNIQUE,
            replicate_id TEXT NOT NULL,
            suite_id TEXT NOT NULL,
            protocol_id TEXT NOT NULL,
            solve_deadline_ms REAL NOT NULL,
            matched_reference INTEGER NOT NULL CHECK (matched_reference IN (0,1)),
            completion_rate REAL NOT NULL,
            mean_objective REAL,
            report_ref TEXT NOT NULL,
            report_sha256 TEXT NOT NULL,
            created_at_utc TEXT NOT NULL,
            FOREIGN KEY (baseline_id) REFERENCES session_baselines(baseline_id) ON DELETE CASCADE
        )
        """
    )


def _extract_record_objective(record: Mapping[str, Any]) -> float | int | None:
    if record.get("valid") is not True:
        return None
    for key in ("objective", "tour_length", "bins_used"):
        val = record.get(key)
        if val is not None and not isinstance(val, bool) and isinstance(val, (int, float)) and math.isfinite(float(val)):
            return val
    return None


def _evaluate_frozen_solver_on_instances(
    solver: FrozenInterfaceSolver,
    instances: Sequence[Mapping[str, Any]],
    *,
    distance_convention: str,
    vehicle_limit_policy: str,
    solve_deadline_ms: float,
    protocol_id: str,
) -> dict[str, Any]:
    outer_s = derive_outer_timeout_s(1, solve_deadline_ms, minimum_s=max(5.0, solve_deadline_ms / 1000.0 + 3.0))
    records: list[dict[str, Any]] = []
    objectives: list[float] = []
    completed_bitmap: list[int] = []
    per_instance: list[dict[str, Any]] = []
    for inst in instances:
        rec = evaluate_frozen_interface_solver(
            solver,
            inst,
            distance_convention=distance_convention,
            vehicle_limit_policy=vehicle_limit_policy,
            solve_deadline_ms=solve_deadline_ms,
            outer_timeout_s=outer_s,
            protocol_id=protocol_id,
        )
        records.append(rec)
        obj = _extract_record_objective(rec)
        comp = bool(rec.get("valid") is True and rec.get("completed") is True and obj is not None)
        completed_bitmap.append(1 if comp else 0)
        if obj is not None:
            objectives.append(float(obj))
        per_instance.append({
            "instance_id": str(inst.get("instance_id") or ""),
            "protocol_id": rec.get("protocol_id"),
            "valid": bool(rec.get("valid")),
            "completed": comp,
            "objective": obj,
            "error_code": rec.get("error_code"),
            "solve_ms": rec.get("solve_ms"),
            "timeout_kind": rec.get("timeout_kind"),
        })
    total = len(instances)
    completed_count = sum(completed_bitmap)
    mean_obj = (sum(objectives) / len(objectives)) if (len(objectives) == total and total > 0) else None
    return {
        "protocol_id": protocol_id,
        "instance_count": total,
        "completed_count": completed_count,
        "completion_rate": round(completed_count / max(1, total), 6),
        "all_completed": bool(total > 0 and completed_count == total),
        "mean_objective": round(mean_obj, 8) if mean_obj is not None else None,
        "completion_bitmap": completed_bitmap,
        "ordered_instance_ids": [row["instance_id"] for row in per_instance],
        "per_instance": per_instance,
        "records": records,
    }


def _objectives_match(
    actual: float | int | None,
    expected: float | int | None,
    *,
    distance_convention: str,
    problem_family: str,
    rel_tol: float,
    abs_tol: float,
) -> bool:
    if actual is None or expected is None:
        return actual is None and expected is None
    if problem_family in {"obp", "bpp"} or distance_convention in {"euc_2d_int", "tsplib_euc_2d", "not_applicable"}:
        if type(actual) is int and type(expected) is int:
            return actual == expected
        return math.isclose(float(actual), float(expected), rel_tol=0.0, abs_tol=1e-12)
    return math.isclose(float(actual), float(expected), rel_tol=rel_tol, abs_tol=abs_tol)


def freeze_session_baseline(
    *,
    run: Path,
    operation_id: str,
    expected_state_version: int,
    baseline_id: str | None = None,
    round_id: int | None = None,
    template_id: str | None = None,
    template_version: str = "v1",
    postprocess_mode: str = "none",
    time_budget_ms: float | None = None,
    suite_id: str | None = None,
    expected_run_id: str | None = None,
) -> dict[str, Any]:
    """Freeze a baseline executable, protocol, and fresh-worker dev receipts inside a Session."""
    from agent_skill_loop.session_actions import begin, fail, opened, receipt, save

    action = "freeze-baseline"
    with opened(run, action, expected_run_id) as (root, con):
        config = json.loads((root / "config_frozen.json").read_text(encoding="utf-8"))
        dev_suite = json.loads((root / "dev_suite.json").read_text(encoding="utf-8"))
        with db._transaction(con):
            ensure_baseline_tables(con)
            row, rd, ih, prev_receipt = begin(
                con,
                action,
                operation_id,
                expected_state_version,
                {
                    "baseline_id": baseline_id,
                    "round_id": round_id,
                    "template_id": template_id,
                    "template_version": template_version,
                    "postprocess_mode": postprocess_mode,
                    "time_budget_ms": time_budget_ms,
                    "suite_id": suite_id,
                },
            )
            if prev_receipt is not None:
                return prev_receipt

            chosen_tid = template_id
            chosen_tver = template_version
            chosen_pp = postprocess_mode
            chosen_opts: dict[str, Any] = {}
            chosen_budget_ms = float(time_budget_ms) if time_budget_ms is not None else 500.0
            if chosen_tid is None:
                target_round_id = round_id if round_id is not None else rd["round_id"]
                target_round = con.execute(
                    "SELECT * FROM rounds WHERE run_id=? AND round_id=?",
                    (row["run_id"], target_round_id),
                ).fetchone()
                if target_round is not None and target_round["normalized_plan_ref"]:
                    plan_doc = json.loads((root / target_round["normalized_plan_ref"]).read_text(encoding="utf-8"))
                    sel = plan_doc.get("interface_selection") if isinstance(plan_doc, Mapping) else None
                    if isinstance(sel, Mapping):
                        chosen_tid = str(sel["template_id"])
                        chosen_tver = str(sel.get("template_version", "v1"))
                        chosen_pp = str(sel.get("postprocess_mode", "none"))
                        chosen_opts = dict(sel.get("template_options") or {})
                        if time_budget_ms is None and sel.get("time_budget_ms") is not None:
                            chosen_budget_ms = float(sel["time_budget_ms"])
            if chosen_tid is None:
                default_pair = _DEFAULT_TEMPLATE_BY_PROBLEM.get(str(row["problem"]))
                if default_pair is None:
                    fail("INVALID_ARGUMENT", action, f"No default template for problem={row['problem']}")
                chosen_tid, chosen_tver = default_pair

            tpl = get_template_spec(chosen_tid, chosen_tver)
            adapter = resolve_problem_adapter(tpl)
            design = build_design_for_template(
                chosen_tid,
                chosen_tver,
                design_id=f"baseline_{chosen_tid}_{chosen_tver}",
                postprocess_mode=chosen_pp,
                rationale="Session baseline freeze.",
            )
            bid = baseline_id or f"baseline_{tpl.problem_family}_{chosen_tid}_{chosen_tver}"
            existing_b = con.execute("SELECT * FROM session_baselines WHERE baseline_id=?", (bid,)).fetchone()
            if existing_b is not None:
                fail("BASELINE_ALREADY_EXISTS", action, f"baseline_id={bid} already frozen")

            if suite_id is not None:
                suite_obj = load_dev_or_public_suite(suite_id, role="interactive_sandbox")
                resolved_suite_id = suite_id
            else:
                resolved_suite_id = str(dev_suite.get("suite_id") or row["benchmark_profile"] or f"session_{row['problem']}")
                suite_obj = dev_suite

            instances = list(suite_obj["instances"])
            dist_conv = str(suite_obj.get("distance_convention") or ("euc_2d_float" if tpl.problem_family in {"cvrp", "tsp"} else "not_applicable"))
            veh_pol = str(suite_obj.get("vehicle_limit_policy") or ("unconstrained" if tpl.problem_family == "cvrp" else "not_applicable"))
            suite_content_sha = hashlib.sha256(
                json.dumps(instances, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
            ).hexdigest()

            solver = FrozenInterfaceSolver(
                solver_id=bid,
                display_name=f"Baseline {tpl.problem_family}:{chosen_tid}/{chosen_tver}",
                problem_family=tpl.problem_family,
                paradigm=tpl.paradigm,
                template_id=tpl.template_id,
                template_version=tpl.template_version,
                template_source_sha256=tpl.template_source_sha256,
                postprocess_mode=chosen_pp,
                template_options=chosen_opts,
                hook_name=tpl.hook_name,
                hook_code=tpl.default_baseline_hook_code,
                hook_code_sha256=sha256_text(tpl.default_baseline_hook_code),
                design_sha256=design.design_sha256,
                origin_run=str(row["run_id"]),
                kb_release_id="session_baseline",
                kb_entry_id=None,
                description=f"Frozen Session baseline for {tpl.problem_family} under {adapter.protocol_id}.",
                default_budget_ms=chosen_budget_ms,
                protocol_id=adapter.protocol_id,
                hook_specs=tpl.hook_specs,
                hook_implementations=tpl.baseline_implementations() if tpl.hook_specs else {},
            )
            baseline_eval = _evaluate_frozen_solver_on_instances(
                solver,
                instances,
                distance_convention=dist_conv,
                vehicle_limit_policy=veh_pol,
                solve_deadline_ms=chosen_budget_ms,
                protocol_id=adapter.protocol_id,
            )
            if not baseline_eval["all_completed"]:
                fail("BASELINE_INCOMPLETE", action, f"Baseline failed to complete all {len(instances)} instances")

            artifact = {
                "schema_version": "m31-session-baseline/v1",
                "baseline_id": bid,
                "run_id": str(row["run_id"]),
                "round_id": int(round_id if round_id is not None else rd["round_id"]),
                "problem": str(row["problem"]),
                "problem_family": tpl.problem_family,
                "protocol_id": adapter.protocol_id,
                "template_id": tpl.template_id,
                "template_version": tpl.template_version,
                "template_source_sha256": tpl.template_source_sha256,
                "evaluator_hash": str(row["evaluator_hash"]),
                "suite_id": resolved_suite_id,
                "suite_content_sha256": suite_content_sha,
                "ordered_instance_ids": baseline_eval["ordered_instance_ids"],
                "distance_convention": dist_conv,
                "vehicle_limit_policy": veh_pol,
                "solve_deadline_ms": chosen_budget_ms,
                "metric_direction": "minimize",
                "frozen_solver": solver.to_dict(),
                "baseline_eval": {k: v for k, v in baseline_eval.items() if k != "records"},
            }
            ref = f"baselines/{bid}.json"
            sha = save(root, ref, artifact)
            con.execute(
                """
                INSERT INTO session_baselines(
                    baseline_id, run_id, round_id, problem_family, protocol_id,
                    template_id, template_version, template_source_sha256, bundle_hash,
                    suite_id, suite_content_sha256, solve_deadline_ms, manifest_ref,
                    manifest_sha256, created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    bid,
                    row["run_id"],
                    artifact["round_id"],
                    tpl.problem_family,
                    adapter.protocol_id,
                    tpl.template_id,
                    tpl.template_version,
                    tpl.template_source_sha256,
                    solver.bundle_hash,
                    resolved_suite_id,
                    suite_content_sha,
                    chosen_budget_ms,
                    ref,
                    sha,
                    db._utc_now(),
                ),
            )
            result = receipt(
                con,
                row,
                rd,
                action,
                operation_id,
                ih,
                {
                    "baseline_id": bid,
                    "baseline_ref": ref,
                    "baseline_sha256": sha,
                    "problem_family": tpl.problem_family,
                    "protocol_id": adapter.protocol_id,
                    "suite_id": resolved_suite_id,
                    "completion_rate": baseline_eval["completion_rate"],
                    "mean_objective": baseline_eval["mean_objective"],
                },
            )
        db.flush_audit(root)
        return result


def re_eval_session_baseline(
    *,
    run: Path,
    operation_id: str,
    expected_state_version: int,
    baseline_id: str,
    suite_id: str | None = None,
    protocol_id: str | None = None,
    time_budget_ms: float | None = None,
    distance_convention: str | None = None,
    replicate_id: str = "rep_1",
    rel_tol: float = 1e-9,
    abs_tol: float = 1e-9,
    expected_run_id: str | None = None,
) -> dict[str, Any]:
    """Re-evaluate a frozen Session baseline in a fresh worker and verify protocol/objective parity."""
    from agent_skill_loop.session_actions import begin, fail, local, opened, receipt, save

    action = "re-eval-baseline"
    with opened(run, action, expected_run_id) as (root, con):
        dev_suite = json.loads((root / "dev_suite.json").read_text(encoding="utf-8"))
        with db._transaction(con):
            ensure_baseline_tables(con)
            row, rd, ih, prev_receipt = begin(
                con,
                action,
                operation_id,
                expected_state_version,
                {
                    "baseline_id": baseline_id,
                    "suite_id": suite_id,
                    "protocol_id": protocol_id,
                    "time_budget_ms": time_budget_ms,
                    "distance_convention": distance_convention,
                    "replicate_id": replicate_id,
                },
            )
            if prev_receipt is not None:
                return prev_receipt

            b_row = con.execute(
                "SELECT * FROM session_baselines WHERE baseline_id=? AND run_id=?",
                (baseline_id, row["run_id"]),
            ).fetchone()
            if b_row is None:
                fail("BASELINE_NOT_FOUND", action, f"unknown baseline_id={baseline_id}")
            manifest_text = local(root, b_row["manifest_ref"]).read_text(encoding="utf-8")
            if db._sha256(manifest_text) != b_row["manifest_sha256"]:
                fail("EVIDENCE_INTEGRITY_FAILED", action, "baseline manifest hash mismatch")
            artifact = json.loads(manifest_text)

            target_protocol = protocol_id or artifact["protocol_id"]
            if target_protocol != artifact["protocol_id"]:
                fail("PROTOCOL_MISMATCH", action, f"protocol mismatch: {target_protocol} != {artifact['protocol_id']}")

            target_suite_id = suite_id or artifact["suite_id"]
            if target_suite_id == artifact["suite_id"] and target_suite_id == str(dev_suite.get("suite_id") or row["benchmark_profile"] or target_suite_id):
                suite_obj = dev_suite
            else:
                suite_obj = load_dev_or_public_suite(target_suite_id, role="interactive_sandbox")

            instances = list(suite_obj["instances"])
            suite_content_sha = hashlib.sha256(
                json.dumps(instances, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
            ).hexdigest()
            same_suite = (target_suite_id == artifact["suite_id"])
            if same_suite and suite_content_sha != artifact["suite_content_sha256"]:
                fail("SUITE_CONTENT_MISMATCH", action, "reloaded suite content hash mismatch")

            solver = FrozenInterfaceSolver.from_dict(artifact["frozen_solver"])
            budget_ms = float(time_budget_ms if time_budget_ms is not None else artifact["solve_deadline_ms"])
            dist_conv = str(distance_convention or suite_obj.get("distance_convention") or artifact["distance_convention"])
            veh_pol = str(suite_obj.get("vehicle_limit_policy") or artifact["vehicle_limit_policy"])
            replay = _evaluate_frozen_solver_on_instances(
                solver,
                instances,
                distance_convention=dist_conv,
                vehicle_limit_policy=veh_pol,
                solve_deadline_ms=budget_ms,
                protocol_id=target_protocol,
            )
            matched_reference = True
            mismatches: list[str] = []
            if same_suite and abs(budget_ms - float(artifact["solve_deadline_ms"])) <= 1e-9 and dist_conv == artifact["distance_convention"]:
                ref_eval = artifact["baseline_eval"]
                if replay["ordered_instance_ids"] != ref_eval["ordered_instance_ids"]:
                    matched_reference = False
                    mismatches.append("instance_ids_mismatch")
                if replay["completion_bitmap"] != ref_eval["completion_bitmap"]:
                    matched_reference = False
                    mismatches.append("completion_bitmap_mismatch")
                for actual_row, expected_row in zip(replay["per_instance"], ref_eval["per_instance"]):
                    if not _objectives_match(
                        actual_row["objective"],
                        expected_row["objective"],
                        distance_convention=dist_conv,
                        problem_family=artifact["problem_family"],
                        rel_tol=rel_tol,
                        abs_tol=abs_tol,
                    ):
                        matched_reference = False
                        mismatches.append(f"objective_mismatch:{actual_row['instance_id']}")
                        break
            if not matched_reference:
                fail("BASELINE_REPLAY_PARITY_FAILED", action, ",".join(mismatches))

            report_payload = {
                "schema_version": "m31-baseline-re-eval/v1",
                "baseline_id": baseline_id,
                "operation_id": operation_id,
                "replicate_id": replicate_id,
                "suite_id": target_suite_id,
                "suite_content_sha256": suite_content_sha,
                "protocol_id": target_protocol,
                "distance_convention": dist_conv,
                "solve_deadline_ms": budget_ms,
                "matched_reference": matched_reference,
                "mismatches": mismatches,
                "evaluation": {k: v for k, v in replay.items() if k != "records"},
            }
            report_ref = f"baselines/re_evals/{baseline_id}_{replicate_id}_{operation_id}.json"
            report_sha = save(root, report_ref, report_payload)
            re_eval_id = f"reeval_{uuid.uuid4().hex}"
            con.execute(
                """
                INSERT INTO baseline_re_evals(
                    re_eval_id, baseline_id, run_id, operation_id, replicate_id, suite_id,
                    protocol_id, solve_deadline_ms, matched_reference, completion_rate,
                    mean_objective, report_ref, report_sha256, created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    re_eval_id,
                    baseline_id,
                    row["run_id"],
                    operation_id,
                    replicate_id,
                    target_suite_id,
                    target_protocol,
                    budget_ms,
                    1 if matched_reference else 0,
                    replay["completion_rate"],
                    replay["mean_objective"],
                    report_ref,
                    report_sha,
                    db._utc_now(),
                ),
            )
            result = receipt(
                con,
                row,
                rd,
                action,
                operation_id,
                ih,
                {
                    "re_eval_id": re_eval_id,
                    "baseline_id": baseline_id,
                    "replicate_id": replicate_id,
                    "suite_id": target_suite_id,
                    "protocol_id": target_protocol,
                    "matched_reference": matched_reference,
                    "all_completed": replay["all_completed"],
                    "completion_rate": replay["completion_rate"],
                    "mean_objective": replay["mean_objective"],
                    "report_ref": report_ref,
                    "report_sha256": report_sha,
                },
            )
        db.flush_audit(root)
        return result
