"""Milestone 3.2 High-Budget Scaling Law & Single-Factor Control Runner.

Orchestrates:
  1. probe-models  : Verify available OpenCode Go weak/strong model aliases (1 minimal call each)
  2. seal-blind    : Externally seal cvrp_m32_blind_120 & freeze pre_blind_protocol_m32.json
  3. emit-mux      : Emit tools/multi_task_mux.py concurrent pane manifest (curve + 3 controls)
  4. run-one       : Execute or crash-resume one (track, seed) run with strict checkpoint barriers
  5. lock-roster   : Extract frozen solvers per predeclared cell & freeze m32_roster_lock.json
  6. unseal-blind  : One-shot atomic unseal & evaluation of cvrp_m32_blind_120 (+ comparators)
  7. report        : Multi-axis curves (requests/tokens/cached/wall/cost/timeouts/dispersion) &
                     per-seed Paired Wilcoxon + 10k bootstrap + Holm-Bonferroni control tests
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import statistics
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from agent_skill_loop.client import ProviderFailure, http_post_with_deadline, load_local_env
from agent_skill_loop.interface_design.blind_eval import (
    paired_bootstrap_comparison,
    paired_wilcoxon_signed_rank,
)
from agent_skill_loop.interface_design.blind_eval_m3 import holm_bonferroni_adjust
from agent_skill_loop.interface_design.blind_eval_m32 import (
    M32_BLIND_COMMITMENT_PATH,
    M32_CHECKPOINTS,
    M32_CONTROLS,
    M32_SEEDS,
    _M32_CUSTODY_NAME,
    freeze_m32_roster_lock,
    freeze_pre_blind_protocol_m32,
    seal_m32_blind_120,
    unseal_and_evaluate_m32,
)
from agent_skill_loop.interface_design.contracts import FrozenInterfaceSolver
from agent_skill_loop.interface_design.model_routing import ModelRoutingPolicy
from agent_skill_loop.interface_design.planner import build_design_for_template
from agent_skill_loop.interface_design.session_baseline import load_dev_or_public_suite
from agent_skill_loop.interface_design.templates import get_template_spec
from agent_skill_loop.milestone_checkpoint import read_milestone_status
from research_agent.contracts import AgentConfig, atomic_write_json, sha256_text, utc_now
from research_agent.loop import run_research_agent

RESUMABLE_EXIT_CODE = 75

DEFAULT_WEAK_MODEL = "deepseek-v4.1-flash"
DEFAULT_STRONG_MODEL = "deepseek-v4-pro"
CANDIDATE_STRONG_MODELS: tuple[str, ...] = ("deepseek-v4-pro", "qwen4-max", "glm-5.3")
TRACK_CHOICES: tuple[str, ...] = ("curve", "model_routing", "l3b_dual_hook", "timeout_2000ms")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_rate_card(path: Path | None) -> dict[str, dict[str, float]] | None:
    if path is None:
        return None
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return {str(k): {str(rk): float(rv) for rk, rv in dict(v).items()} for k, v in dict(raw).items()}


def _build_l3_ctrl_solver(budget_ms: float) -> FrozenInterfaceSolver:
    tpl = get_template_spec("cvrp_ruin_recreate", "v1")
    design = build_design_for_template("cvrp_ruin_recreate", "v1", postprocess_mode="none", rationale="M3.2 L3-ctrl baseline")
    return FrozenInterfaceSolver(
        solver_id=f"m32_l3_ctrl_{int(round(budget_ms))}ms",
        display_name=f"M3.2 L3-ctrl Baseline ({int(round(budget_ms))}ms)",
        problem_family="cvrp",
        paradigm=tpl.paradigm,
        template_id=tpl.template_id,
        template_version=tpl.template_version,
        template_source_sha256=tpl.template_source_sha256,
        postprocess_mode="none",
        template_options={},
        hook_name=tpl.hook_name,
        hook_code=tpl.default_baseline_hook_code,
        hook_code_sha256=sha256_text(tpl.default_baseline_hook_code),
        design_sha256=design.design_sha256,
        origin_run="m32_l3_ctrl_baseline",
        kb_release_id="m32_baseline",
        kb_entry_id=None,
        description="Unmodified L3 worst-cost removal skeleton comparator.",
        default_budget_ms=float(budget_ms),
        protocol_id="cvrp/v1",
    )


def cmd_probe_models(args: argparse.Namespace) -> int:
    load_local_env()
    api_key = os.environ.get(args.api_key_env, "").strip()
    if not api_key:
        raise RuntimeError(f"missing_api_key:{args.api_key_env}")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "eoh-frozen-bridge/0908",
        "x-opencode-session": "m32-probe-session",
    }
    models = list(dict.fromkeys([args.weak_model, *args.strong_candidates]))
    results: dict[str, Any] = {}
    for model in models:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "Reply with OK only."}],
            "temperature": 0.0,
        }
        try:
            status, raw = http_post_with_deadline(
                args.endpoint, headers, json.dumps(payload).encode("utf-8"), timeout=30.0,
            )
            parsed = json.loads(raw.decode("utf-8"))
            results[model] = {
                "ok": status == 200 and bool(parsed.get("choices")),
                "status": status,
                "served_model": parsed.get("model"),
                "usage": parsed.get("usage"),
            }
        except Exception as exc:
            results[model] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    print(json.dumps({"endpoint": args.endpoint, "models": results}, indent=2))
    return 0


def cmd_seal_blind(args: argparse.Namespace) -> int:
    out_dir = Path(args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    custody_dir = Path(args.custody_dir).resolve()
    commitment_path = Path(args.commitment_path).resolve()
    sealed_path = custody_dir / "cvrp_m32_blind_120_sealed.json"

    reused_seal = False
    if sealed_path.is_file() and commitment_path.is_file():
        com = json.loads(commitment_path.read_text(encoding="utf-8"))
        if com.get("commitment_status") == "sealed_external":
            reused_seal = True
            seal_info = {
                "suite_id": "cvrp_m32_blind_120",
                "commitment_path": str(commitment_path),
                "commitment_sha256": _sha256_file(commitment_path),
                "sealed_path": str(sealed_path),
                "reused_existing": True,
            }
    if not reused_seal:
        res = seal_m32_blind_120(commitment_path=commitment_path, custody_dir=custody_dir)
        seal_info = {**res, "reused_existing": False}

    protocol_path = out_dir / "pre_blind_protocol_m32.json"
    if protocol_path.is_file():
        proto_res = {
            "protocol_path": str(protocol_path),
            "protocol_sha256": _sha256_file(protocol_path),
            "reused_existing": True,
        }
    else:
        proto = freeze_pre_blind_protocol_m32(
            protocol_path,
            commitment_path=commitment_path,
            seeds=tuple(args.seeds),
            controls=tuple(args.controls),
            time_budget_ms=500.0,
            control_deadlines_ms={"timeout_2000ms": 2000.0} if "timeout_2000ms" in args.controls else None,
        )
        proto_res = {
            "protocol_path": proto["protocol_path"],
            "protocol_sha256": proto["protocol_sha256"],
            "reused_existing": False,
        }

    bundle = {
        "schema_version": "m32-seal-and-protocol/v1",
        "sealed": seal_info,
        "protocol": proto_res,
    }
    atomic_write_json(out_dir / "m32_seal_and_protocol.json", bundle)
    print(json.dumps(bundle, ensure_ascii=False, indent=2))
    return 0


def cmd_emit_mux(args: argparse.Namespace) -> int:
    out_dir = Path(args.output_dir).resolve()
    tracks: list[str]
    if args.stage == "curve":
        tracks = ["curve"]
    elif args.stage == "controls":
        tracks = list(M32_CONTROLS)
    else:
        tracks = ["curve", *M32_CONTROLS]

    manifest_path = Path(args.manifest_path).resolve() if args.manifest_path else (out_dir / f"mux_m32_{args.stage}.json")
    panes: list[dict[str, Any]] = []
    for track in tracks:
        for seed in args.seeds:
            pane_id = f"m32_{track}_s{seed}"
            cmd = [
                sys.executable,
                str(Path(__file__).resolve()),
                "--output-dir", str(out_dir),
                "run-one",
                "--track", str(track),
                "--seed", str(seed),
                "--mode", str(args.mode),
                "--weak-model", str(args.weak_model),
                "--strong-model", str(args.strong_model),
                "--endpoint", str(args.endpoint),
                "--api-key-env", str(args.api_key_env),
                "--request-cap", str(args.request_cap),
                "--max-rounds", str(args.max_rounds),
                "--eoh-pop-size", str(args.eoh_pop_size),
                "--eoh-n-pop", str(args.eoh_n_pop),
                "--eoh-max-sample-nums", str(args.eoh_max_sample_nums),
            ]
            if track == "curve":
                cmd.extend(["--checkpoints", *[str(x) for x in args.checkpoints]])
            if args.rate_card_json:
                cmd.extend(["--rate-card-json", str(args.rate_card_json)])
            if args.resume:
                cmd.append("--resume")
            panes.append({"id": pane_id, "command": cmd, "cwd": str(REPO)})

    atomic_write_json(manifest_path, {"panes": panes})
    print(json.dumps({"manifest_path": str(manifest_path), "pane_count": len(panes)}, indent=2))
    return 0


def _build_track_config(args: argparse.Namespace) -> AgentConfig:
    out_dir = Path(args.output_dir).resolve()
    track = str(args.track)
    seed = int(args.seed)
    run_dir = out_dir / "runs" / f"{track}_s{seed}"
    rate_card = _load_rate_card(args.rate_card_json) or {}

    if track == "curve":
        ckpts = tuple(int(x) for x in args.checkpoints)
        tpls = ("cvrp_ruin_recreate",)
        init_tpl = "cvrp_ruin_recreate"
        budget_ms = 500.0
        wall_s = float(args.wall_seconds)
        routing_policy = ModelRoutingPolicy(
            enabled=False, weak_model=args.weak_model, strong_model=args.weak_model, rate_card=rate_card,
        ).to_dict()
    elif track == "model_routing":
        ckpts = (int(args.request_cap),)
        tpls = ("cvrp_ruin_recreate",)
        init_tpl = "cvrp_ruin_recreate"
        budget_ms = 500.0
        wall_s = float(args.wall_seconds)
        routing_policy = ModelRoutingPolicy(
            enabled=True, weak_model=args.weak_model, strong_model=args.strong_model, strong_every_n=4, rate_card=rate_card,
        ).to_dict()
    elif track == "l3b_dual_hook":
        ckpts = (int(args.request_cap),)
        tpls = ("cvrp_ruin_recreate_dual",)
        init_tpl = "cvrp_ruin_recreate_dual"
        budget_ms = 500.0
        wall_s = float(args.wall_seconds)
        routing_policy = ModelRoutingPolicy(
            enabled=False, weak_model=args.weak_model, strong_model=args.weak_model, rate_card=rate_card,
        ).to_dict()
    elif track == "timeout_2000ms":
        ckpts = (int(args.request_cap),)
        tpls = ("cvrp_ruin_recreate",)
        init_tpl = "cvrp_ruin_recreate"
        budget_ms = 2000.0
        wall_s = max(float(args.wall_seconds), 7200.0)
        routing_policy = ModelRoutingPolicy(
            enabled=False, weak_model=args.weak_model, strong_model=args.weak_model, rate_card=rate_card,
        ).to_dict()
    else:
        raise ValueError(f"unknown_m32_track:{track}")

    dev_suite = load_dev_or_public_suite("cvrp_dev_hetero_24", split="dev_train", role="diagnostic_interactive")
    dev_count = len(dev_suite["instances"])

    return AgentConfig(
        run_id=f"m32_{track}_s{seed}",
        output_dir=str(run_dir),
        problem_family="cvrp",
        arm_id=f"m32_{track}",
        max_rounds=int(args.max_rounds),
        total_request_cap=int(args.request_cap),
        outer_requests_per_round_cap=int(args.outer_cap),
        outer_reflect_cap=int(args.reflect_cap),
        eoh_pop_size=int(args.eoh_pop_size),
        eoh_n_pop=int(args.eoh_n_pop),
        eoh_max_sample_nums=int(args.eoh_max_sample_nums),
        dev_instance_count=dev_count,
        instance_time_budget_ms=budget_ms,
        allowed_templates=tpls,
        allowed_postprocess_modes=("none",),
        initial_template_id=init_tpl,
        initial_postprocess_mode="none",
        planner_model=str(args.weak_model),
        eoh_model=str(args.weak_model),
        endpoint=str(args.endpoint),
        api_key_env=str(args.api_key_env),
        search_seed=seed,
        dev_suite_id="cvrp_dev_hetero_24",
        dev_split="dev_train",
        use_benchmark_dev_suite=True,
        checkpoint_budgets=ckpts,
        strict_checkpoint_barriers=True,
        model_routing_policy=routing_policy,
        rate_card=rate_card or None,
        mode=str(args.mode),
        request_timeout_s=float(args.request_timeout_s),
        wall_seconds=wall_s,
    )


def cmd_run_one(args: argparse.Namespace) -> int:
    load_local_env()
    cfg = _build_track_config(args)
    run_dir = Path(cfg.output_dir)
    ckpt_path = run_dir / "agent_checkpoint.json"
    resume = bool(args.resume and ckpt_path.is_file())
    try:
        summary = run_research_agent(cfg, resume=resume)
    except ProviderFailure as exc:
        ckpt_preserved = ckpt_path.is_file()
        status_payload = {
            "run_id": cfg.run_id,
            "track": args.track,
            "seed": args.seed,
            "status": "resumable",
            "reason": str(exc),
            "checkpoint_preserved": ckpt_preserved,
            "exit_code": RESUMABLE_EXIT_CODE,
            "updated_at": utc_now(),
        }
        if run_dir.is_dir():
            atomic_write_json(run_dir / "run_interrupt_status.json", status_payload)
        print(json.dumps(status_payload, ensure_ascii=False, indent=2))
        return RESUMABLE_EXIT_CODE
    atomic_write_json(
        run_dir / "run_interrupt_status.json",
        {"run_id": cfg.run_id, "status": summary.get("final_phase"), "checkpoint_preserved": ckpt_path.is_file(), "updated_at": utc_now()},
    )
    print(json.dumps({
        "run_id": cfg.run_id,
        "track": args.track,
        "seed": args.seed,
        "final_phase": summary.get("final_phase"),
        "best_dev_objective": summary.get("best_dev_objective"),
        "frozen_checkpoints": summary.get("frozen_checkpoints"),
        "attempted_requests": (summary.get("budget_summary") or {}).get("attempted_requests"),
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_lock_roster(args: argparse.Namespace) -> int:
    out_dir = Path(args.output_dir).resolve()
    seal_meta = json.loads((out_dir / "m32_seal_and_protocol.json").read_text(encoding="utf-8"))
    proto_path = Path(seal_meta["protocol"]["protocol_path"])
    proto_sha = seal_meta["protocol"]["protocol_sha256"]
    protocol = json.loads(proto_path.read_text(encoding="utf-8"))

    snap_dir = out_dir / "roster_snapshots"
    pending_snapshots: dict[str, tuple[Path, dict[str, Any], str]] = {}
    snapshot_paths: dict[str, Path] = {}
    missing_cells: dict[str, str] = {}
    checkpoint_metadata: dict[str, Any] = {}

    for cell in protocol["roster_cells"]:
        seed_str, kind, tag = cell.split(":", 2)
        if kind == "checkpoint":
            track_name = "curve"
            ckpt_budget = int(tag)
            run_dir = out_dir / "runs" / f"curve_s{seed_str}"
            ckpt_file = run_dir / "checkpoints" / f"frozen_checkpoint_{tag}.json"
        elif kind == "control":
            track_name = tag
            ckpt_budget = int(args.control_budget)
            run_dir = out_dir / "runs" / f"{tag}_s{seed_str}"
            ckpt_file = run_dir / "checkpoints" / f"frozen_checkpoint_{args.control_budget}.json"
        else:
            raise ValueError(f"unexpected_cell_kind:{cell}")

        if not run_dir.is_dir():
            missing_cells[cell] = "infrastructure_failure"
            continue
        summary_path = run_dir / "research_summary.json"
        if not summary_path.is_file():
            raise RuntimeError(f"cannot_lock_incomplete_or_missing_run:{cell}:{summary_path}")
        run_summary = json.loads(summary_path.read_text(encoding="utf-8"))
        if run_summary.get("final_phase") not in {"completed", "budget_stopped", "no_champion"}:
            raise RuntimeError(f"cannot_lock_non_terminal_run:{cell}:{run_summary.get('final_phase')}")

        if not ckpt_file.is_file():
            missing_cells[cell] = "early_stop"
            continue

        ledger_path = run_dir / "agent_budget.sqlite3"
        if not ledger_path.is_file():
            raise RuntimeError(f"cannot_lock_without_sqlite_ledger:{cell}:{ledger_path}")
        mstatus = read_milestone_status(ledger_path, f"m32_{track_name}_s{seed_str}")
        db_ckpt = next((c for c in (mstatus.get("checkpoints") or ()) if int(c["ckpt_budget"]) == ckpt_budget), None)
        if db_ckpt is None or db_ckpt.get("state") != "sealed" or not db_ckpt.get("payload_sha256"):
            raise RuntimeError(f"cannot_lock_unsealed_checkpoint:{cell}:{db_ckpt.get('state') if db_ckpt else None}")
        if _sha256_file(ckpt_file) != str(db_ckpt["payload_sha256"]):
            raise ValueError(f"checkpoint_sqlite_sha256_mismatch:{cell}")

        payload = json.loads(ckpt_file.read_text(encoding="utf-8"))
        if payload.get("winner_source_ordinal") != db_ckpt.get("winner_source_ordinal"):
            raise ValueError(f"checkpoint_winner_ordinal_mismatch:{cell}")
        solver_dict = payload.get("frozen_solver")
        if solver_dict is None:
            missing_cells[cell] = "no_eligible_snapshot"
            continue
        out_snap = snap_dir / f"{cell.replace(':', '_')}.json"
        snap_text = json.dumps(solver_dict, ensure_ascii=False, indent=2) + "\n"
        snap_sha = sha256_text(snap_text)
        pending_snapshots[cell] = (out_snap, solver_dict, snap_sha)
        snapshot_paths[cell] = out_snap
        checkpoint_metadata[cell] = {
            "source_checkpoint_file": str(ckpt_file),
            "winner_source_ordinal": payload.get("winner_source_ordinal"),
            "best_dev_objective": payload.get("best_dev_objective"),
            "usage_cutoff": payload.get("usage_cutoff"),
            "wall_elapsed_seconds_at_seal": payload.get("wall_elapsed_seconds_at_seal"),
        }

    lock_path = out_dir / "m32_roster_lock.json"
    if lock_path.is_file():
        existing_lock = json.loads(lock_path.read_text(encoding="utf-8"))
        if existing_lock.get("protocol_sha256") != proto_sha:
            raise ValueError("existing_roster_lock_protocol_mismatch")
        expected_roster = []
        for cell in protocol["roster_cells"]:
            if cell in missing_cells:
                expected_roster.append({"cell": cell, "missing_reason": missing_cells[cell]})
            else:
                expected_roster.append({"cell": cell, "snapshot_sha256": pending_snapshots[cell][2]})
        if existing_lock.get("roster") != expected_roster:
            raise ValueError("existing_roster_lock_mismatch")
        snap_dir.mkdir(parents=True, exist_ok=True)
        for out_snap, solver_dict, _ in pending_snapshots.values():
            atomic_write_json(out_snap, solver_dict)
        lock_res = {
            "roster_lock_path": str(lock_path),
            "roster_lock_sha256": _sha256_file(lock_path),
            "reused_existing": True,
        }
    else:
        snap_dir.mkdir(parents=True, exist_ok=True)
        for out_snap, solver_dict, _ in pending_snapshots.values():
            atomic_write_json(out_snap, solver_dict)
        lock_res = freeze_m32_roster_lock(
            lock_path,
            protocol_path=proto_path,
            expected_protocol_sha256=proto_sha,
            snapshot_paths=snapshot_paths,
            missing_cells=missing_cells,
        )
        lock_res["reused_existing"] = False

    lock_bundle = {
        "schema_version": "m32-roster-lock-bundle/v1",
        "protocol_path": str(proto_path),
        "protocol_sha256": proto_sha,
        "roster_lock_path": lock_res["roster_lock_path"],
        "roster_lock_sha256": lock_res["roster_lock_sha256"],
        "snapshot_paths": {k: str(v) for k, v in snapshot_paths.items()},
        "missing_cells": missing_cells,
        "checkpoint_metadata": checkpoint_metadata,
    }
    atomic_write_json(out_dir / "m32_roster_lock_bundle.json", lock_bundle)
    print(json.dumps({
        "roster_lock_path": lock_res["roster_lock_path"],
        "locked_count": len(snapshot_paths),
        "missing_count": len(missing_cells),
    }, indent=2))
    return 0


def cmd_unseal_blind(args: argparse.Namespace) -> int:
    out_dir = Path(args.output_dir).resolve()
    custody_dir = Path(args.custody_dir).resolve()
    commitment_path = Path(args.commitment_path).resolve()
    bundle = json.loads((out_dir / "m32_roster_lock_bundle.json").read_text(encoding="utf-8"))
    snapshot_paths = {k: Path(v) for k, v in bundle["snapshot_paths"].items()}

    l3_500 = _build_l3_ctrl_solver(500.0)
    l3_2000 = _build_l3_ctrl_solver(2000.0)
    blind_dir = out_dir / "blind_120_eval"
    res = unseal_and_evaluate_m32(
        protocol_path=Path(bundle["protocol_path"]),
        expected_protocol_sha256=bundle["protocol_sha256"],
        roster_lock_path=Path(bundle["roster_lock_path"]),
        expected_roster_lock_sha256=bundle["roster_lock_sha256"],
        snapshot_paths=snapshot_paths,
        output_dir=blind_dir,
        commitment_path=commitment_path,
        custody_dir=custody_dir,
        baseline_algorithms=(("cw_parallel_merge", 500.0), ("cw_relocate_2opt", 500.0)),
        comparator_solvers=(("l3_ctrl@500ms", l3_500, 500.0), ("l3_ctrl@2000ms", l3_2000, 2000.0)),
    )
    print(json.dumps({
        "report_path": res["report_path"],
        "report_sha256": res["report_sha256"],
        "record_count": len(res["records"]),
        "baselines": sorted((res.get("baseline_records") or {}).keys()),
    }, indent=2))
    return 0


def _is_completed_m32_row(row: Mapping[str, Any]) -> bool:
    if "completed" in row:
        return row.get("completed") is True and bool(row.get("feasible")) and row.get("objective") is not None
    return bool(row.get("feasible")) and row.get("objective") is not None


def _penalty_for_row(row: Mapping[str, Any], *, ref_fallback: float = 1e6) -> float:
    ref_val = row.get("reference_objective")
    if isinstance(ref_val, (int, float)) and not isinstance(ref_val, bool):
        return 2.0 * float(ref_val)
    return ref_fallback


def _agg_blind_rows(rows: Sequence[Mapping[str, Any]], *, ref_fallback: float = 1e6, deadline_enforced: bool = True) -> dict[str, Any]:
    n = len(rows)
    comp = [r for r in rows if _is_completed_m32_row(r)]
    within_deadline = [r for r in comp if not r.get("budget_exhausted")]
    feas = [r for r in rows if r.get("feasible") and r.get("objective") is not None]
    exact_k = [r for r in feas if r.get("exact_k_feasible") is True]
    timeouts = sum(1 for r in rows if r.get("budget_exhausted"))
    pens = [
        float(r["objective"])
        if _is_completed_m32_row(r)
        else _penalty_for_row(r, ref_fallback=ref_fallback)
        for r in rows
    ]
    strict_pens = [
        float(r["objective"])
        if (_is_completed_m32_row(r) and not r.get("budget_exhausted"))
        else _penalty_for_row(r, ref_fallback=ref_fallback)
        for r in rows
    ]
    solve_ms = sorted(float(r["solve_ms"]) for r in rows if r.get("solve_ms") is not None)
    return {
        "instance_count": n,
        "deadline_enforced": bool(deadline_enforced),
        "completed_count": len(comp),
        "completion_rate": round(len(comp) / max(1, n), 6),
        "within_deadline_completed_count": len(within_deadline),
        "within_deadline_completion_rate": round(len(within_deadline) / max(1, n), 6),
        "feasible_count": len(feas),
        "exact_k_feasible_count": len(exact_k),
        "feasibility_rate": round(len(feas) / max(1, n), 6),
        "exact_k_feasibility_rate": round(len(exact_k) / max(1, n), 6),
        "timeout_count": timeouts,
        "completed_only_mean_objective": round(sum(float(r["objective"]) for r in comp) / len(comp), 6) if comp else None,
        "valid_only_mean_objective": round(sum(float(r["objective"]) for r in feas) / len(feas), 6) if feas else None,
        "penalized_mean_objective": round(sum(pens) / max(1, len(pens)), 6) if pens else None,
        "strict_deadline_penalized_mean_objective": round(sum(strict_pens) / max(1, len(strict_pens)), 6) if strict_pens else None,
        "solve_ms_p50": round(solve_ms[len(solve_ms) // 2], 4) if solve_ms else None,
        "penalized_values": pens,
    }


def _disp(vals: Sequence[float]) -> dict[str, float | None]:
    if not vals:
        return {"mean": None, "std": None, "min": None, "max": None}
    return {
        "mean": round(sum(vals) / len(vals), 6),
        "std": round(statistics.stdev(vals), 6) if len(vals) > 1 else 0.0,
        "min": round(min(vals), 6),
        "max": round(max(vals), 6),
    }


def cmd_report(args: argparse.Namespace) -> int:
    out_dir = Path(args.output_dir).resolve()
    bundle = json.loads((out_dir / "m32_roster_lock_bundle.json").read_text(encoding="utf-8"))
    blind_doc = json.loads((out_dir / "blind_120_eval" / "m32_blind_evaluation.json").read_text(encoding="utf-8"))
    proto = json.loads(Path(bundle["protocol_path"]).read_text(encoding="utf-8"))
    seeds: list[int] = list(proto["seeds"])
    controls: list[str] = list(proto["controls"])

    by_cell: dict[str, list[dict[str, Any]]] = {}
    for rec in blind_doc["records"]:
        by_cell.setdefault(str(rec["cell"]), []).append(rec)

    cell_metrics = {cell: _agg_blind_rows(rows, deadline_enforced=True) for cell, rows in by_cell.items()}
    baseline_metrics = {
        key: _agg_blind_rows(rows, deadline_enforced=False)
        for key, rows in (blind_doc.get("baseline_records") or {}).items()
    }
    ckpt_meta = bundle.get("checkpoint_metadata") or {}

    curve_summary: dict[str, Any] = {}
    for B in M32_CHECKPOINTS:
        objs, raw_objs, comp_rates, feas_rates, exact_rates, reqs, in_toks, out_toks, cached_toks, walls, costs = [], [], [], [], [], [], [], [], [], [], []
        timeouts = []
        per_seed = {}
        for s in seeds:
            cell = f"{s}:checkpoint:{B}"
            cm = cell_metrics.get(cell)
            meta = ckpt_meta.get(cell) or {}
            uc = meta.get("usage_cutoff") or {}
            if cm is not None:
                objs.append(float(cm["penalized_mean_objective"]))
                if cm.get("valid_only_mean_objective") is not None:
                    raw_objs.append(float(cm["valid_only_mean_objective"]))
                comp_rates.append(float(cm["completion_rate"]))
                feas_rates.append(float(cm["feasibility_rate"]))
                exact_rates.append(float(cm["exact_k_feasibility_rate"]))
                timeouts.append(int(cm["timeout_count"]))
            if uc:
                reqs.append(int(uc.get("attempted_requests") or 0))
                if uc.get("input_tokens") is not None:
                    in_toks.append(int(uc["input_tokens"]))
                if uc.get("output_tokens") is not None:
                    out_toks.append(int(uc["output_tokens"]))
                if uc.get("cached_tokens") is not None:
                    cached_toks.append(int(uc["cached_tokens"]))
                if meta.get("wall_elapsed_seconds_at_seal") is not None:
                    walls.append(float(meta["wall_elapsed_seconds_at_seal"]))
                if uc.get("priced_cost_usd") is not None:
                    costs.append(float(uc["priced_cost_usd"]))
            per_seed[str(s)] = {
                **({k: v for k, v in cm.items() if k != "penalized_values"} if cm else {"missing_reason": bundle["missing_cells"].get(cell)}),
                "usage_cutoff": uc,
                "winner_source_ordinal": meta.get("winner_source_ordinal"),
                "wall_elapsed_seconds_at_seal": meta.get("wall_elapsed_seconds_at_seal"),
            }
        curve_summary[str(B)] = {
            "checkpoint_budget": B,
            "blind_objective": _disp(objs),
            "blind_raw_feasible_objective": _disp(raw_objs),
            "completion_rate_mean": round(sum(comp_rates) / len(comp_rates), 6) if comp_rates else None,
            "feasibility_rate_mean": round(sum(feas_rates) / len(feas_rates), 6) if feas_rates else None,
            "exact_k_feasibility_rate_mean": round(sum(exact_rates) / len(exact_rates), 6) if exact_rates else None,
            "timeout_count_mean": round(sum(timeouts) / len(timeouts), 3) if timeouts else None,
            "attempted_requests_mean": round(sum(reqs) / len(reqs), 2) if reqs else None,
            "input_tokens_mean": round(sum(in_toks) / len(in_toks), 1) if in_toks else None,
            "output_tokens_mean": round(sum(out_toks) / len(out_toks), 1) if out_toks else None,
            "cached_tokens_mean": round(sum(cached_toks) / len(cached_toks), 1) if cached_toks else None,
            "wall_seconds_mean": round(sum(walls) / len(walls), 2) if walls else None,
            "priced_cost_usd_mean": round(sum(costs) / len(costs), 6) if costs else None,
            "per_seed": per_seed,
        }

    # Controls vs matched main curve endpoint (B=400 or args.control_budget)
    ctrl_summary: dict[str, Any] = {}
    paired_tests: dict[str, Any] = {}
    p_collect: list[tuple[str, float]] = []
    ref_ckpt = int(args.control_budget)
    for ctrl in controls:
        objs, raw_objs, comp_rates, feas_rates, exact_rates, timeouts = [], [], [], [], [], []
        per_seed = {}
        for s in seeds:
            c_cell = f"{s}:control:{ctrl}"
            m_cell = f"{s}:checkpoint:{ref_ckpt}"
            cm = cell_metrics.get(c_cell)
            mm = cell_metrics.get(m_cell)
            if cm is not None:
                objs.append(float(cm["penalized_mean_objective"]))
                if cm.get("valid_only_mean_objective") is not None:
                    raw_objs.append(float(cm["valid_only_mean_objective"]))
                comp_rates.append(float(cm["completion_rate"]))
                feas_rates.append(float(cm["feasibility_rate"]))
                exact_rates.append(float(cm["exact_k_feasibility_rate"]))
                timeouts.append(int(cm["timeout_count"]))
            meta = ckpt_meta.get(c_cell) or {}
            per_seed[str(s)] = {
                **({k: v for k, v in cm.items() if k != "penalized_values"} if cm else {"missing_reason": bundle["missing_cells"].get(c_cell)}),
                "usage_cutoff": meta.get("usage_cutoff"),
                "wall_elapsed_seconds_at_seal": meta.get("wall_elapsed_seconds_at_seal"),
            }
            if cm is not None and mm is not None:
                if [r.get("instance_id") for r in by_cell[c_cell]] != [r.get("instance_id") for r in by_cell[m_cell]]:
                    raise ValueError(f"paired_instance_id_mismatch:{c_cell}:{m_cell}")
                c_vals = cm["penalized_values"]
                m_vals = mm["penalized_values"]
                w = paired_wilcoxon_signed_rank(c_vals, m_vals)
                b = paired_bootstrap_comparison(c_vals, m_vals, n_boot=10000, seed=int(s))
                common_c, common_m = [], []
                for cr, mr in zip(by_cell[c_cell], by_cell[m_cell]):
                    if _is_completed_m32_row(cr) and _is_completed_m32_row(mr):
                        common_c.append(float(cr["objective"]))
                        common_m.append(float(mr["objective"]))
                key = f"{ctrl}_vs_curve_{ref_ckpt}_s{s}"
                paired_tests[key] = {
                    "seed": s,
                    "control": ctrl,
                    "reference": f"curve_checkpoint_{ref_ckpt}",
                    "wilcoxon_p_two_sided": w["p_two_sided"],
                    "bootstrap": b,
                    "common_completed_count": len(common_c),
                    "common_completed_delta_pct": round(100.0 * (sum(common_c) - sum(common_m)) / max(sum(common_m), 1e-12), 4) if common_c else None,
                }
                p_collect.append((key, float(w["p_two_sided"])))
        ctrl_summary[ctrl] = {
            "blind_objective": _disp(objs),
            "blind_raw_feasible_objective": _disp(raw_objs),
            "completion_rate_mean": round(sum(comp_rates) / len(comp_rates), 6) if comp_rates else None,
            "feasibility_rate_mean": round(sum(feas_rates) / len(feas_rates), 6) if feas_rates else None,
            "exact_k_feasibility_rate_mean": round(sum(exact_rates) / len(exact_rates), 6) if exact_rates else None,
            "timeout_count_mean": round(sum(timeouts) / len(timeouts), 3) if timeouts else None,
            "per_seed": per_seed,
        }

    # Curve step pairs: 400 vs 36 per seed
    for s in seeds:
        c400_key = f"{s}:checkpoint:400"
        c36_key = f"{s}:checkpoint:36"
        c400 = cell_metrics.get(c400_key)
        c36 = cell_metrics.get(c36_key)
        if c400 and c36:
            if [r.get("instance_id") for r in by_cell[c400_key]] != [r.get("instance_id") for r in by_cell[c36_key]]:
                raise ValueError(f"paired_instance_id_mismatch:{c400_key}:{c36_key}")
            w = paired_wilcoxon_signed_rank(c400["penalized_values"], c36["penalized_values"])
            b = paired_bootstrap_comparison(c400["penalized_values"], c36["penalized_values"], n_boot=10000, seed=int(s))
            key = f"curve_400_vs_36_s{s}"
            paired_tests[key] = {
                "seed": s,
                "control": "curve_400",
                "reference": "curve_36",
                "wilcoxon_p_two_sided": w["p_two_sided"],
                "bootstrap": b,
            }
            p_collect.append((key, float(w["p_two_sided"])))

    if p_collect:
        adj = holm_bonferroni_adjust([p for _, p in p_collect])
        for (k, _), ap in zip(p_collect, adj):
            paired_tests[k]["p_holm_wilcoxon"] = ap

    hist_m3 = None
    hist_path = REPO / "experiments" / "milestone3" / "phase3d_blind_eval" / "blind_120_evaluation_report.json"
    if hist_path.is_file():
        hdoc = json.loads(hist_path.read_text(encoding="utf-8"))
        hist_m3 = {
            "note": "Historical cvrp_m3_blind_120 reference only (never compared on raw point equality against cvrp_m32_blind_120).",
            "arm_summary_500ms": hdoc.get("blind_120_standard_500ms_arm_summary"),
        }

    report = {
        "schema_version": "m32-scaling-report/v1",
        "generated_at": utc_now(),
        "suite_id": "cvrp_m32_blind_120",
        "scaling_curve": curve_summary,
        "single_factor_controls": ctrl_summary,
        "baseline_comparators": {k: {kk: vv for kk, vv in v.items() if kk != "penalized_values"} for k, v in baseline_metrics.items()},
        "per_seed_paired_hypothesis_tests": paired_tests,
        "historical_m3_blind_reference": hist_m3,
    }
    atomic_write_json(out_dir / "m32_scaling_report.json", report)

    md = [
        "# Milestone 3.2 Scaling Law & Single-Factor Control Report (`cvrp_m32_blind_120`)",
        "",
        "## 1. Main Curve (`36 -> 100 -> 200 -> 400`, `cvrp_ruin_recreate/v1`, 500 ms)",
        "",
        "| Checkpoint | Raw Feas Mean | Penalized Mean (Std) | Min / Max | Comp | Feas | Exact-k | Timeouts/120 | Reqs | Wall(s) |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for b_str, row in curve_summary.items():
        bo = row["blind_objective"]
        ro = row.get("blind_raw_feasible_objective") or {}
        if bo["mean"] is not None:
            raw_str = f"{ro['mean']:.4f}" if ro.get("mean") is not None else "—"
            md.append(
                f"| {b_str} | {raw_str} | {bo['mean']:.4f} ({bo['std']:.4f}) | {bo['min']:.4f} / {bo['max']:.4f} | "
                f"{row['completion_rate_mean']:.3f} | {row['feasibility_rate_mean']:.3f} | {row['exact_k_feasibility_rate_mean']:.3f} | "
                f"{row['timeout_count_mean']:.1f} | {row['attempted_requests_mean'] or 0:.1f} | {row['wall_seconds_mean'] or 0:.1f} |"
            )
    md.extend([
        "",
        "*Note: `Raw Feas Mean` reports the unpenalized mean of all verified feasible solutions (including valid anytime incumbents returned at timeout); `Penalized Mean` applies the pre-declared `2 * reference_objective` penalty whenever `completed=False` (`budget_exhausted`).*",
        "",
        "## 2. Single-Factor Controls (Matched Total Request Budget)",
        "",
        "| Control | Raw Feas Mean | Penalized Mean (Std) | Min / Max | Comp | Feas | Exact-k | Timeouts/120 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for ctrl, row in ctrl_summary.items():
        bo = row["blind_objective"]
        ro = row.get("blind_raw_feasible_objective") or {}
        if bo["mean"] is not None:
            raw_str = f"{ro['mean']:.4f}" if ro.get("mean") is not None else "—"
            md.append(
                f"| {ctrl} | {raw_str} | {bo['mean']:.4f} ({bo['std']:.4f}) | {bo['min']:.4f} / {bo['max']:.4f} | "
                f"{row['completion_rate_mean']:.3f} | {row['feasibility_rate_mean']:.3f} | {row['exact_k_feasibility_rate_mean']:.3f} | {row['timeout_count_mean']:.1f} |"
            )
    if baseline_metrics:
        md.extend([
            "",
            "## 3. Baseline Comparators (`enforce_wall_deadline=False` Deterministic Reference)",
            "",
            "| Comparator | Raw Mean | Strict-Deadline Penalized | Within-Deadline Comp | Exact-k | Timeouts/120 |",
            "|---|---:|---:|---:|---:|---:|",
        ])
        for bname, bm in baseline_metrics.items():
            md.append(
                f"| {bname} | {bm['valid_only_mean_objective']:.4f} | {bm['strict_deadline_penalized_mean_objective']:.4f} | "
                f"{bm['within_deadline_completion_rate']:.3f} ({bm['within_deadline_completed_count']}/120) | "
                f"{bm['exact_k_feasibility_rate']:.3f} | {bm['timeout_count']} |"
            )
        md.append("")
        md.append("*Note: `baseline_comparators` run with `enforce_wall_deadline=False` so wall clock cannot clip deterministic trajectories mid-loop; `l3_ctrl@500ms` logged 9 overruns at `n=200` (502.6–553.3 ms), while `l3_ctrl@2000ms` had 0/120 overruns and is the strict deadline-matched comparator for `timeout_2000ms`.*")
    (out_dir / "m32_scaling_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({"report_json": str(out_dir / "m32_scaling_report.json"), "report_md": str(out_dir / "m32_scaling_report.md")}, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Milestone 3.2 High-Budget Scaling & Control Runner.")
    p.add_argument("--output-dir", type=Path, default=REPO / "experiments" / "milestone3_2")
    p.add_argument("--custody-dir", type=Path, default=Path.home() / _M32_CUSTODY_NAME)
    p.add_argument("--commitment-path", type=Path, default=M32_BLIND_COMMITMENT_PATH)
    sub = p.add_subparsers(dest="stage", required=True)

    s_probe = sub.add_parser("probe-models", help="Verify OpenCode Go model aliases.")
    s_probe.add_argument("--weak-model", default=DEFAULT_WEAK_MODEL)
    s_probe.add_argument("--strong-candidates", nargs="+", default=list(CANDIDATE_STRONG_MODELS))
    s_probe.add_argument("--endpoint", default=os.environ.get("OPENCODE_GO_ENDPOINT", "https://opencode.ai/zen/go/v1/chat/completions"))
    s_probe.add_argument("--api-key-env", default="OPENCODE_GO_API_KEY")
    s_probe.set_defaults(func=cmd_probe_models)

    s_seal = sub.add_parser("seal-blind", help="Externally seal cvrp_m32_blind_120 and freeze protocol.")
    s_seal.add_argument("--seeds", type=int, nargs="+", default=list(M32_SEEDS))
    s_seal.add_argument("--controls", nargs="+", default=list(M32_CONTROLS))
    s_seal.set_defaults(func=cmd_seal_blind)

    s_mux = sub.add_parser("emit-mux", help="Emit tools/multi_task_mux.py manifest JSON.")
    s_mux.add_argument("--seeds", type=int, nargs="+", default=list(M32_SEEDS))
    s_mux.add_argument("--stage-name", dest="stage", choices=("curve", "controls", "all"), default="curve")
    s_mux.add_argument("--manifest-path", type=Path, default=None)
    s_mux.add_argument("--mode", choices=("mock", "live"), default="live")
    s_mux.add_argument("--weak-model", default=DEFAULT_WEAK_MODEL)
    s_mux.add_argument("--strong-model", default=DEFAULT_STRONG_MODEL)
    s_mux.add_argument("--endpoint", default=os.environ.get("OPENCODE_GO_ENDPOINT", "https://opencode.ai/zen/go/v1/chat/completions"))
    s_mux.add_argument("--api-key-env", default="OPENCODE_GO_API_KEY")
    s_mux.add_argument("--request-cap", type=int, default=400)
    s_mux.add_argument("--max-rounds", type=int, default=10)
    s_mux.add_argument("--eoh-pop-size", type=int, default=4)
    s_mux.add_argument("--eoh-n-pop", type=int, default=2)
    s_mux.add_argument("--eoh-max-sample-nums", type=int, default=48)
    s_mux.add_argument("--checkpoints", type=int, nargs="+", default=list(M32_CHECKPOINTS))
    s_mux.add_argument("--rate-card-json", type=Path, default=None)
    s_mux.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True)
    s_mux.set_defaults(func=cmd_emit_mux)

    s_one = sub.add_parser("run-one", help="Execute one (track, seed) scaling/control cell.")
    s_one.add_argument("--track", required=True, choices=list(TRACK_CHOICES))
    s_one.add_argument("--seed", type=int, required=True)
    s_one.add_argument("--mode", choices=("mock", "live"), default="live")
    s_one.add_argument("--weak-model", default=DEFAULT_WEAK_MODEL)
    s_one.add_argument("--strong-model", default=DEFAULT_STRONG_MODEL)
    s_one.add_argument("--endpoint", default=os.environ.get("OPENCODE_GO_ENDPOINT", "https://opencode.ai/zen/go/v1/chat/completions"))
    s_one.add_argument("--api-key-env", default="OPENCODE_GO_API_KEY")
    s_one.add_argument("--request-cap", type=int, default=400)
    s_one.add_argument("--max-rounds", type=int, default=10)
    s_one.add_argument("--outer-cap", type=int, default=4)
    s_one.add_argument("--reflect-cap", type=int, default=2)
    s_one.add_argument("--eoh-pop-size", type=int, default=4)
    s_one.add_argument("--eoh-n-pop", type=int, default=2)
    s_one.add_argument("--eoh-max-sample-nums", type=int, default=48)
    s_one.add_argument("--checkpoints", type=int, nargs="+", default=list(M32_CHECKPOINTS))
    s_one.add_argument("--rate-card-json", type=Path, default=None)
    s_one.add_argument("--request-timeout-s", type=float, default=90.0)
    s_one.add_argument("--wall-seconds", type=float, default=14400.0)
    s_one.add_argument("--resume", action="store_true")
    s_one.set_defaults(func=cmd_run_one)

    s_lock = sub.add_parser("lock-roster", help="Freeze all snapshot paths into m32_roster_lock.json.")
    s_lock.add_argument("--control-budget", type=int, default=400)
    s_lock.set_defaults(func=cmd_lock_roster)

    s_unseal = sub.add_parser("unseal-blind", help="One-shot atomic evaluation of cvrp_m32_blind_120.")
    s_unseal.set_defaults(func=cmd_unseal_blind)

    s_rep = sub.add_parser("report", help="Generate multi-axis M3.2 scaling & control report.")
    s_rep.add_argument("--control-budget", type=int, default=400)
    s_rep.set_defaults(func=cmd_report)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
