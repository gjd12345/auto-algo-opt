"""Run and report the M5 CVRP trajectory-control experiment."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sqlite3
import statistics
import sys
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from contextlib import closing
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from agent_skill_loop.client import ProviderFailure, load_local_env
from agent_skill_loop.cvrp_workbench.solvers import evaluate_algorithm_on_instance
from agent_skill_loop.evidence.search_progress import _behavior_metrics
from agent_skill_loop.interface_design.blind_eval import (
    paired_bootstrap_comparison,
    paired_wilcoxon_signed_rank,
)
from agent_skill_loop.interface_design.blind_eval_m3 import holm_bonferroni_adjust
from agent_skill_loop.interface_design.blind_eval_m32 import (
    _write_once,
    read_public_milestone_blind_commitment,
)
from agent_skill_loop.interface_design.blind_eval_m5 import (
    M5_ARM_SEEDS,
    M5_BASELINE_ALGORITHMS,
    M5_BLIND_COMMITMENT_PATH,
    M5_BLIND_SUITE_ID,
    M5_DEEPSEEK_ARMS,
    M5_DEFAULT_CUSTODY_DIR,
    M5_MODEL2_ARMS,
    M5_REQUEST_CAP,
    M5_SOLVE_DEADLINE_MS,
    _arm_plan,
    _m5_custody_dir,
    build_m5_public_record,
    freeze_m5_roster_lock,
    freeze_pre_blind_protocol_m5,
    load_locked_m5_roster,
    read_m5_protocol,
    seal_m5_blind_120,
    unseal_and_evaluate_m5,
)
from agent_skill_loop.interface_design.contracts import FrozenInterfaceSolver
from agent_skill_loop.interface_design.session_baseline import load_dev_or_public_suite
from research_agent.contracts import AgentConfig, atomic_write_json, atomic_write_text, utc_now
from research_agent.loop import run_research_agent
from tools.run_b4_intron_ablation import (
    EXTERNAL_CVRPLIB_SUITES,
    build_pruned_m32_champion,
    evaluate_public_frozen_solver,
    load_m32_champion_solver,
    load_raw_m32_champion,
    validate_frozen_solver,
)
from tools.run_m32_scaling import (
    RESUMABLE_EXIT_CODE,
    _build_l3_ctrl_solver,
    _load_rate_card,
    cmd_probe_models as _probe_models,
)

DEFAULT_DEEPSEEK = "deepseek-v4.1-flash"
DEFAULT_MODEL2 = "qwen4-max"
DEFAULT_OUTPUT = REPO / "experiments" / "milestone5"
ARMS = M5_DEEPSEEK_ARMS + M5_MODEL2_ARMS
CONTROLS = {"trajectory_ctrl_full_500ms", "model2_ctrl_full_500ms"}
SCREENS = CONTROLS | {"whitelist_latency_500ms"}
TERMINAL_PHASES = {"completed", "budget_stopped", "no_champion"}
TEMPLATES = (
    "cvrp_sequential_construct", "cvrp_parallel_merge_static",
    "cvrp_parallel_merge_dynamic", "cvrp_ruin_recreate",
)
POSTPROCESS_MODES = ("none", "intra_2opt", "relocate_2opt")
SIZES = (50, 100, 150, 200)
SEAL_BUNDLE = "m5_seal_and_protocol.json"
LOCK_BUNDLE = "m5_roster_lock_bundle.json"
EXTERNAL_EVALUATION = "m5_external_evaluation.json"
REPORT = "m5_trajectory_control_report"


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ValueError(f"expected_json_object:{path}")
    return value


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _run_id(arm: str, seed: int) -> str:
    return f"m5_{arm}_s{seed}"


def _run_dir(out_dir: Path, arm: str, seed: int) -> Path:
    return out_dir / "runs" / f"{arm}_s{seed}"


def _parts(cell: str) -> tuple[str, int]:
    arm, seed = cell.split(":")
    return arm, int(seed)


def _output_dir(args: argparse.Namespace) -> Path:
    return Path(args.output_dir).resolve()


def _show(payload: Mapping[str, Any]) -> None:
    print(json.dumps(payload, indent=2, allow_nan=False))


def _rel_to_out(path: Path, out_dir: Path) -> str:
    resolved = Path(path).resolve()
    base = out_dir.resolve()
    try:
        return resolved.relative_to(base).as_posix()
    except ValueError:
        return str(resolved)


def _resolve_out_path(raw: str, out_dir: Path) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else (out_dir.resolve() / path)


def _protocol_args(seal: Mapping[str, Any], out_dir: Path) -> dict[str, Any]:
    protocol = seal["protocol"]
    return {
        "protocol_path": _resolve_out_path(str(protocol["protocol_path"]), out_dir),
        "expected_protocol_sha256": protocol["protocol_sha256"],
    }


def _lock_args(bundle: Mapping[str, Any], out_dir: Path) -> dict[str, Any]:
    return {
        "protocol_path": _resolve_out_path(str(bundle["protocol_path"]), out_dir),
        "expected_protocol_sha256": bundle["protocol_sha256"],
        "roster_lock_path": _resolve_out_path(str(bundle["roster_lock_path"]), out_dir),
        "expected_roster_lock_sha256": bundle["roster_lock_sha256"],
        "snapshot_paths": {
            cell: _resolve_out_path(str(path), out_dir)
            for cell, path in bundle["snapshot_paths"].items()
        },
    }


def _require_protocol(out_dir: Path) -> dict[str, Any]:
    args = _protocol_args(_json(out_dir / SEAL_BUNDLE), out_dir)
    return read_m5_protocol(args["protocol_path"], args["expected_protocol_sha256"])


def _check_model2(args: argparse.Namespace, protocol: Mapping[str, Any]) -> str:
    model2 = protocol["model2"]
    if args.model2 is not None and args.model2 != model2:
        raise ValueError("model2_does_not_match_frozen_m5_protocol")
    return model2


def cmd_probe_models(args: argparse.Namespace) -> int:
    return _probe_models(argparse.Namespace(
        endpoint=args.endpoint,
        api_key_env=args.api_key_env,
        weak_model=args.model1 or DEFAULT_DEEPSEEK,
        strong_candidates=[args.model2 or DEFAULT_MODEL2],
    ))


def cmd_seal_blind(args: argparse.Namespace) -> int:
    out_dir = _output_dir(args)
    custody = _m5_custody_dir(args.custody_dir, REPO)
    commitment = Path(args.commitment_path).resolve()
    protocol_path = out_dir / "pre_blind_protocol_m5.json"
    bundle_path = out_dir / SEAL_BUNDLE
    if bundle_path.is_file():
        existing = _json(bundle_path)
        protocol = _require_protocol(out_dir)
        _check_model2(args, protocol)
        if args.arm_seeds_json and _json(args.arm_seeds_json) != protocol["arm_seeds"]:
            raise ValueError("arm_seeds_do_not_match_frozen_m5_protocol")
        if Path(existing["seal"]["commitment_path"]) != commitment:
            raise ValueError("commitment_path_does_not_match_frozen_m5_protocol")
        if not (custody / f"{M5_BLIND_SUITE_ID}_sealed.json").is_file():
            raise FileNotFoundError("m5_custody_seal_missing")
        read_public_milestone_blind_commitment(
            commitment, expected_suite_id=M5_BLIND_SUITE_ID,
            expected_sha256=protocol["blind_commitment"]["commitment_file_sha256"],
        )
        _show({"protocol_path": str(protocol_path), "reused_existing": True})
        return 0

    arm_seeds, _ = _arm_plan(_json(args.arm_seeds_json) if args.arm_seeds_json else M5_ARM_SEEDS)
    model2 = args.model2 if args.model2 is not None else DEFAULT_MODEL2
    if not model2 or model2 != model2.strip():
        raise ValueError("invalid_m5_model2")
    sealed_path = custody / f"{M5_BLIND_SUITE_ID}_sealed.json"
    if sealed_path.is_file() and commitment.is_file():
        public = read_public_milestone_blind_commitment(commitment, expected_suite_id=M5_BLIND_SUITE_ID)
        seal = {
            "suite_id": M5_BLIND_SUITE_ID,
            "instance_count": public["instance_count"],
            "commitment_path": str(commitment),
            "commitment_sha256": _sha256(commitment.read_bytes()),
            "suite_content_sha256": public["suite_content_sha256"],
        }
    else:
        seal = seal_m5_blind_120(commitment_path=commitment, custody_dir=custody)
    if protocol_path.is_file():
        digest = _sha256(protocol_path.read_bytes())
        protocol = read_m5_protocol(protocol_path, digest)
        if (
            protocol["blind_commitment"]["commitment_file_sha256"] != seal["commitment_sha256"]
            or protocol["model2"] != model2
            or protocol["arm_seeds"] != {arm: list(seeds) for arm, seeds in arm_seeds.items()}
        ):
            raise ValueError("existing_m5_protocol_mismatch")
        frozen = {"protocol_path": str(protocol_path), "protocol_sha256": digest}
    else:
        frozen = freeze_pre_blind_protocol_m5(
            protocol_path, commitment_path=commitment, arm_seeds=arm_seeds, model2=model2,
        )
    _write_once(bundle_path, {
        "schema_version": "m5-seal-bundle/v1",
        "seal": {key: value for key, value in seal.items() if key != "sealed_path"},
        "protocol": {
            "protocol_path": _rel_to_out(Path(frozen["protocol_path"]), out_dir),
            "protocol_sha256": frozen["protocol_sha256"],
        },
    })
    _show({"protocol_path": str(protocol_path), "instance_count": seal["instance_count"]})
    return 0


def cmd_emit_mux(args: argparse.Namespace) -> int:
    out_dir = _output_dir(args)
    protocol = _require_protocol(out_dir)
    model2 = _check_model2(args, protocol)
    model1 = getattr(args, "model1", None)
    if model1 is not None and model1.casefold() != DEFAULT_DEEPSEEK.casefold():
        raise ValueError("model1_does_not_match_m5_deepseek_family")
    panes = []
    for cell in protocol["roster_cells"]:
        arm, seed = _parts(cell)
        command = [
            sys.executable, str(Path(__file__).resolve()), "--output-dir", str(out_dir),
            "run-one", "--arm", arm, "--seed", str(seed), "--mode", args.mode,
            "--model2", model2, "--endpoint", args.endpoint, "--api-key-env", args.api_key_env,
            "--request-timeout-s", str(args.request_timeout_s), "--wall-seconds", str(args.wall_seconds),
        ]
        if model1:
            command.extend(["--model1", model1])
        if args.resume:
            command.append("--resume")
        if args.rate_card_json:
            command.extend(["--rate-card-json", str(args.rate_card_json.resolve())])
        panes.append({"id": _run_id(arm, seed), "command": command, "cwd": str(REPO)})
    path = args.manifest_path or out_dir / "mux_m5.json"
    atomic_write_json(path, {"panes": panes})
    _show({"manifest_path": str(path), "pane_count": len(panes)})
    return 0


def _build_arm_config(args: argparse.Namespace) -> AgentConfig:
    arm, seed = args.arm, args.seed
    if arm not in ARMS:
        raise ValueError(f"unknown_m5_arm:{arm}")
    model1 = getattr(args, "model1", None) or DEFAULT_DEEPSEEK
    if model1.casefold() != DEFAULT_DEEPSEEK.casefold():
        raise ValueError("model1_does_not_match_m5_deepseek_family")
    model = (args.model2 or DEFAULT_MODEL2) if arm in M5_MODEL2_ARMS else model1
    screens = arm in SCREENS
    control = arm in CONTROLS
    return AgentConfig(
        run_id=_run_id(arm, seed),
        output_dir=str(_run_dir(_output_dir(args), arm, seed)),
        problem_family="cvrp",
        arm_id=arm,
        search_seed=seed,
        initial_template_id="cvrp_parallel_merge_static",
        allowed_templates=TEMPLATES,
        allowed_postprocess_modes=POSTPROCESS_MODES,
        use_benchmark_dev_suite=True,
        dev_suite_id="cvrp_dev_hetero_24",
        dev_instance_count=24,
        instance_time_budget_ms=M5_SOLVE_DEADLINE_MS,
        total_request_cap=M5_REQUEST_CAP,
        max_rounds=8,
        outer_requests_per_round_cap=4,
        outer_reflect_cap=2,
        eoh_pop_size=4,
        eoh_n_pop=2,
        eoh_max_sample_nums=30,
        strict_checkpoint_barriers=True,
        checkpoint_budgets=(M5_REQUEST_CAP,),
        planner_model=model,
        eoh_model=model,
        endpoint=args.endpoint,
        api_key_env=args.api_key_env,
        mode=args.mode,
        rate_card=_load_rate_card(args.rate_card_json),
        request_timeout_s=args.request_timeout_s,
        wall_seconds=args.wall_seconds,
        allow_extended_numpy_whitelist=screens,
        enable_n200_latency_screen=screens,
        enable_degenerate_constant_screen=screens,
        enable_stagnation_diagnostic_gate=control,
        early_stop_no_jump_requests=24 if control else None,
        basin_restart_on_stagnation=control,
    )


def cmd_run_one(args: argparse.Namespace) -> int:
    protocol = _require_protocol(_output_dir(args))
    args.model2 = _check_model2(args, protocol)
    if f"{args.arm}:{args.seed}" not in protocol["roster_cells"]:
        raise ValueError("unregistered_m5_run_cell")
    if args.mode == "live":
        load_local_env()
    config = _build_arm_config(args)
    run_dir = Path(config.output_dir)
    checkpoint = run_dir / "agent_checkpoint.json"
    status = {"run_id": config.run_id, "updated_at": utc_now()}
    try:
        summary = run_research_agent(config, resume=args.resume and checkpoint.is_file())
    except ProviderFailure as exc:
        status.update(status="resumable", reason=exc.error_code,
                      checkpoint_preserved=checkpoint.is_file(), exit_code=RESUMABLE_EXIT_CODE)
        if run_dir.is_dir():
            atomic_write_json(run_dir / "run_interrupt_status.json", status)
        _show(status)
        return RESUMABLE_EXIT_CODE
    status.update(status=summary["final_phase"], checkpoint_preserved=checkpoint.is_file())
    atomic_write_json(run_dir / "run_interrupt_status.json", status)
    _show({**status, "attempted_requests": summary.get("budget_summary", {}).get("attempted_requests")})
    return 0


def _open_ledger(path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    return db


def _verify_run_config(out_dir: Path, arm: str, seed: int, model2: str) -> str:
    path = _run_dir(out_dir, arm, seed) / "agent_config.json"
    persisted = AgentConfig.from_dict(_json(path))
    if persisted.mode not in {"live", "mock"}:
        raise ValueError(f"invalid_m5_run_mode:{arm}:{seed}")
    if persisted.mode == "live" and (
        str(persisted.endpoint).startswith("mock://") or os.environ.get("AGENT_SKILL_M2_MOCK") == "1"
    ):
        raise ValueError(f"live_mode_with_mock_endpoint_or_env:{arm}:{seed}")
    model1 = persisted.planner_model if (
        arm in M5_DEEPSEEK_ARMS and str(persisted.planner_model).casefold() == DEFAULT_DEEPSEEK.casefold()
    ) else None
    expected = _build_arm_config(argparse.Namespace(
        output_dir=out_dir, arm=arm, seed=seed, model1=model1, model2=model2, mode=persisted.mode,
        endpoint=persisted.endpoint, api_key_env=persisted.api_key_env,
        request_timeout_s=persisted.request_timeout_s, wall_seconds=persisted.wall_seconds, rate_card_json=None,
    )).to_dict()
    actual = persisted.to_dict()
    for key, value in expected.items():
        if key not in {"rate_card", "rate_card_version"} and actual[key] != value:
            raise ValueError(f"m5_run_config_mismatch:{arm}:{seed}:{key}")
    return persisted.mode


def _read_champion(
    run_dir: Path, arm: str, seed: int, cap: int,
) -> tuple[bytes | None, dict[str, Any]]:
    cell = f"{arm}:{seed}"
    run_id = _run_id(arm, seed)
    summary = _json(run_dir / "research_summary.json")
    phase = summary.get("final_phase")
    if phase not in TERMINAL_PHASES or summary.get("run_id") != run_id:
        raise ValueError(f"cannot_lock_non_terminal_or_mismatched_run:{cell}")
    checkpoint = run_dir / "checkpoints" / f"frozen_checkpoint_{cap}.json"
    with closing(_open_ledger(run_dir / "agent_budget.sqlite3")) as db:
        row = db.execute(
            "SELECT state, payload_sha256, winner_source_ordinal, settled_through_ordinal "
            "FROM milestone_checkpoints WHERE run_id=? AND ckpt_budget=?", (run_id, cap),
        ).fetchone()
        requests = db.execute("SELECT COUNT(*) FROM budget_requests WHERE run_id=?", (run_id,)).fetchone()[0]
    metadata = {"final_phase": phase, "attempted_requests": requests}
    if checkpoint.is_file():
        data = checkpoint.read_bytes()
        if row is None or row["state"] != "sealed":
            raise ValueError(f"cannot_lock_unsealed_checkpoint:{cell}")
        if _sha256(data) != row["payload_sha256"]:
            raise ValueError(f"checkpoint_sqlite_sha256_mismatch:{cell}")
        payload = json.loads(data)
        if (
            payload["run_id"] != run_id or payload["checkpoint_budget"] != cap
            or payload["winner_source_ordinal"] != row["winner_source_ordinal"]
            or payload["settled_through_ordinal"] != row["settled_through_ordinal"]
            or row["settled_through_ordinal"] != cap
        ):
            raise ValueError(f"checkpoint_identity_mismatch:{cell}")
        candidate = payload.get("frozen_solver")
        if candidate is not None:
            serialized = (json.dumps(candidate, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()
            return serialized, {
                **metadata, "winner_source": f"sealed_checkpoint_{cap}",
                "winner_source_ordinal": row["winner_source_ordinal"],
                "source_sha256": row["payload_sha256"],
            }
    elif row is not None and row["state"] == "sealed":
        raise FileNotFoundError(f"sealed_checkpoint_export_missing:{cell}")

    ref = summary.get("best_solver_manifest_ref")
    if ref:
        if phase not in {"completed", "budget_stopped"} or requests >= cap:
            raise ValueError(f"ineligible_agent_best_solver_fallback:{cell}")
        manifest = Path(ref)
        if manifest.is_absolute() or not (path := (run_dir / manifest).resolve()).is_relative_to(run_dir):
            raise ValueError(f"agent_best_solver_ref_outside_run:{cell}")
        data = path.read_bytes()
        return data, {**metadata, "winner_source": "agent_best_solver", "source_sha256": _sha256(data)}
    if phase == "no_champion":
        return None, metadata
    raise ValueError(f"terminal_run_missing_champion:{cell}")


def cmd_lock_roster(args: argparse.Namespace) -> int:
    out_dir = _output_dir(args)
    protocol_args = _protocol_args(_json(out_dir / SEAL_BUNDLE), out_dir)
    protocol = read_m5_protocol(protocol_args["protocol_path"], protocol_args["expected_protocol_sha256"])
    lock_path = out_dir / "m5_roster_lock.json"
    bundle_path = out_dir / LOCK_BUNDLE
    if bundle_path.is_file():
        bundle = _json(bundle_path)
        lock_args = _lock_args(bundle, out_dir)
        if lock_args["expected_protocol_sha256"] != protocol_args["expected_protocol_sha256"]:
            raise ValueError("existing_m5_roster_protocol_mismatch")
        _, locked, missing = load_locked_m5_roster(**lock_args)
        _show({"roster_lock_path": str(lock_path), "locked_count": len(locked), "missing_count": len(missing)})
        return 0
    snapshots = {}
    missing = {}
    metadata = {}
    modes = {
        _verify_run_config(out_dir, *_parts(cell), protocol["model2"])
        for cell in protocol["roster_cells"]
    }
    if len(modes) != 1:
        raise ValueError("m5_roster_mixes_mock_and_live_runs")
    for cell in protocol["roster_cells"]:
        arm, seed = _parts(cell)
        data, metadata[cell] = _read_champion(_run_dir(out_dir, arm, seed), arm, seed, protocol["request_cap"])
        if data is None:
            missing[cell] = "no_eligible_snapshot"
            continue
        solver = FrozenInterfaceSolver.from_dict(json.loads(data))
        if solver.template_id not in TEMPLATES or solver.postprocess_mode not in POSTPROCESS_MODES:
            raise ValueError(f"champion_outside_m5_search_space:{cell}")
        result = validate_frozen_solver(
            solver, instance_time_budget_ms=M5_SOLVE_DEADLINE_MS, allow_extended_numpy_whitelist=arm in SCREENS,
        )
        if not result.passed:
            raise ValueError(f"champion_failed_interface_validation:{cell}:{[f.error_code for f in result.failures]}")
        snapshots[cell] = data

    snapshot_paths = {}
    for cell, data in snapshots.items():
        path = out_dir / "roster_snapshots" / f"{cell.replace(':', '_')}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("xb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
        except FileExistsError:
            if path.read_bytes() != data:
                raise ValueError(f"existing_m5_snapshot_mismatch:{cell}") from None
        snapshot_paths[cell] = path
    if lock_path.is_file():
        lock_sha = _sha256(lock_path.read_bytes())
        _, _, locked_missing = load_locked_m5_roster(
            **protocol_args, roster_lock_path=lock_path, expected_roster_lock_sha256=lock_sha,
            snapshot_paths=snapshot_paths,
        )
        if locked_missing != missing:
            raise ValueError("existing_m5_roster_missing_cells_mismatch")
    else:
        lock = freeze_m5_roster_lock(
            lock_path, **protocol_args, snapshot_paths=snapshot_paths, missing_cells=missing,
        )
        lock_sha = lock["roster_lock_sha256"]

    _write_once(bundle_path, {
        "schema_version": "m5-roster-lock-bundle/v1",
        "protocol_path": _rel_to_out(protocol_args["protocol_path"], out_dir),
        "protocol_sha256": protocol_args["expected_protocol_sha256"],
        "roster_lock_path": _rel_to_out(lock_path, out_dir),
        "roster_lock_sha256": lock_sha,
        "snapshot_paths": {cell: _rel_to_out(path, out_dir) for cell, path in snapshot_paths.items()},
        "missing_cells": missing,
        "snapshot_metadata": metadata,
        "run_mode": next(iter(modes)),
        "comparator_manifest_sha256": _comparator_digests(_comparator_solvers()),
    })
    _show({"roster_lock_path": str(lock_path), "locked_count": len(snapshots), "missing_count": len(missing)})
    return 0


def _comparator_solvers() -> tuple[tuple[str, FrozenInterfaceSolver, float], ...]:
    raw = load_raw_m32_champion()
    deadline = M5_SOLVE_DEADLINE_MS
    return (
        ("l3_ctrl@500ms", _build_l3_ctrl_solver(deadline), deadline),
        ("m32_champion_raw@500ms", load_m32_champion_solver(raw), deadline),
        ("m32_champion_pruned@500ms", load_m32_champion_solver(build_pruned_m32_champion(raw)), deadline),
    )


def _comparator_digests(solvers: Sequence[tuple[str, FrozenInterfaceSolver, float]]) -> dict[str, str]:
    return {
        label: _sha256(json.dumps(solver.to_dict(), sort_keys=True, allow_nan=False).encode())
        for label, solver, _ in solvers
    }


def _locked_comparators(bundle: Mapping[str, Any]) -> tuple[tuple[str, FrozenInterfaceSolver, float], ...]:
    solvers = _comparator_solvers()
    if _comparator_digests(solvers) != bundle["comparator_manifest_sha256"]:
        raise ValueError("m5_locked_comparator_manifest_mismatch")
    return solvers


def cmd_unseal_blind(args: argparse.Namespace) -> int:
    out_dir = _output_dir(args)
    bundle = _json(out_dir / LOCK_BUNDLE)
    commitment = Path(args.commitment_path).resolve()
    custody = _m5_custody_dir(args.custody_dir, REPO).resolve()
    if bundle.get("run_mode") != "live" and (
        commitment == M5_BLIND_COMMITMENT_PATH.resolve()
        or custody == M5_DEFAULT_CUSTODY_DIR.resolve()
    ):
        raise ValueError("mock_roster_cannot_consume_production_m5_blind_attempt")
    result = unseal_and_evaluate_m5(
        **_lock_args(bundle, out_dir),
        output_dir=out_dir / "blind_120_eval",
        commitment_path=args.commitment_path,
        custody_dir=args.custody_dir,
        comparator_solvers=_locked_comparators(bundle),
        baseline_algorithms=M5_BASELINE_ALGORITHMS,
    )
    _show({"report_path": result["report_path"], "record_count": len(result["records"])})
    return 0


def cmd_eval_external(args: argparse.Namespace) -> int:
    out_dir = _output_dir(args)
    bundle = _json(out_dir / LOCK_BUNDLE)
    lock_args = _lock_args(bundle, out_dir)
    _, solvers, missing = load_locked_m5_roster(**lock_args)
    comparators = {label: solver for label, solver, _ in _locked_comparators(bundle)}
    records = {}
    for suite_id, split, role in EXTERNAL_CVRPLIB_SUITES:
        suite = load_dev_or_public_suite(suite_id, split=split, role=role)
        policy = suite["vehicle_limit_policy"]
        exact_k_applicable = policy != "free_fleet_min_k_lb"
        suite_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for instance in suite["instances"]:
            results = {
                label: evaluate_public_frozen_solver(solver, instance, suite, solve_deadline_ms=M5_SOLVE_DEADLINE_MS)
                for label, solver in (solvers | comparators).items()
            }
            for algorithm, deadline in M5_BASELINE_ALGORITHMS:
                results[f"{algorithm}@{deadline:g}ms"] = evaluate_algorithm_on_instance(
                    algorithm, instance, distance_convention=suite["distance_convention"],
                    vehicle_limit_policy=policy, time_budget_ms=deadline,
                    enforce_wall_deadline=True, record_trace=False,
                )
            for label, result in results.items():
                if result.get("error_code") in {"worker_protocol", "worker_crash", "worker_start_failed"}:
                    raise RuntimeError(f"m5_external_worker_failed:{suite_id}:{label}")
                suite_rows[label].append(build_m5_public_record(instance, result, exact_k_applicable=exact_k_applicable))
        records[suite_id] = {"vehicle_limit_policy": policy, "records": dict(suite_rows)}
    path = out_dir / EXTERNAL_EVALUATION
    atomic_write_json(path, {
        "schema_version": "m5-external-evaluation/v1",
        "protocol_sha256": lock_args["expected_protocol_sha256"],
        "roster_lock_sha256": lock_args["expected_roster_lock_sha256"],
        "missing_cells": missing,
        "suites": records,
    })
    _show({"report_path": str(path), "suite_count": len(records)})
    return 0


def _jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _finite(value: Any) -> float | None:
    return float(value) if type(value) in {float, int} and math.isfinite(value) else None


def _mean(values: Sequence[float]) -> float | None:
    return statistics.fmean(values) if values else None


def _rate(count: int, denominator: int) -> float | None:
    return count / denominator if denominator else None


def _last_search_progress(run_dir: Path) -> Mapping[str, Any]:
    rounds = run_dir / "session_run" / "rounds"
    for path in sorted(rounds.glob("round_*/evaluation_facts.json"), reverse=True):
        progress = _json(path).get("search_progress", {}).get("cumulative")
        if isinstance(progress, Mapping):
            return progress
    return {}


def _logged_evaluations(run_dir: Path) -> tuple[list[dict[str, Any]], bool, bool]:
    archives = sorted(run_dir.glob("session_run_interrupted_*"))
    paths = [
        path for session in (*archives, run_dir / "session_run")
        for path in sorted((session / "rounds").rglob("evaluations.jsonl"))
    ]
    rows = []
    seen = set()
    for path in paths:
        for row in _jsonl(path):
            identity = row.get("attempt_token") or row.get("evaluation_id")
            if identity is not None:
                if identity in seen:
                    continue
                seen.add(identity)
            rows.append({**row, **(row.get("evaluation") or {})})
    return rows, bool(paths), bool(archives)


def _candidate_errors(rows: Sequence[Mapping[str, Any]], have_logs: bool) -> dict[str, int | None]:
    errors = Counter(
        row["error_code"] for row in rows
        if row.get("origin") == "generated" and row.get("revision", "original") == "original"
        and isinstance(row.get("error_code"), str)
    )
    return {
        code: errors[code] if have_logs else None
        for code in ("forbidden_attribute", "n200_latency_exceeded", "degenerate_constant_output")
    }


def _tool_metrics(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "agent_artifacts" / "agent_turns.jsonl"
    tools: Counter[str] = Counter()
    # The messages are conversation snapshots. Deduplicate repeated tool results
    # by call ID, or by their offset in the round/phase transcript.
    unknown_results = set()
    turns_seen = set()
    for turn in _jsonl(path):
        request_id = turn.get("request_id")
        if request_id is not None:
            if request_id in turns_seen:
                continue
            turns_seen.add(request_id)
        decision = turn.get("decision", {})
        if decision.get("action") == "call_tool" and isinstance(decision.get("tool"), str):
            tools[decision["tool"]] += 1
        error = decision.get("error")
        if isinstance(error, str) and "unknown_hypothesis" in error:
            unknown_results.add(("decision", request_id, turn.get("round_id"), turn.get("step_index")))
        for offset, message in enumerate(turn.get("messages", [])):
            if message.get("role") not in {"tool", "user"}:
                continue
            content = message.get("content")
            if not isinstance(content, str) or "unknown_hypothesis" not in content:
                continue
            try:
                payload = json.loads(content)
            except ValueError:
                continue
            if not isinstance(payload, dict):
                continue
            result = payload.get("result", payload)
            if isinstance(result, dict) and "unknown_hypothesis" in str(result.get("error", "")):
                identity = message.get("tool_call_id") or (turn.get("round_id"), turn.get("phase"), offset)
                unknown_results.add(("result", identity))
    counts = {name: tools[name] if path.is_file() else None for name in (
        "diagnose_suite", "run_math_sandbox", "propose_and_validate_interface", "kb_search", "kb_read",
    )}
    counts["kb_search+kb_read"] = tools["kb_search"] + tools["kb_read"] if path.is_file() else None
    total = sum(tools.values())
    return {
        "outer_tool_call_count": total if path.is_file() else None,
        "outer_tool_calls": counts,
        "outer_tool_call_distribution": {
            name: _rate(count, total) if count is not None else None for name, count in counts.items()
        },
        "unknown_hypothesis_errors": len(unknown_results) if path.is_file() else None,
    }


def _trajectory(run_dir: Path, metadata: Mapping[str, Any]) -> dict[str, Any]:
    summary = _json(run_dir / "research_summary.json")
    run_id = summary["run_id"]
    with closing(_open_ledger(run_dir / "agent_budget.sqlite3")) as db:
        total = db.execute("SELECT COUNT(*) FROM budget_requests WHERE run_id=?", (run_id,)).fetchone()[0]
        candidates = db.execute(
            "SELECT global_ordinal, generation_status, eligible, dev_all_feasible, "
            "dev_completion_rate, dev_penalized_mean FROM candidate_provenance "
            "WHERE run_id=? ORDER BY global_ordinal", (run_id,),
        ).fetchall()
        wall = db.execute("SELECT wall_offset_seconds FROM run_wall_clock WHERE run_id=?", (run_id,)).fetchone()
    generation = Counter(row["generation_status"] for row in candidates)
    valid = generation["valid_candidate"]
    attempted = valid + generation["invalid_candidate"] + generation["malformed_response"]
    eligible = [row for row in candidates if row["eligible"] and _finite(row["dev_penalized_mean"]) is not None]
    # Match the research agent's preference for feasibility, then completion, then objective.
    best = max(eligible, key=lambda row: (
        row["dev_all_feasible"] == 1, row["dev_completion_rate"] or 0.0,
        -row["dev_penalized_mean"], -row["global_ordinal"],
    ), default=None)
    peak = best["global_ordinal"] if best is not None else None
    hypotheses_path = run_dir / "hypotheses.jsonl"
    hypotheses = _jsonl(hypotheses_path)
    hypotheses_ids = {row["hypothesis_id"] for row in hypotheses if row.get("hypothesis_id")}
    evaluations, have_eval_logs, resumed_session = _logged_evaluations(run_dir)
    progress = _last_search_progress(run_dir)
    behavior_source = "evaluation_facts" if progress else None
    if have_eval_logs and (resumed_session or not progress):
        progress = _behavior_metrics([], evaluations)
        behavior_source = "evaluation_logs"
    events = summary.get("trajectory_control_events")
    event_counts = Counter(event["event"] for event in (events or []))
    tokens = summary.get("token_summary") or {}
    cost = summary.get("cost_summary") or {}
    checkpoint_path = run_dir / "agent_checkpoint.json"
    wall_seconds = wall["wall_offset_seconds"] if wall is not None else (
        _json(checkpoint_path).get("accumulated_wall_seconds") if checkpoint_path.is_file() else None
    )
    return {
        "total_requests": total,
        "generation_counts": dict(generation),
        "candidate_attempt_count": attempted,
        "valid_candidate_count": valid,
        "valid_candidate_rate": _rate(valid, attempted),
        **{f"{name}_count": count for name, count in _candidate_errors(evaluations, have_eval_logs).items()},
        **_tool_metrics(run_dir),
        "behavior_source": behavior_source,
        "behavior_comparable_coverage": progress.get("behavior_comparable_coverage"),
        "behavior_duplicate_rate": progress.get("behavior_duplicate_rate"),
        "behavior_generated_count": progress.get("behavior_generated_denominator"),
        "behavior_comparable_count": progress.get("behavior_comparable_count"),
        "hypothesis_ledger_total_lines": len(hypotheses) if hypotheses_path.is_file() else None,
        "hypothesis_ledger_distinct_ids": len(hypotheses_ids) if hypotheses_path.is_file() else None,
        "peak_request_ordinal": peak,
        "post_peak_waste_pct": 100.0 * (total - peak) / total if total and peak is not None else None,
        "early_stop_count": event_counts["stagnation_early_stop"] if events is not None else None,
        "stagnation_gate_count": event_counts["stagnation_diagnostic_required"] if events is not None else None,
        "basin_restart_count": event_counts["basin_restart"] if events is not None else None,
        "wall_seconds": wall_seconds,
        "input_tokens": tokens.get("input_tokens"),
        "output_tokens": tokens.get("output_tokens"),
        "cached_tokens": tokens.get("cached_tokens"),
        "total_tokens": tokens.get("total_tokens"),
        "priced_cost_usd": cost.get("priced_cost_usd"),
        "unpriced_attempts": cost.get("unpriced_attempts"),
        "winner_source": metadata.get("winner_source"),
        "winner_source_ordinal": metadata.get("winner_source_ordinal"),
    }


def _completed(row: Mapping[str, Any], exact_k: bool = False) -> bool:
    return bool(
        row["completed"] and row["feasible"] and not row["budget_exhausted"]
        and row["objective"] is not None and (not exact_k or row["exact_k_feasible"] is True)
    )


def _penalized(row: Mapping[str, Any], exact_k: bool = False) -> float:
    completed = _completed(row, exact_k)
    value = _finite(row["objective"] if completed else row["reference_objective"])
    if value is None:
        raise ValueError(f"missing_m5_objective_or_penalty_reference:{row['instance_id']}")
    return value if completed else 2.0 * value


def _metrics(rows: Sequence[Mapping[str, Any]], *, exact_k: bool = False) -> dict[str, Any]:
    completed = [row for row in rows if _completed(row, exact_k)]
    feasible = [
        row for row in rows if row["feasible"] and row["objective"] is not None
        and (not exact_k or row["exact_k_feasible"] is True)
    ]
    timeout_count = sum(row["budget_exhausted"] for row in rows)
    # Some external records can lack a BKS, in which case penalization is undefined.
    can_penalize = all(_completed(row, exact_k) or _finite(row["reference_objective"]) is not None for row in rows)
    return {
        "instance_count": len(rows),
        "completed_count": len(completed),
        "completion_rate": _rate(len(completed), len(rows)),
        "feasible_count": len(feasible),
        "feasibility_rate": _rate(len(feasible), len(rows)),
        "timeout_count": timeout_count,
        "timeout_rate": _rate(timeout_count, len(rows)),
        "overall_penalized_mean_objective": _mean([_penalized(row, exact_k) for row in rows]) if can_penalize else None,
        "raw_feasible_mean_objective": _mean([row["objective"] for row in feasible]),
        "completed_mean_objective": _mean([row["objective"] for row in completed]),
    }


def _fleet_metrics(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    exact = [row for row in rows if row.get("exact_k_applicable", row["exact_k_feasible"] is not None)]
    return {
        "free_fleet": _metrics(rows),
        "exact_k": _metrics(exact, exact_k=True) if exact else None,
    }


def _group_metrics(rows: Sequence[Mapping[str, Any]], sizes: Sequence[int]) -> dict[str, Any]:
    return {
        **_fleet_metrics(rows),
        "by_size": {str(size): _fleet_metrics([row for row in rows if row["size"] == size]) for size in sizes},
    }


def _indexed(rows: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    indexed = {row["instance_id"]: row for row in rows}
    if len(indexed) != len(rows):
        raise ValueError("duplicate_m5_instance_record")
    return indexed


def _common_completed(
    left: Sequence[Mapping[str, Any]], right: Sequence[Mapping[str, Any]], *, exact_k: bool = False,
) -> dict[str, Any]:
    pairs = [
        (lrow["objective"], rrow["objective"])
        for lrow, rrow in zip(left, right, strict=True)
        if _completed(lrow, exact_k) and _completed(rrow, exact_k)
    ]
    left_mean = _mean([pair[0] for pair in pairs])
    right_mean = _mean([pair[1] for pair in pairs])
    return {
        "instance_count": len(pairs),
        "left_mean_objective": left_mean,
        "right_mean_objective": right_mean,
        "relative_gain_pct": (
            100.0 * (right_mean - left_mean) / right_mean
            if left_mean is not None and right_mean else None
        ),
    }


def _paired_contrast(
    left: Sequence[Mapping[str, Any]], right: Sequence[Mapping[str, Any]], *, seed: int,
) -> dict[str, Any]:
    left_by_id, right_by_id = _indexed(left), _indexed(right)
    if not left_by_id or left_by_id.keys() != right_by_id.keys():
        raise ValueError("m5_paired_instance_ids_mismatch")
    left = list(left_by_id.values())
    right = [right_by_id[row["instance_id"]] for row in left]
    if any(
        (lrow["size"], lrow["reference_objective"]) != (rrow["size"], rrow["reference_objective"])
        for lrow, rrow in zip(left, right, strict=True)
    ):
        raise ValueError("m5_paired_instance_metadata_mismatch")
    left_values = [_penalized(row) for row in left]
    right_values = [_penalized(row) for row in right]
    exact_applicable = all(
        row.get("exact_k_applicable", row.get("exact_k_feasible") is not None)
        for row in (*left, *right)
    )
    exact_block = None
    if exact_applicable:
        left_exact = [_penalized(row, exact_k=True) for row in left]
        right_exact = [_penalized(row, exact_k=True) for row in right]
        exact_block = {
            "wilcoxon": paired_wilcoxon_signed_rank(left_exact, right_exact),
            "bootstrap": paired_bootstrap_comparison(left_exact, right_exact, n_boot=10000, seed=seed),
        }
    return {
        "overall": {
            "wilcoxon": paired_wilcoxon_signed_rank(left_values, right_values),
            "bootstrap": paired_bootstrap_comparison(left_values, right_values, n_boot=10000, seed=seed),
            "exact_k": exact_block,
        },
        "common_completed": {
            "free_fleet": _common_completed(left, right),
            "exact_k": _common_completed(left, right, exact_k=True),
            "by_size": {
                str(size): {
                    "free_fleet": _common_completed(
                        [row for row in left if row["size"] == size], [row for row in right if row["size"] == size],
                    ),
                    "exact_k": _common_completed(
                        [row for row in left if row["size"] == size], [row for row in right if row["size"] == size],
                        exact_k=True,
                    ),
                } for size in SIZES
            },
        },
    }


def _contrasts(
    protocol: Mapping[str, Any],
    by_cell: Mapping[str, Sequence[Mapping[str, Any]]],
    comparators: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    result = {}
    arm_seeds = protocol["arm_seeds"]
    for family, contrasts in protocol["contrast_families"].items():
        rows = []
        for left, right in contrasts:
            for seed in arm_seeds.get(left, []):
                if right in ARMS and seed not in arm_seeds.get(right, []):
                    continue
                left_rows = by_cell.get(f"{left}:{seed}")
                right_rows = by_cell.get(f"{right}:{seed}") if right in ARMS else comparators.get(right)
                base = {"left": left, "right": right, "seed": seed}
                if left_rows is None or right_rows is None:
                    rows.append({**base, "status": "unavailable"})
                else:
                    rows.append({**base, "status": "paired", **_paired_contrast(left_rows, right_rows, seed=seed)})
        # Keep missing seed pairs in the predeclared family without imputing an
        # effect or publishing an adjusted p-value for them.
        adjusted = holm_bonferroni_adjust([
            row["overall"]["wilcoxon"]["p_two_sided"] if row["status"] == "paired" else 1.0
            for row in rows
        ])
        exact_rows = [
            row for row in rows
            if row["status"] == "paired" and row["overall"].get("exact_k") is not None
        ]
        exact_adjusted = holm_bonferroni_adjust([
            row["overall"]["exact_k"]["wilcoxon"]["p_two_sided"]
            if (row["status"] == "paired" and row["overall"].get("exact_k") is not None) else 1.0
            for row in rows
        ]) if exact_rows else []
        for idx, (row, p_value) in enumerate(zip(rows, adjusted, strict=True)):
            if row["status"] == "paired":
                row["overall"]["wilcoxon_p_holm"] = p_value
                if exact_adjusted and row["overall"].get("exact_k") is not None:
                    row["overall"]["exact_k"]["wilcoxon_p_holm"] = exact_adjusted[idx]
        result[family] = rows
    return result


def _numeric_means(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    keys = dict.fromkeys(key for row in rows for key in row)
    result = {}
    for key in keys:
        values = [row.get(key) for row in rows]
        numbers = [value for item in values if (value := _finite(item)) is not None]
        if numbers:
            result[key] = _mean(numbers)
        elif any(isinstance(value, Mapping) for value in values):
            result[key] = _numeric_means([value for value in values if isinstance(value, Mapping)])
        elif all(value is None for value in values):
            result[key] = None
    return result


def _check_report_binding(doc: Mapping[str, Any], lock_args: Mapping[str, Any]) -> None:
    if (
        doc.get("protocol_sha256") != lock_args["expected_protocol_sha256"]
        or doc.get("roster_lock_sha256") != lock_args["expected_roster_lock_sha256"]
    ):
        raise ValueError("m5_evaluation_report_binding_mismatch")


def _report_markdown(report: Mapping[str, Any]) -> str:
    def fmt(value: float | None) -> str:
        return f"{value:.4f}" if value is not None else "—"

    lines = [
        "# M5 CVRP trajectory control", "",
        "Arm means weight each available seed equally. Exact-k uses the nearest-neighbor fleet target on blind instances.", "",
        "| Arm | Evaluated seeds | Penalized objective | Completed | Exact-k completed | Requests | Valid candidates | USD |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for arm, arm_row in report["per_arm"].items():
        blind = arm_row["mean_seed_metrics"]
        free, exact = blind.get("free_fleet") or {}, blind.get("exact_k") or {}
        trajectory = arm_row["mean_trajectory"]
        lines.append(
            f"| {arm} | {arm_row['evaluated_seed_count']} | {fmt(free.get('overall_penalized_mean_objective'))}"
            f" | {fmt(free.get('completion_rate'))} | {fmt(exact.get('completion_rate'))}"
            f" | {fmt(trajectory.get('total_requests'))} | {fmt(trajectory.get('valid_candidate_count'))}"
            f" | {fmt(trajectory.get('priced_cost_usd'))} |"
        )
    lines += ["", "## Paired blind results by seed", "",
              "| Contrast | Seed | Bootstrap gain (%) | Holm-adjusted p | Common completed |",
              "| --- | ---: | ---: | ---: | ---: |"]
    for family_rows in report["contrasts"].values():
        for row in family_rows:
            overall = row.get("overall", {})
            common = row.get("common_completed", {}).get("free_fleet", {})
            lines.append(
                f"| {row['left']} vs {row['right']} | {row['seed']}"
                f" | {fmt(overall.get('bootstrap', {}).get('rel_gain_vs_baseline_pct'))}"
                f" | {fmt(overall.get('wilcoxon_p_holm'))} | {common.get('instance_count', '—')} |"
            )
    lines += ["", "The JSON report contains per-size, fleet, external-suite, and trajectory detail.", ""]
    return "\n".join(lines)


def cmd_report(args: argparse.Namespace) -> int:
    out_dir = _output_dir(args)
    bundle = _json(out_dir / LOCK_BUNDLE)
    lock_args = _lock_args(bundle, out_dir)
    protocol, solvers, missing = load_locked_m5_roster(**lock_args)
    blind = _json(out_dir / "blind_120_eval" / "m5_blind_evaluation.json")
    external = _json(out_dir / EXTERNAL_EVALUATION)
    for doc in (blind, external):
        _check_report_binding(doc, lock_args)
    by_cell: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in blind["records"]:
        by_cell[row["cell"]].append(row)
    expected_count = protocol["blind_commitment"]["instance_count"]
    comparators = blind.get("baseline_records", {})
    if set(by_cell) != set(solvers) or any(
        len(_indexed(rows)) != expected_count for rows in (*by_cell.values(), *comparators.values())
    ):
        raise ValueError("m5_blind_report_incomplete")
    per_cell = {
        cell: _group_metrics(by_cell[cell], SIZES) if cell in by_cell else {"missing_reason": missing[cell]}
        for cell in protocol["roster_cells"]
    }
    trajectory = {
        cell: _trajectory(_run_dir(out_dir, *_parts(cell)), bundle["snapshot_metadata"][cell])
        for cell in protocol["roster_cells"]
    }
    per_arm = {}
    for arm, seeds in protocol["arm_seeds"].items():
        cells = [f"{arm}:{seed}" for seed in seeds]
        available = [per_cell[cell] for cell in cells if cell in by_cell]
        per_arm[arm] = {
            "planned_seed_count": len(seeds),
            "evaluated_seed_count": len(available),
            "mean_seed_metrics": _numeric_means(available),
            "mean_trajectory": _numeric_means([trajectory[cell] for cell in cells]),
        }
    external_suites = {}
    expected_external_solvers = (
        set(solvers)
        | set(bundle["comparator_manifest_sha256"])
        | {f"{algo}@{deadline:g}ms" for algo, deadline in M5_BASELINE_ALGORITHMS}
    )
    for suite_id, suite in external["suites"].items():
        if set(suite["records"]) != expected_external_solvers:
            raise ValueError(f"m5_external_solvers_incomplete:{suite_id}")
        indexed_ids = [tuple(sorted(_indexed(rows))) for rows in suite["records"].values()]
        if not indexed_ids or not indexed_ids[0] or any(ids != indexed_ids[0] for ids in indexed_ids[1:]):
            raise ValueError(f"m5_external_instance_ids_mismatch:{suite_id}")
        sizes = sorted({row["size"] for rows in suite["records"].values() for row in rows})
        exact_ok = suite["vehicle_limit_policy"] != "free_fleet_min_k_lb"
        ref_labels = (
            "cw_parallel_merge@500ms",
            "cw_relocate_2opt@500ms",
            "l3_ctrl@500ms",
            "m32_champion_pruned@500ms",
        )
        indexed_suite = {key: _indexed(rows) for key, rows in suite["records"].items()}
        common_vs = {}
        for solver_key in solvers:
            left_idx = indexed_suite[solver_key]
            left_aligned = list(left_idx.values())
            common_vs[solver_key] = {}
            for ref_key in ref_labels:
                if ref_key not in indexed_suite:
                    continue
                right_aligned = [indexed_suite[ref_key][iid] for iid in left_idx]
                common_vs[solver_key][ref_key] = {
                    "free_fleet": _common_completed(left_aligned, right_aligned),
                    "exact_k": _common_completed(left_aligned, right_aligned, exact_k=True) if exact_ok else None,
                }
        external_suites[suite_id] = {
            "vehicle_limit_policy": suite["vehicle_limit_policy"],
            "per_solver": {key: _group_metrics(rows, sizes) for key, rows in suite["records"].items()},
            "common_completed_vs_comparators": common_vs,
        }
    report = {
        "schema_version": "m5-trajectory-control-report/v1",
        "protocol_sha256": lock_args["expected_protocol_sha256"],
        "roster_lock_sha256": lock_args["expected_roster_lock_sha256"],
        "model2": protocol["model2"],
        "run_mode": bundle["run_mode"],
        "per_cell": per_cell,
        "per_arm": per_arm,
        "comparators_and_baselines": {key: _group_metrics(rows, SIZES) for key, rows in comparators.items()},
        "contrasts": _contrasts(protocol, by_cell, comparators),
        "trajectory_by_cell": trajectory,
        "external_suites": external_suites,
    }
    path = out_dir / f"{REPORT}.json"
    atomic_write_json(path, report)
    atomic_write_text(out_dir / f"{REPORT}.md", _report_markdown(report))
    _show({"report_path": str(path)})
    return 0


def _provider_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--model1", default=None, help=f"Primary DeepSeek model alias (default {DEFAULT_DEEPSEEK}).")
    parser.add_argument("--model2", default=None, help=f"Second model alias (default {DEFAULT_MODEL2}).")
    parser.add_argument("--endpoint", default=os.environ.get(
        "OPENCODE_GO_ENDPOINT", "https://opencode.ai/zen/go/v1/chat/completions",
    ))
    parser.add_argument("--api-key-env", default="OPENCODE_GO_API_KEY")


def _execution_args(parser: argparse.ArgumentParser) -> None:
    _provider_args(parser)
    parser.add_argument("--mode", choices=("mock", "live"), default="live")
    parser.add_argument("--rate-card-json", type=Path)
    parser.add_argument("--request-timeout-s", type=float, default=90.0)
    parser.add_argument("--wall-seconds", type=float, default=14400.0)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--custody-dir", type=Path, default=M5_DEFAULT_CUSTODY_DIR)
    parser.add_argument("--commitment-path", type=Path, default=M5_BLIND_COMMITMENT_PATH)
    sub = parser.add_subparsers(dest="stage", required=True)

    probe = sub.add_parser("probe-models", help="Probe the DeepSeek and Model2 aliases.")
    _provider_args(probe)
    probe.set_defaults(func=cmd_probe_models)

    seal = sub.add_parser("seal-blind", help="Create an external seal and freeze the M5 protocol.")
    seal.add_argument("--model2", default=None, help=f"Second model alias (default {DEFAULT_MODEL2}).")
    seal.add_argument("--arm-seeds-json", type=Path, help="Path to a JSON object mapping arm names to seed arrays.")
    seal.set_defaults(func=cmd_seal_blind)

    mux = sub.add_parser("emit-mux", help="Emit one mux pane per predeclared arm and seed.")
    _execution_args(mux)
    mux.add_argument("--manifest-path", type=Path)
    mux.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True)
    mux.set_defaults(func=cmd_emit_mux)

    one = sub.add_parser("run-one", help="Run or resume one registered arm and seed.")
    _execution_args(one)
    one.add_argument("--arm", required=True, choices=ARMS)
    one.add_argument("--seed", type=int, required=True)
    one.add_argument("--resume", action="store_true")
    one.set_defaults(func=cmd_run_one)

    for name, fn, help_text in (
        ("lock-roster", cmd_lock_roster, "Lock validated winners from terminal runs."),
        ("unseal-blind", cmd_unseal_blind, "Claim the blind attempt and evaluate the locked roster."),
        ("eval-external", cmd_eval_external, "Evaluate the locked roster on held-out CVRPLib suites."),
        ("report", cmd_report, "Report per-seed contrasts and run trajectories."),
    ):
        sub.add_parser(name, help=help_text).set_defaults(func=fn)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
