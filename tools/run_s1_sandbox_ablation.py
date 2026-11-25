"""Run the single-variable CVRP numerical sandbox ablation."""

from __future__ import annotations

import argparse
import ast
from collections import Counter
from collections.abc import Mapping, Sequence
from itertools import combinations
import json
import math
import os
from pathlib import Path
import re
import secrets
from statistics import stdev
import sys
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from agent_skill_loop.client import ProviderFailure, load_local_env
from agent_skill_loop.cvrp_workbench.solvers import evaluate_algorithm_on_instance
from agent_skill_loop.interface_design.blind_commitment import (
    _CAPACITY_LEVELS, _gen_coords, _gen_demands, _seeded_rng, _sha256_payload,
    require_external_custody_path,
)
from agent_skill_loop.interface_design.blind_eval import (
    paired_bootstrap_comparison, paired_wilcoxon_signed_rank,
)
from agent_skill_loop.interface_design.blind_eval_m3 import holm_bonferroni_adjust
from agent_skill_loop.interface_design.blind_eval_m32 import _cell, _read_pinned, _write_once
from agent_skill_loop.interface_design.blind_eval_m5 import _blind_design_rows, build_m5_public_record
from agent_skill_loop.interface_design.contracts import FrozenInterfaceSolver
from agent_skill_loop.interface_design.session_baseline import load_dev_or_public_suite
from research_agent.contracts import AgentCheckpoint, AgentConfig, atomic_write_json, atomic_write_text
from research_agent.loop import run_research_agent
from research_agent.tools.math_sandbox import _has_finite_numeric_evidence
from tools.run_b4_intron_ablation import (
    EXTERNAL_CVRPLIB_SUITES, evaluate_public_frozen_solver, validate_frozen_solver,
)
from tools.run_m32_scaling import RESUMABLE_EXIT_CODE
from tools.run_m5_trajectory_control import (
    POSTPROCESS_MODES, TEMPLATES, TERMINAL_PHASES, _completed, _fleet_metrics, _indexed, _json,
    _penalized, _read_champion as _read_budget_champion, _sha256,
)

ARMS = {
    "arm_s1_0_free_tool": "off",
    "arm_s1_1_slice_only": "slice_only",
    "arm_s1_2_sandbox_only": "sandbox_only",
}
MODELS = ("DeepSeek-V4.1-Flash", "Qwen4-Max")
SEEDS = tuple(range(20261124, 20261129))
RELEASE_ID = "20261124-main-co-workbench-m4"
RELEASE_SHA256 = "3c9e5507de4a503bb7f9a577dac4dbbc164ab9cb3d1cc5ec193ba39112003b3f"
REQUEST_CAP = 36
DEADLINE_MS = 500.0
DEV_SUITE_ID = "cvrp_dev_hetero_24"
BLIND_SUITE_ID = "cvrp_s1_sandbox_blind_120"
SUITE_COUNTS = {BLIND_SUITE_ID: 120, "cvrp_ext_cvrplib_abp_74": 74, "cvrp_ext_cvrplib_x_100": 100}
DEFAULT_OUTPUT = REPO / "experiments" / "milestone5_s1_sandbox_ablation"
DEFAULT_CUSTODY = Path.home() / ".agent_skill_custody" / "s1_sandbox"
PROTOCOL = "s1_pre_blind_protocol.json"
COMMITMENT = f"{BLIND_SUITE_ID}_commitment.json"
LOCK = "s1_roster_lock.json"
EVALUATION = "s1_evaluation.json"
AUDIT = "s1_script_audit.json"
PILOT_APPROVAL = "s1_pilot_approval.json"
REPORT = "s1_sandbox_ablation_report"
REF_FIELDS = ("artifact_ref", "artifact_sha256", "script_ref", "script_sha256")
FLEETS = ("free_fleet", "exact_k")
DENOMINATORS = ("common_completed", "penalized_2x")
_CELL_CONTRASTS = tuple((right, left) for left, right in combinations(ARMS, 2))


def _show(data: Mapping[str, Any]) -> None:
    print(json.dumps(data, ensure_ascii=False))


def _id(model: str, arm: str, seed: int) -> str:
    return f"{model}:{arm}:{seed}"


def _parts(cell: str) -> tuple[str, str, int]:
    model, arm, seed = cell.split(":")
    return model, arm, int(seed)


def _cells(phase: str, seeds: Sequence[int] | None = None) -> list[str]:
    models = MODELS[:1] if phase == "pilot" else MODELS
    defaults = SEEDS[:3] if phase == "pilot" else SEEDS
    return [_id(model, arm, seed) for model in models for seed in (seeds or defaults) for arm in ARMS]


def _relative_file(root: Path, ref: str) -> Path:
    candidate = Path(ref)
    path = (root / candidate).resolve()
    if candidate.is_absolute() or not path.is_relative_to(root.resolve()):
        raise ValueError("s1_artifact_path_outside_output")
    return path


def _publish_once(path: Path, payload: Mapping[str, Any]) -> None:
    if path.exists():
        if _json(path) != payload:
            raise ValueError(f"s1_existing_receipt_mismatch:{path.name}")
        return
    _write_once(path, payload)


def _custody(args: argparse.Namespace) -> Path:
    root = require_external_custody_path(args.custody_dir or DEFAULT_CUSTODY, repo_root=REPO)
    if args.mock and (root == DEFAULT_CUSTODY.resolve() or root in DEFAULT_CUSTODY.resolve().parents
                      or root.is_relative_to(DEFAULT_CUSTODY.resolve().parent)):
        raise ValueError("s1_mock_requires_isolated_external_custody")
    if any(part.casefold().startswith(".agent_skill_custody_") for part in root.parts):
        raise ValueError("s1_custody_must_use_its_own_root")
    return root


def _private_path(root: Path, filename: str) -> Path:
    path = require_external_custody_path(root / filename, repo_root=REPO)
    if path.parent != root:
        raise ValueError("s1_private_path_outside_custody")
    return path


def _seal(root: Path, commitment_path: Path) -> None:
    sealed_path = _private_path(root, f"{BLIND_SUITE_ID}_sealed.json")
    if sealed_path.exists() or commitment_path.exists():
        raise FileExistsError("s1_sealed_suite_or_commitment_already_exists")
    token = secrets.token_hex(32)
    instances = []
    for index, (size, spatial, depot, capacity, demand) in enumerate(_blind_design_rows()):
        cell = _cell(size, spatial, depot, capacity, demand)
        rng = _seeded_rng(token, f"{BLIND_SUITE_ID}/{cell}", index)
        instance = {
            "instance_id": f"s1blind_{cell}-{index:03d}",
            "cell": cell, "size": size, "spatial": spatial, "depot_style": depot,
            "capacity_level": capacity, "demand_dist": demand, "source_tag": BLIND_SUITE_ID,
            "protocol_id": "cvrp/v1",
            "depot": [0.5, 0.5] if depot == "centre" else [0.05, 0.95],
            "customer_coordinates": _gen_coords(spatial, rng, size),
            "demands": _gen_demands(demand, rng, size),
            "capacity": _CAPACITY_LEVELS[capacity],
        }
        reference = evaluate_algorithm_on_instance("nn", instance, record_trace=False)
        objective, fleet = reference["tour_length"], reference["route_count"]
        if (
            reference["valid"] is not True or type(objective) not in (int, float)
            or not math.isfinite(objective) or objective <= 0 or type(fleet) is not int or fleet <= 0
        ):
            raise RuntimeError("s1_nn_reference_failed")
        instance.update(reference_objective=objective, reference_kind="solver_reference", k_vehicles=fleet)
        instances.append(instance)
    metadata = {
        "suite_id": BLIND_SUITE_ID, "suite_role": "final_blind_acceptance",
        "exposure_status": "locked_s1_blind", "problem_family": "cvrp", "protocol_id": "cvrp/v1",
        "split": "blind", "distance_convention": "euc_2d_float", "vehicle_limit_policy": "unconstrained",
        "generator_version": "cvrp_s1_sandbox_blind_generator/v1",
        "generator_source_sha256": _sha256_payload([
            _sha256(Path(__file__).read_bytes()),
            _sha256(Path(_seeded_rng.__code__.co_filename).read_bytes()),
            _sha256(Path(_blind_design_rows.__code__.co_filename).read_bytes()),
        ]),
        "instance_count": len(instances), "suite_content_sha256": _sha256_payload(instances),
        "stratification_spec": {"by_cell": dict(Counter(row["cell"] for row in instances))},
        "reference_baseline": "nearest_neighbor", "exact_k_reference": "nearest_neighbor_route_count",
    }
    _write_once(sealed_path, {
        **metadata, "schema_version": "milestone-blind-sealed/v1",
        "sealed_seed_token": token, "instances": instances,
    })
    _write_once(commitment_path, {
        **metadata, "schema_version": "milestone-blind-commitment/v1", "commitment_status": "sealed",
        "instances": [
            {"instance_id": row["instance_id"], "cell": row["cell"], "instance_sha256": _sha256_payload(row)}
            for row in instances
        ],
    })


def _public_commitment(path: Path) -> dict[str, Any]:
    doc = _json(path)
    fields = {
        "suite_id", "suite_role", "exposure_status", "problem_family", "protocol_id", "split",
        "distance_convention", "vehicle_limit_policy", "generator_version", "generator_source_sha256",
        "instance_count", "suite_content_sha256", "stratification_spec", "reference_baseline",
        "exact_k_reference", "schema_version", "commitment_status", "instances",
    }
    if (
        set(doc) != fields
        or doc.get("suite_id") != BLIND_SUITE_ID or doc.get("schema_version") != "milestone-blind-commitment/v1"
        or doc.get("commitment_status") != "sealed" or doc.get("instance_count") != SUITE_COUNTS[BLIND_SUITE_ID]
        or len(doc.get("instances", [])) != SUITE_COUNTS[BLIND_SUITE_ID]
        or not re.fullmatch(r"[0-9a-f]{64}", doc.get("suite_content_sha256", ""))
        or any(set(row) != {"instance_id", "cell", "instance_sha256"} for row in doc["instances"])
    ):
        raise ValueError("invalid_s1_blind_commitment")
    return doc


def _protocol(args: argparse.Namespace) -> tuple[dict[str, Any], str]:
    path = args.out_dir / PROTOCOL
    data = path.read_bytes()
    doc = json.loads(data)
    expected = _protocol_payload(args, doc["commitment_sha256"])
    if doc != expected:
        raise ValueError("s1_pre_blind_protocol_mismatch")
    return doc, _sha256(data)


def _protocol_payload(args: argparse.Namespace, commitment_sha256: str) -> dict[str, Any]:
    return {
        "schema_version": "s1-pre-blind-protocol/v1",
        "commitment_sha256": commitment_sha256, "blind_suite_id": BLIND_SUITE_ID,
        "run_mode": "mock" if args.mock else "live",
        "arms": ARMS, "pilot_cells": _cells("pilot", args.seeds), "full_cells": _cells("full", args.seeds),
        "dev_suite_id": DEV_SUITE_ID, "request_cap": REQUEST_CAP, "solve_deadline_ms": DEADLINE_MS,
        "templates": list(TEMPLATES), "postprocess_modes": list(POSTPROCESS_MODES),
        "static_kb": {"release_id": RELEASE_ID, "manifest_sha256": RELEASE_SHA256},
        "pairwise_contrasts": [list(pair) for pair in _CELL_CONTRASTS],
        "denominators": list(DENOMINATORS), "bootstrap_replicates": 10000,
        "holm_family": ["suite_id", "model", "fleet", "denominator"],
        "endpoint": args.endpoint, "api_key_env": args.api_key_env,
        "request_timeout_s": args.request_timeout_s, "wall_seconds": args.wall_seconds,
    }


def cmd_seal_blind(args: argparse.Namespace) -> int:
    root = _custody(args)
    commitment_path = args.out_dir / COMMITMENT
    if commitment_path.resolve().is_relative_to(root):
        raise ValueError("s1_output_must_be_outside_custody")
    if not commitment_path.exists():
        _seal(root, commitment_path)
    doc = _public_commitment(commitment_path)
    if not _private_path(root, f"{BLIND_SUITE_ID}_sealed.json").is_file():
        raise FileNotFoundError("s1_custody_seal_missing")
    digest = _sha256(commitment_path.read_bytes())
    protocol = _protocol_payload(args, digest)
    _publish_once(args.out_dir / PROTOCOL, protocol)
    _show({"commitment_path": str(commitment_path), "instance_count": doc["instance_count"]})
    return 0


def _config(args: argparse.Namespace, cell: str) -> AgentConfig:
    model, arm, seed = _parts(cell)
    return AgentConfig(
        run_id=f"m5_s1_{model}_{arm}_s{seed}",
        output_dir=str(args.out_dir / "runs" / model / str(seed) / arm),
        arm_id=arm, search_seed=seed, planner_model=model, eoh_model=model,
        allowed_templates=TEMPLATES, allowed_postprocess_modes=POSTPROCESS_MODES,
        dev_suite_id=DEV_SUITE_ID, use_benchmark_dev_suite=True, dev_instance_count=24,
        max_rounds=8, total_request_cap=REQUEST_CAP, instance_time_budget_ms=DEADLINE_MS,
        strict_checkpoint_barriers=True, checkpoint_budgets=(REQUEST_CAP,),
        kb_enabled=True, kb_store_path=str(REPO / "knowledge_store" / "releases" / RELEASE_ID),
        pinned_kb_release_id=RELEASE_ID, pinned_kb_manifest_sha256=RELEASE_SHA256,
        stagnation_diagnostic_mode=ARMS[arm],
        endpoint=args.endpoint, api_key_env=args.api_key_env, mode="mock" if args.mock else "live",
        request_timeout_s=args.request_timeout_s, wall_seconds=args.wall_seconds,
    )


def _check_pilot_approval(args: argparse.Namespace, protocol: Mapping[str, Any], protocol_sha: str) -> None:
    if args.mock or args.phase == "pilot":
        return
    approval_path = args.out_dir / PILOT_APPROVAL
    if not approval_path.is_file():
        raise ValueError("run inspect-scripts --phase pilot --approve-pilot after reviewing the pilot audit")
    approval = _json(approval_path)
    approved = _read_pinned(args.out_dir / "s1_approved_pilot_audit.json", approval["audit_sha256"], "s1_pilot_audit")
    current = _audit_for_cells(args, protocol["pilot_cells"], protocol_sha)
    if approval.get("protocol_sha256") != protocol_sha or approved != current or not current["eligible_for_approval"]:
        raise ValueError("s1_pilot_approval_invalid")


def cmd_emit_mux(args: argparse.Namespace) -> int:
    protocol, digest = _protocol(args)
    _check_pilot_approval(args, protocol, digest)
    panes = []
    for cell in protocol[f"{args.phase}_cells"]:
        config = _config(args, cell)
        if (Path(config.output_dir) / "research_summary.json").is_file():
            continue
        model, arm, seed = _parts(cell)
        command = [
            sys.executable, str(Path(__file__).resolve()), "run-cell",
            "--out-dir", str(args.out_dir), "--phase", args.phase,
            "--model", model, "--arm", arm, "--seed", str(seed), "--resume",
            "--endpoint", args.endpoint, "--api-key-env", args.api_key_env,
            "--request-timeout-s", str(args.request_timeout_s), "--wall-seconds", str(args.wall_seconds),
        ]
        if args.mock:
            command.append("--mock")
        if args.seeds:
            command.extend(["--seeds", *map(str, args.seeds)])
        panes.append({"id": config.run_id, "command": command, "cwd": str(REPO)})
    path = args.manifest_path or args.out_dir / f"mux_s1_{args.phase}.json"
    atomic_write_json(path, {"panes": panes})
    _show({"manifest_path": str(path), "pane_count": len(panes)})
    return 0


def cmd_run_cell(args: argparse.Namespace) -> int:
    protocol, digest = _protocol(args)
    _check_pilot_approval(args, protocol, digest)
    cell = _id(args.model, args.arm, args.seed)
    if cell not in protocol[f"{args.phase}_cells"]:
        raise ValueError(f"s1_unregistered_cell:{cell}")
    if (args.out_dir / LOCK).exists():
        raise ValueError("s1_roster_is_already_locked")
    config = _config(args, cell)
    run_dir = Path(config.output_dir)
    if (run_dir / "research_summary.json").is_file():
        stored = _json(run_dir / "research_summary.json")
        if stored.get("final_phase") in TERMINAL_PHASES:
            _show({"cell": cell, "status": stored["final_phase"], "reused": True})
            return 0
    if not args.mock:
        load_local_env()
        if config.endpoint.startswith("mock://") or os.environ.get("AGENT_SKILL_M2_MOCK") == "1":
            raise ValueError("s1_live_run_has_mock_endpoint_or_environment")
    checkpoint = run_dir / "agent_checkpoint.json"
    if checkpoint.exists() and not args.resume:
        raise ValueError("s1_existing_run_requires_resume")
    try:
        summary = run_research_agent(config, resume=checkpoint.is_file())
    except ProviderFailure as exc:
        _show({"cell": cell, "status": "resumable", "reason": exc.error_code})
        return RESUMABLE_EXIT_CODE
    _show({"cell": cell, "status": summary["final_phase"]})
    return 0


def _audit_value(value: Any) -> Any:
    """Retain nonfinite outputs for inspection in a portable JSON document."""
    if type(value) is float and not math.isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {key: _audit_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_audit_value(item) for item in value]
    return value


def _sandbox_references(node: Any):
    if isinstance(node, Mapping):
        for key, value in node.items():
            if key in {"sandbox_ref", "last_sandbox_ref"} and isinstance(value, Mapping):
                yield value
            elif isinstance(value, (Mapping, list)):
                yield from _sandbox_references(value)
    elif isinstance(node, list):
        for value in node:
            yield from _sandbox_references(value)


def inspect_scripts(run_dir: Path) -> dict[str, Any]:
    """Read original source and verify each recorded source/result binding without executing scripts."""
    run_dir = run_dir.resolve()
    artifacts = run_dir / "agent_artifacts"
    folder = artifacts / "sandbox"
    checkpoint = AgentCheckpoint.from_dict(_json(run_dir / "agent_checkpoint.json"))
    errors = []
    trusted = {}
    for ref in checkpoint.sandbox_run_refs:
        if not all(isinstance(ref.get(key), str) for key in REF_FIELDS):
            errors.append("malformed_sandbox_call_receipt")
            continue
        artifact_ref = ref["artifact_ref"]
        if artifact_ref in trusted:
            errors.append(f"duplicate_sandbox_call_receipt:{artifact_ref}")
        trusted[artifact_ref] = {key: ref[key] for key in REF_FIELDS}
    verified = {}
    docs = [checkpoint.to_dict()]
    docs.extend(_json(path) for path in sorted(artifacts.glob("round_*.json")))
    for doc in docs:
        for ref in _sandbox_references(doc):
            if not all(isinstance(ref.get(key), str) for key in REF_FIELDS):
                errors.append("malformed_sandbox_reference")
                continue
            normalized = {key: ref[key] for key in REF_FIELDS}
            previous = verified.setdefault(ref["artifact_ref"], normalized)
            if previous != normalized:
                errors.append(f"conflicting_sandbox_reference:{ref['artifact_ref']}")
    scripts = []
    for artifact in sorted(folder.glob("run_*.json")):
        artifact_ref = artifact.relative_to(run_dir).as_posix()
        payload = _json(_relative_file(run_dir, artifact_ref))
        script_ref = artifact.with_suffix(".py").relative_to(run_dir).as_posix()
        script_path = _relative_file(run_dir, script_ref)
        source = script_path.read_bytes() if script_path.is_file() else None
        script_hash = _sha256(source) if source is not None else None
        refs = {
            "artifact_ref": artifact_ref, "artifact_sha256": _sha256(artifact.read_bytes()),
            "script_ref": script_ref, "script_sha256": script_hash,
        }
        receipt = trusted.pop(artifact_ref, None)
        recorded = verified.pop(artifact_ref, None)
        bindings_ok = bool(
            source is not None and payload.get("script_ref") == script_ref
            and payload.get("script_sha256") == script_hash
            and (receipt is None or receipt == refs)
            and (recorded is None or recorded == refs)
        )
        if not bindings_ok:
            errors.append(f"sandbox_sha256_binding_mismatch:{artifact_ref}")
        script = source.decode("utf-8") if source is not None else None
        calls = []
        if script is not None:
            try:
                tree = ast.parse(script)
            except SyntaxError:
                pass  # Invalid attempted scripts are part of the audit.
            else:
                calls = sorted({
                    node.func.id for node in ast.walk(tree)
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                })
        result = payload.get("result")
        numeric = payload.get("ok") is True and _has_finite_numeric_evidence(result)
        if recorded is not None and not numeric:
            errors.append(f"sandbox_verified_reference_has_no_numeric_result:{artifact_ref}")
        scripts.append({
            **refs, "bindings_ok": bindings_ok, "has_checkpoint_or_round_binding": recorded is not None,
            "has_call_receipt": receipt is not None, "uncommitted": receipt is None and recorded is None,
            "executed_at": payload.get("executed_at"), "ok": payload.get("ok") is True,
            "finite_numeric_evidence": numeric,
            "script": script, "result": _audit_value(result), "stdout": payload.get("stdout"),
            "output_truncated": payload.get("output_truncated", False),
            "error_code": payload.get("error_code"), "script_function_calls": calls,
        })
    errors.extend(f"missing_sandbox_artifact:{ref}" for ref in sorted(verified.keys() | trusted.keys()))
    orphan_scripts = sorted(
        path.relative_to(run_dir).as_posix()
        for path in folder.glob("run_*.py") if not path.with_suffix(".json").is_file()
    )
    bypass_events = checkpoint.gate_bypass_events
    if (
        checkpoint.gate_bypass_count != len(bypass_events)
        or len({event["round_id"] for event in bypass_events}) != len(bypass_events)
        or any(not event.get("reason") for event in bypass_events)
    ):
        errors.append("sandbox_gate_bypass_receipt_mismatch")
    successful_files = sum(
        row["bindings_ok"] and row["finite_numeric_evidence"] and not row["uncommitted"] for row in scripts
    )
    if checkpoint.sandbox_success_count != successful_files or (
        (checkpoint.last_sandbox_ref is None) != (checkpoint.sandbox_success_count == 0)
    ):
        errors.append("sandbox_success_count_mismatch")
    return {
        "run_id": checkpoint.run_id, "final_phase": checkpoint.phase,
        "last_sandbox_ref": checkpoint.last_sandbox_ref,
        "sandbox_success_count": checkpoint.sandbox_success_count,
        "gate_bypass_count": checkpoint.gate_bypass_count, "gate_bypass_events": bypass_events,
        "scripts": scripts, "errors": errors, "orphan_scripts": orphan_scripts,
    }


def _audit_for_cells(args: argparse.Namespace, cells: Sequence[str], protocol_sha: str) -> dict[str, Any]:
    runs = {}
    for cell in cells:
        config = _config(args, cell)
        run_dir = Path(config.output_dir)
        if not (run_dir / "agent_checkpoint.json").is_file():
            runs[cell] = {"errors": ["missing_agent_checkpoint"], "scripts": []}
            continue
        audit = inspect_scripts(run_dir)
        if audit["run_id"] != config.run_id:
            audit["errors"].append("sandbox_checkpoint_run_id_mismatch")
        config_file = run_dir / "agent_config.json"
        if not config_file.is_file() or AgentConfig.from_dict(_json(config_file)) != config:
            audit["errors"].append("sandbox_agent_config_mismatch")
        runs[cell] = audit
    eligible = all(
        run.get("final_phase") in TERMINAL_PHASES and not run["errors"] for run in runs.values()
    ) and any(
        run.get("sandbox_success_count", 0) > 0
        for cell, run in runs.items() if ARMS[_parts(cell)[1]] == "sandbox_only"
    )
    return {
        "schema_version": "s1-script-audit/v1", "protocol_sha256": protocol_sha,
        "eligible_for_approval": eligible, "runs": runs,
    }


def cmd_inspect_scripts(args: argparse.Namespace) -> int:
    protocol, digest = _protocol(args)
    audit = _audit_for_cells(args, protocol[f"{args.phase}_cells"], digest)
    path = args.out_dir / AUDIT
    atomic_write_json(path, audit)
    if args.approve_pilot:
        if args.phase != "pilot" or not audit["eligible_for_approval"]:
            raise ValueError("s1_pilot_audit_not_eligible_for_approval")
        approved_path = args.out_dir / "s1_approved_pilot_audit.json"
        _publish_once(approved_path, audit)
        _publish_once(args.out_dir / PILOT_APPROVAL, {
            "schema_version": "s1-pilot-approval/v1", "protocol_sha256": digest,
            "audit_sha256": _sha256(approved_path.read_bytes()),
        })
    _show({"audit_path": str(path), "eligible_for_approval": audit["eligible_for_approval"]})
    return 0


def _read_champion(run_dir: Path, config: AgentConfig) -> tuple[bytes | None, dict[str, Any]]:
    return _read_budget_champion(
        run_dir, f"s1_{config.planner_model}_{config.arm_id}", config.search_seed, REQUEST_CAP,
    )


def _locked_roster(args: argparse.Namespace) -> tuple[dict[str, Any], str, dict[str, FrozenInterfaceSolver]]:
    protocol, protocol_sha = _protocol(args)
    data = (args.out_dir / LOCK).read_bytes()
    lock = json.loads(data)
    expected_cells = protocol[f"{args.phase}_cells"]
    if (
        lock.get("schema_version") != "s1-roster-lock/v1"
        or lock.get("protocol_sha256") != protocol_sha or lock.get("phase") != args.phase
        or [row["cell"] for row in lock["roster"]] != expected_cells
    ):
        raise ValueError("s1_roster_does_not_match_protocol")
    solvers = {}
    for row in lock["roster"]:
        if row.get("missing_reason") == "no_eligible_snapshot":
            continue
        path = _relative_file(args.out_dir, row["snapshot_ref"])
        snapshot = _read_pinned(path, row["snapshot_sha256"], "s1_snapshot")
        solvers[row["cell"]] = FrozenInterfaceSolver.from_dict(snapshot)
    return lock, _sha256(data), solvers


def cmd_lock_roster(args: argparse.Namespace) -> int:
    protocol, protocol_sha = _protocol(args)
    if args.phase != "full" and not args.mock:
        raise ValueError("s1_production_blind_roster_requires_full_phase")
    _check_pilot_approval(args, protocol, protocol_sha)
    path = args.out_dir / LOCK
    if path.exists():
        lock, _, solvers = _locked_roster(args)
        _show({"roster_lock_path": str(path), "locked_count": len(solvers), "missing_count": len(lock["roster"]) - len(solvers)})
        return 0
    cells = protocol[f"{args.phase}_cells"]
    audit = _audit_for_cells(args, cells, protocol_sha)
    rows = []
    snapshots = {}
    for cell in cells:
        config = _config(args, cell)
        run_dir = Path(config.output_dir)
        if AgentConfig.from_dict(_json(run_dir / "agent_config.json")) != config:
            raise ValueError(f"s1_run_config_mismatch:{cell}")
        if audit["runs"][cell]["errors"]:
            raise ValueError(f"s1_run_audit_invalid:{cell}:{audit['runs'][cell]['errors']}")
        data, provenance = _read_champion(run_dir, config)
        row = {"cell": cell, "provenance": provenance}
        if data is None:
            row["missing_reason"] = "no_eligible_snapshot"
        else:
            solver = FrozenInterfaceSolver.from_dict(json.loads(data))
            if (
                solver.problem_family != "cvrp" or solver.template_id not in TEMPLATES
                or solver.postprocess_mode not in POSTPROCESS_MODES
            ):
                raise ValueError(f"s1_champion_outside_search_space:{cell}")
            result = validate_frozen_solver(
                solver, instance_time_budget_ms=DEADLINE_MS,
                allow_extended_numpy_whitelist=config.allow_extended_numpy_whitelist,
            )
            if not result.passed:
                raise ValueError(f"s1_champion_failed_interface_validation:{cell}")
            ref = f"roster_snapshots/{config.run_id}.json"
            snapshots[ref] = json.loads(data)
            row["snapshot_ref"] = ref
        rows.append(row)
    for row in rows:
        if "snapshot_ref" in row:
            ref = row["snapshot_ref"]
            snapshot_path = args.out_dir / ref
            _publish_once(snapshot_path, snapshots[ref])
            row["snapshot_sha256"] = _sha256(snapshot_path.read_bytes())
    audit_path = args.out_dir / "s1_locked_script_audit.json"
    _publish_once(audit_path, audit)
    payload = {
        "schema_version": "s1-roster-lock/v1", "protocol_sha256": protocol_sha,
        "phase": args.phase, "run_mode": protocol["run_mode"], "roster": rows,
        "script_audit_sha256": _sha256(audit_path.read_bytes()),
    }
    _write_once(path, payload)
    _show({"roster_lock_path": str(path), "locked_count": len(snapshots), "missing_count": len(rows) - len(snapshots)})
    return 0


def _claim_blind(args: argparse.Namespace, protocol: Mapping[str, Any], roster_sha: str) -> dict[str, Any]:
    root = _custody(args)
    path = args.out_dir / COMMITMENT
    commitment = _public_commitment(path)
    commitment_sha = _sha256(path.read_bytes())
    if commitment_sha != protocol["commitment_sha256"]:
        raise ValueError("s1_commitment_sha256_mismatch")
    sealed_path = _private_path(root, f"{BLIND_SUITE_ID}_sealed.json")
    if not sealed_path.is_file():
        raise FileNotFoundError("s1_custody_seal_missing")
    content_sha = commitment["suite_content_sha256"]
    marker = _private_path(root, f"{BLIND_SUITE_ID}.{content_sha}.consumed")
    try:
        _write_once(marker, {"commitment_sha256": commitment_sha, "roster_lock_sha256": roster_sha})
    except FileExistsError:
        raise FileExistsError("blind_attempt_already_consumed") from None
    try:
        sealed = _json(sealed_path)
        if sealed["schema_version"] != "milestone-blind-sealed/v1":
            raise ValueError("s1_invalid_custody_schema")
        for key in commitment.keys() - {"instances", "schema_version", "commitment_status"}:
            if sealed.get(key) != commitment[key]:
                raise ValueError("s1_custody_metadata_mismatch")
        instances = sealed["instances"]
        if _sha256_payload(instances) != content_sha or len(instances) != SUITE_COUNTS[BLIND_SUITE_ID]:
            raise ValueError("s1_custody_content_mismatch")
        for instance, row in zip(instances, commitment["instances"], strict=True):
            if (
                instance["instance_id"] != row["instance_id"] or instance["cell"] != row["cell"]
                or _sha256_payload(instance) != row["instance_sha256"]
            ):
                raise ValueError("s1_custody_instance_mismatch")
    except Exception:
        raise RuntimeError("s1_blind_payload_verification_failed_attempt_consumed") from None
    return sealed


def _score_suite(
    suite: Mapping[str, Any], cells: Sequence[str], solvers: Mapping[str, FrozenInterfaceSolver],
) -> dict[str, Any]:
    exact_applicable = suite["vehicle_limit_policy"] != "free_fleet_min_k_lb"
    records = {cell: [] for cell in cells}
    # Rotate evaluation order by instance, while keeping wall-clock evaluators
    # serial to avoid contention at the 500 ms acceptance boundary.
    for index, instance in enumerate(suite["instances"]):
        offset = index % len(cells)
        for cell in (*cells[offset:], *cells[:offset]):
            solver = solvers.get(cell)
            result = (
                evaluate_public_frozen_solver(solver, instance, suite, solve_deadline_ms=DEADLINE_MS)
                if solver is not None else {}
            )
            if result.get("error_code") in {"worker_protocol", "worker_crash", "worker_start_failed"}:
                raise RuntimeError("s1_frozen_worker_failed")
            records[cell].append(build_m5_public_record(
                instance, result, solve_deadline_ms=DEADLINE_MS, exact_k_applicable=exact_applicable,
            ))
    return {"vehicle_limit_policy": suite["vehicle_limit_policy"], "records": records}


def cmd_unseal_eval(args: argparse.Namespace) -> int:
    path = args.out_dir / EVALUATION
    if path.exists():
        raise FileExistsError("blind_attempt_already_consumed")
    lock, lock_sha, solvers = _locked_roster(args)
    protocol, protocol_sha = _protocol(args)
    if lock["run_mode"] != protocol["run_mode"] or (args.phase != "full" and not args.mock):
        raise ValueError("s1_ineligible_blind_roster")
    _read_pinned(args.out_dir / "s1_locked_script_audit.json", lock["script_audit_sha256"], "s1_locked_script_audit")
    _check_pilot_approval(args, protocol, protocol_sha)
    _custody(args)
    commitment_path = args.out_dir / COMMITMENT
    _public_commitment(commitment_path)
    if _sha256(commitment_path.read_bytes()) != protocol["commitment_sha256"]:
        raise ValueError("s1_commitment_sha256_mismatch")
    cells = [row["cell"] for row in lock["roster"]]
    suites = {}
    for suite_id, split, role in EXTERNAL_CVRPLIB_SUITES:
        suite = load_dev_or_public_suite(suite_id, split=split, role=role)
        if not args.mock and len(suite["instances"]) != SUITE_COUNTS[suite_id]:
            raise ValueError(f"s1_unexpected_external_suite_count:{suite_id}")
        if args.mock:
            suite = {**suite, "instances": suite["instances"][:3]}
        suites[suite_id] = _score_suite(suite, cells, solvers)
    blind = _claim_blind(args, protocol, lock_sha)
    try:
        suites[BLIND_SUITE_ID] = _score_suite(blind, cells, solvers)
    except Exception:
        raise RuntimeError("s1_blind_evaluation_failed_attempt_consumed") from None
    _write_once(path, {
        "schema_version": "s1-evaluation/v1", "protocol_sha256": protocol_sha, "roster_lock_sha256": lock_sha,
        "suites": suites,
    })
    _show({"evaluation_path": str(path), "suite_count": len(suites)})
    return 0


def _paired_tests(
    left: Sequence[Mapping[str, Any]], right: Sequence[Mapping[str, Any]], seed: int, *, exact: bool,
) -> dict[str, Any]:
    l_index, r_index = _indexed(left), _indexed(right)
    if l_index.keys() != r_index.keys() or not l_index:
        raise ValueError("s1_paired_instance_ids_mismatch")
    pairs = [(l_index[key], r_index[key]) for key in sorted(l_index)]
    for lrow, rrow in pairs:
        keys = ("size", "reference_objective", "exact_k_applicable")
        if any(lrow[key] != rrow[key] for key in keys):
            raise ValueError("s1_paired_reference_mismatch")
    if exact:
        pairs = [(lrow, rrow) for lrow, rrow in pairs if lrow["exact_k_applicable"]]
    common = [
        (lrow["objective"], rrow["objective"]) for lrow, rrow in pairs
        if _completed(lrow, exact) and _completed(rrow, exact)
    ]
    penalized = [(_penalized(lrow, exact), _penalized(rrow, exact)) for lrow, rrow in pairs]
    results = {}
    for denominator, cost_pairs in zip(DENOMINATORS, (common, penalized), strict=True):
        if not cost_pairs:
            results[denominator] = {"n_pairs": 0, "wilcoxon": None, "bootstrap": None}
            continue
        lcosts, rcosts = zip(*cost_pairs, strict=True)
        results[denominator] = {
            "n_pairs": len(lcosts),
            "wilcoxon": paired_wilcoxon_signed_rank(lcosts, rcosts),
            "bootstrap": paired_bootstrap_comparison(lcosts, rcosts, n_boot=10000, seed=seed),
        }
    return results


def _contrast_report(
    suite_id: str, records: Mapping[str, Sequence[Mapping[str, Any]]], cells: Sequence[str],
) -> list[dict[str, Any]]:
    contrasts = []
    for model in MODELS:
        seeds = sorted({_parts(cell)[2] for cell in cells if _parts(cell)[0] == model})
        by_model = []
        for seed in seeds:
            for left, right in _CELL_CONTRASTS:
                lhs, rhs = records[_id(model, left, seed)], records[_id(model, right, seed)]
                by_model.append({
                    "suite_id": suite_id, "model": model, "seed": seed, "left": left, "right": right,
                    **{fleet: _paired_tests(lhs, rhs, seed, exact=fleet == "exact_k") for fleet in FLEETS},
                })
        for fleet in FLEETS:
            for denominator in DENOMINATORS:
                tests = [row[fleet][denominator] for row in by_model]
                adjusted = holm_bonferroni_adjust([
                    test["wilcoxon"]["p_two_sided"] if test["wilcoxon"] else 1.0 for test in tests
                ])
                for test, p in zip(tests, adjusted, strict=True):
                    test["wilcoxon_p_holm"] = p if test["wilcoxon"] else None
        contrasts.extend(by_model)
    return contrasts


def _cross_seed_std(per_seed: Mapping[str, Any]) -> dict[str, Any]:
    stats = {}
    metrics = ("completion_rate", "completed_mean_objective", "overall_penalized_mean_objective")
    for model in MODELS:
        cells = [cell for cell in per_seed if _parts(cell)[0] == model]
        if not cells:
            continue
        stats[model] = {}
        for arm in ARMS:
            stats[model][arm] = {}
            for fleet in FLEETS:
                rows = [per_seed[cell][fleet] for cell in cells if _parts(cell)[1] == arm and per_seed[cell][fleet] is not None]
                if not rows:
                    stats[model][arm][fleet] = None
                    continue
                summary = {}
                for metric in metrics:
                    values = [row[metric] for row in rows if row[metric] is not None]
                    summary[metric] = {"n_seeds": len(values), "sample_std": stdev(values) if len(values) >= 2 else None}
                stats[model][arm][fleet] = summary
    return stats


def _report_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# S1 CVRP numerical sandbox ablation", "",
        f"Phase **{report['phase']}**, mode **{report['run_mode']}**. ",
        "Each paired test uses instances from one search seed. Holm–Bonferroni families are defined by "
        "suite, model, fleet policy and denominator, across all planned arm comparisons and seeds.", "",
        "## Completion and tour length by seed", "",
        "| Suite | Model | Arm | Seed | Fleet | Completion rate | Completed mean length | 2×-penalized mean length |",
        "| --- | --- | --- | --- | --- | ---: | ---: | ---: |",
    ]
    def number(value: float | None) -> str:
        return "—" if value is None else f"{value:.6g}"

    for suite, cells in report["per_seed"].items():
        for cell, by_fleet in cells.items():
            model, arm, seed = _parts(cell)
            for fleet, metrics in by_fleet.items():
                if metrics is None:
                    continue
                lines.append(
                    f"| {suite} | {model} | {arm} | {seed} | {fleet} | {number(metrics['completion_rate'])} | "
                    f"{number(metrics['completed_mean_objective'])} | {number(metrics['overall_penalized_mean_objective'])} |"
                )
    lines.extend([
        "", "## Cross-seed sample standard deviations", "",
        "| Suite | Model | Arm | Fleet | Completion rate SD | Completed mean length SD | Penalized mean length SD |",
        "| --- | --- | --- | --- | ---: | ---: | ---: |",
    ])
    for suite, models in report["cross_seed_std"].items():
        for model, arms in models.items():
            for arm, fleets in arms.items():
                for fleet, stats in fleets.items():
                    if stats is not None:
                        values = " | ".join(f"{number(metric['sample_std'])} ({metric['n_seeds']} seeds)" for metric in stats.values())
                        lines.append(f"| {suite} | {model} | {arm} | {fleet} | {values} |")
    lines.extend([
        "", "## Paired tests by seed", "",
        "Positive gain means the left arm has shorter tours. Bootstrap intervals use 10,000 resamples.", "",
        "| Suite | Model | Seed | Left arm | Right arm | Fleet | Denominator | Pairs | Gain (%) | 95% CI (%) | Wilcoxon p | Holm p |",
        "| --- | --- | --- | --- | --- | --- | --- | ---: | ---: | --- | ---: | ---: |",
    ])
    for row in report["contrasts"]:
        for fleet in FLEETS:
            for denominator, tests in row[fleet].items():
                bootstrap = tests["bootstrap"]
                gain = bootstrap["rel_gain_vs_baseline_pct"] if bootstrap else None
                interval = ", ".join(map(number, bootstrap["rel_gain_ci95_pct"])) if bootstrap else "—"
                p_value = tests["wilcoxon"]["p_two_sided"] if tests["wilcoxon"] else None
                lines.append(
                    f"| {row['suite_id']} | {row['model']} | {row['seed']} | {row['left']} | {row['right']} | {fleet} | "
                    f"{denominator} | {tests['n_pairs']} | {number(gain)} | {interval} | {number(p_value)} | "
                    f"{number(tests['wilcoxon_p_holm'])} |"
                )
    lines.extend([
        "", "## Sandbox script and gate-bypass audit", "",
        "| Cell | Script | Result SHA-256 | Script SHA-256 | Binding check | Numeric output | Gate bypasses |",
        "| --- | --- | --- | --- | --- | --- | ---: |",
    ])
    for cell, audit in report["sandbox_audit"].items():
        if not audit["scripts"]:
            lines.append(f"| {cell} | — | — | — | — | — | {audit['gate_bypass_count']} |")
        for row in audit["scripts"]:
            lines.append(
                f"| {cell} | `{row['script_ref']}` | `{row['artifact_sha256']}` | `{row['script_sha256']}` | "
                f"{row['bindings_ok']} | {row['finite_numeric_evidence']} | {audit['gate_bypass_count']} |"
            )
        for event in audit["gate_bypass_events"]:
            lines.append(f"| {cell} | Round {event['round_id']} | — | — | {event['reason']} | — | 1 |")
    lines.extend([
        "", f"[Full paired statistics, script sources and outputs]({REPORT}.json)", "",
    ])
    return "\n".join(lines)


def cmd_report(args: argparse.Namespace) -> int:
    lock, lock_sha, _ = _locked_roster(args)
    evaluation = _json(args.out_dir / EVALUATION)
    if (
        evaluation["schema_version"] != "s1-evaluation/v1" or evaluation["roster_lock_sha256"] != lock_sha
        or evaluation["protocol_sha256"] != lock["protocol_sha256"]
        or evaluation["suites"].keys() != SUITE_COUNTS.keys()
    ):
        raise ValueError("s1_evaluation_binding_mismatch")
    per_seed, cross_seed, contrasts = {}, {}, []
    cells = [row["cell"] for row in lock["roster"]]
    for suite_id, suite in evaluation["suites"].items():
        records = suite["records"]
        if set(records) != set(cells) or (
            (suite_id == BLIND_SUITE_ID or not args.mock)
            and any(len(rows) != SUITE_COUNTS[suite_id] for rows in records.values())
        ):
            raise ValueError("s1_evaluation_roster_or_suite_count_mismatch")
        per_seed[suite_id] = {cell: _fleet_metrics(records[cell]) for cell in cells}
        cross_seed[suite_id] = _cross_seed_std(per_seed[suite_id])
        contrasts.extend(_contrast_report(suite_id, records, cells))
    audit = _read_pinned(
        args.out_dir / "s1_locked_script_audit.json", lock["script_audit_sha256"], "s1_locked_script_audit",
    )
    protocol, _ = _protocol(args)
    report = {
        "schema_version": "s1-report/v1", "phase": args.phase, "run_mode": lock["run_mode"],
        "protocol_sha256": lock["protocol_sha256"], "roster_lock_sha256": lock_sha,
        "evaluation_sha256": _sha256((args.out_dir / EVALUATION).read_bytes()),
        "per_seed": per_seed, "cross_seed_std": cross_seed, "contrasts": contrasts,
        "sandbox_audit": audit["runs"], "missing_cells": [row["cell"] for row in lock["roster"] if "missing_reason" in row],
        "holm_family": protocol["holm_family"],
    }
    path = args.out_dir / f"{REPORT}.json"
    atomic_write_json(path, report)
    atomic_write_text(args.out_dir / f"{REPORT}.md", _report_markdown(report))
    _show({"report_path": str(path)})
    return 0


def _common_args(parser: argparse.ArgumentParser, *, suppress: bool = False) -> None:
    def default(value: Any) -> Any:
        return argparse.SUPPRESS if suppress else value

    parser.add_argument("--out-dir", "--output-dir", type=Path, default=default(DEFAULT_OUTPUT))
    parser.add_argument("--phase", choices=("pilot", "full"), default=default("pilot"))
    parser.add_argument("--seeds", type=int, choices=SEEDS, nargs="+", default=default(None),
                        help="Limit the roster in mock mode.")
    parser.add_argument("--custody-dir", type=Path, default=default(None))
    parser.add_argument("--mock", action="store_true", default=default(False))
    parser.add_argument("--endpoint", default=default(os.environ.get(
        "OPENCODE_GO_ENDPOINT", "https://opencode.ai/zen/go/v1/chat/completions",
    )))
    parser.add_argument("--api-key-env", default=default("OPENCODE_GO_API_KEY"))
    parser.add_argument("--request-timeout-s", type=float, default=default(60.0))
    parser.add_argument("--wall-seconds", type=float, default=default(14400.0))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    _common_args(parser)
    subs = parser.add_subparsers(dest="stage", required=True)
    subparsers = {}
    for stage, fn, description in (
        ("seal-blind", cmd_seal_blind, "Create an independent external blind seal and freeze the protocol."),
        ("emit-mux", cmd_emit_mux, "Write a multi_task_mux manifest for the selected phase."),
        ("run-cell", cmd_run_cell, "Run or resume one registered arm/model/seed cell."),
        ("inspect-scripts", cmd_inspect_scripts, "Extract and verify sandbox scripts, evidence and bypass events."),
        ("lock-roster", cmd_lock_roster, "Freeze dev-selected champions and their audit before blind evaluation."),
        ("unseal-eval", cmd_unseal_eval, "Evaluate the locked roster on the independent blind and CVRPLib suites."),
        ("report", cmd_report, "Report seed-level metrics, paired tests and the complete script audit."),
    ):
        subparser = subs.add_parser(stage, help=description)
        _common_args(subparser, suppress=True)
        subparser.set_defaults(func=fn)
        subparsers[stage] = subparser
    subparsers["emit-mux"].add_argument("--manifest-path", type=Path)
    _model_map = {m.casefold(): m for m in MODELS}
    subparsers["run-cell"].add_argument(
        "--model", type=lambda s: _model_map.get(s.casefold(), s), choices=MODELS, default=MODELS[0],
    )
    subparsers["run-cell"].add_argument("--seed", type=int, required=True)
    subparsers["run-cell"].add_argument("--arm", choices=ARMS, required=True)
    subparsers["run-cell"].add_argument("--resume", action="store_true")
    subparsers["inspect-scripts"].add_argument(
        "--approve-pilot", action="store_true", help="Confirm human review of the eligible pilot audit for full runs.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.out_dir = args.out_dir.resolve()
    if args.seeds and (not args.mock or len(args.seeds) != len(set(args.seeds))):
        parser.error("--seeds requires --mock and unique seeds")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
