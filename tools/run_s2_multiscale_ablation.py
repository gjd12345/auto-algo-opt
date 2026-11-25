"""Run Experiment 2C, the CVRP multiscale × early-stop online factorial."""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Mapping, Sequence
from contextlib import closing
from itertools import combinations
import json
import math
import os
from pathlib import Path
import secrets
import sys
from typing import Any

import numpy as np

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from agent_skill_loop.client import ProviderFailure, load_local_env
from agent_skill_loop.cvrp_workbench.baselines_2026 import summarize_solve_timing
from agent_skill_loop.cvrp_workbench.solvers import evaluate_algorithm_on_instance
from agent_skill_loop.interface_design.blind_commitment import (
    _CAPACITY_LEVELS, _gen_coords, _gen_demands, _seeded_rng, _sha256_payload,
    require_external_custody_path,
)
from agent_skill_loop.interface_design.blind_eval import paired_wilcoxon_signed_rank
from agent_skill_loop.interface_design.blind_eval_m3 import holm_bonferroni_adjust
from agent_skill_loop.interface_design.blind_eval_m32 import (
    SEALED_S2_BLIND_SUITE_ID, _cell, _read_pinned, _write_once, read_public_milestone_blind_commitment,
    read_verified_milestone_blind_payload,
)
from agent_skill_loop.interface_design.blind_eval_m5 import _blind_design_rows
from agent_skill_loop.interface_design.contracts import FrozenInterfaceSolver
from agent_skill_loop.interface_design.runtime import evaluate_frozen_interface_solver
from agent_skill_loop.interface_design.session_baseline import load_dev_or_public_suite
from agent_skill_loop.interface_design.templates import get_template_spec
from agent_skill_loop.interface_design.timed_cvrp import TIMED_CVRP_PROTOCOL, TIMED_CVRP_SOURCE_SHA256
from agent_skill_loop.session_supervisor import task_output
from research_agent.contracts import AgentConfig, atomic_write_json, atomic_write_text
from research_agent.loop import _build_initial_baseline_solver, run_research_agent
from tools.run_b4_intron_ablation import EXTERNAL_CVRPLIB_SUITES
from tools.run_m32_scaling import RESUMABLE_EXIT_CODE
from tools.run_m5_trajectory_control import POSTPROCESS_MODES, TEMPLATES, TERMINAL_PHASES, _indexed, _json, _open_ledger, _sha256
from tools.s2_multiscale_calibration import SIZE_BANDS, read_threshold_lock

MODELS = ("DeepSeek-V4.1-Flash", "Qwen4-Max")
SEEDS = (20261124, 20261125, 20261126)
ARMS = {
    "arm_s2_00_base_whitelist": (False, False),
    "arm_s2_10_multiscale_only": (True, False),
    "arm_s2_01_earlystop_only": (False, True),
    "arm_s2_11_combined": (True, True),
}
FACTORS = ("enable_multiscale_latency_ratio_screen", "early_stop_no_jump_requests", "basin_restart_on_stagnation")
REQUEST_CAP = 100
MAX_ROUNDS = 12
MAX_SAMPLES = 32
DEADLINE_MS = 500.0
DEV_SUITE_ID = "cvrp_dev_hetero_24"
BLIND_SUITE_ID = SEALED_S2_BLIND_SUITE_ID
SUITE_COUNTS = {BLIND_SUITE_ID: 120, "cvrp_ext_cvrplib_abp_74": 74, "cvrp_ext_cvrplib_x_100": 100}
RELEASE_ID = "20261124-main-co-workbench-m4"
RELEASE_SHA256 = "3c9e5507de4a503bb7f9a577dac4dbbc164ab9cb3d1cc5ec193ba39112003b3f"
S2_ROOT = REPO / "experiments" / "milestone5_s2_multiscale"
THRESHOLD_LOCK = S2_ROOT / "multiscale_threshold_lock.json"
THRESHOLD_LOCK_SHA256 = "e44cd57210aaf4191e7dbf4a87105ea654039154885b877ab90eb2dd2d7c9ae1"
POLICY = {
    "floor_ms": 1.0, "min_t200_trigger_ms": 10.0,
    "max_ratio_200_100": 8.0, "n200_abs_cap_ms": 50.596442562694065,
}
DEFAULT_OUTPUT = S2_ROOT / "exp2c"
DEFAULT_CUSTODY = Path.home() / ".agent_skill_custody" / "s2_multiscale"
DEFAULT_ENDPOINT = "https://llmapi.paratera.com/v1/chat/completions"
PROTOCOL = "s2_pre_blind_protocol.json"
COMMITMENT = f"{BLIND_SUITE_ID}_commitment.json"
SEAL_REGISTRATION = "s2_seal_registration.json"
LOCK = "s2_roster_lock.json"
EVALUATION = "s2_evaluation.json"
REPORT = "s2_multiscale_ablation_report"
RUN_BINDING = "s2_cell_binding.json"
RUN_FAILURE = "s2_cell_failure.json"
TIMING_VIEWS = ("feasible_before_deadline", "returned_before_deadline")
DENOMINATORS = ("common_completed", "penalized_2x")
BLIND_SIZES = (50, 100, 150, 200)
PUBLIC_BANDS = ((1, 99), *SIZE_BANDS, (1001, None))
BOOTSTRAP_REPLICATES = 10_000
_EFFECTS = {
    "multiscale_main": (-0.5, 0.5, -0.5, 0.5),
    "early_stop_main": (-0.5, -0.5, 0.5, 0.5),
    "interaction": (1.0, -1.0, -1.0, 1.0),
    **{
        f"{right}_minus_{left}": tuple(float(arm == right) - float(arm == left) for arm in ARMS)
        for left, right in combinations(ARMS, 2)
    },
}
_PROTECTED = (REPO / "eoh_frozen", REPO / "benchmarks" / "eohs_v1", REPO / "knowledge_store", REPO / ".secrets", REPO / ".git")
_TIMED_EVAL = {"protocol": TIMED_CVRP_PROTOCOL, "source_sha256": TIMED_CVRP_SOURCE_SHA256}


def _show(payload: Mapping[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False, allow_nan=False))
    return 0


def _id(model: str, arm: str, seed: int) -> str:
    return f"{model}:{arm}:{seed}"


def _parts(cell: str) -> tuple[str, str, int]:
    model, arm, seed = cell.split(":")
    return model, arm, int(seed)


def _cells() -> list[str]:
    return [_id(model, arm, seed) for model in MODELS for seed in SEEDS for arm in ARMS]


def _output_path(root: Path, ref: str | Path) -> Path:
    path = (root / ref).resolve()
    if not path.is_relative_to(root) or any(path.is_relative_to(item.resolve()) for item in _PROTECTED):
        raise ValueError("s2_artifact_path_outside_output_or_protected")
    if any(part.casefold().startswith(".agent_skill_custody") for part in path.parts):
        raise ValueError("s2_output_must_be_outside_custody")
    return path


def _publish_once(path: Path, payload: Mapping[str, Any]) -> None:
    if path.exists():
        if _json(path) != payload:
            raise ValueError(f"s2_existing_receipt_mismatch:{path.name}")
        return
    _write_once(path, payload)


def _custody(args: argparse.Namespace) -> Path:
    root = require_external_custody_path(args.custody_dir or DEFAULT_CUSTODY, repo_root=REPO)
    approved_parent = DEFAULT_CUSTODY.parent.resolve()
    if root == approved_parent or root in approved_parent.parents or (
        root.is_relative_to(approved_parent) and root != DEFAULT_CUSTODY.resolve()
    ):
        raise ValueError("s2_requires_dedicated_custody")
    if args.out_dir.is_relative_to(root) or root.is_relative_to(args.out_dir):
        raise ValueError("s2_output_and_custody_must_be_disjoint")
    if args.mock and (root == DEFAULT_CUSTODY.resolve() or root.is_relative_to(DEFAULT_CUSTODY.resolve())):
        raise ValueError("s2_mock_requires_isolated_external_custody")
    return root


def _private_path(root: Path, name: str) -> Path:
    path = root / name
    if path.is_symlink() or path.resolve() != path:
        raise ValueError("s2_invalid_custody_artifact_path")
    return path


def _positive(value: Any) -> float | None:
    return float(value) if type(value) in (int, float) and math.isfinite(value) and value > 0 else None


def _validate_suite(suite: Mapping[str, Any], suite_id: str) -> None:
    rows = suite["instances"]
    if len(rows) != SUITE_COUNTS[suite_id] or len({row["instance_id"] for row in rows}) != len(rows):
        raise ValueError(f"s2_suite_roster_mismatch:{suite_id}")
    for row in rows:
        if _positive(row.get("reference_objective")) is None:
            raise ValueError(f"s2_missing_penalty_reference:{suite_id}:{row['instance_id']}")
        if type(row.get("size")) is not int or row["size"] <= 0:
            raise ValueError(f"s2_invalid_instance_size:{suite_id}:{row['instance_id']}")


def _generate_blind() -> dict[str, Any]:
    token = secrets.token_hex(32)
    instances = []
    for index, (size, spatial, depot, capacity, demand) in enumerate(_blind_design_rows()):
        cell = _cell(size, spatial, depot, capacity, demand)
        rng = _seeded_rng(token, f"exp2c/{BLIND_SUITE_ID}/v1/{cell}", index)
        instance = {
            "instance_id": f"s2blind_{cell}-{index:03d}",
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
        if reference["valid"] is not True or _positive(objective) is None or type(fleet) is not int or fleet <= 0:
            raise RuntimeError("s2_nn_reference_failed")
        instance.update(reference_objective=objective, reference_kind="solver_reference", k_vehicles=fleet)
        instances.append(instance)
    return {
        "schema_version": "milestone-blind-sealed/v1", "suite_id": BLIND_SUITE_ID,
        "suite_role": "final_blind_acceptance", "exposure_status": "locked_s2_blind",
        "problem_family": "cvrp", "protocol_id": "cvrp/v1", "split": "blind",
        "distance_convention": "euc_2d_float", "vehicle_limit_policy": "unconstrained",
        "generator_version": "cvrp_s2_multiscale_blind_generator/v1",
        "generator_source_sha256": _sha256_payload([
            _sha256(Path(source).read_bytes())
            for source in (__file__, _seeded_rng.__code__.co_filename, _blind_design_rows.__code__.co_filename)
        ]),
        "instance_count": len(instances), "suite_content_sha256": _sha256_payload(instances),
        "stratification_spec": {
            "by_cell": dict(Counter(row["cell"] for row in instances)),
            "by_size": {str(size): count for size, count in Counter(row["size"] for row in instances).items()},
        },
        "reference_baseline": "nearest_neighbor", "exact_k_reference": "nearest_neighbor_route_count",
        "sealed_seed_token": token, "instances": instances,
    }


def _public_suites() -> dict[str, dict[str, Any]]:
    return {
        suite_id: load_dev_or_public_suite(suite_id, split=split, role=role)
        for suite_id, split, role in EXTERNAL_CVRPLIB_SUITES
    }


def _suite_hash(suite: Mapping[str, Any]) -> str:
    return _sha256_payload({
        key: suite[key] for key in ("suite_id", "split", "distance_convention", "vehicle_limit_policy", "instances")
    })


def _read_screen_lock() -> dict[str, str]:
    lock = read_threshold_lock(THRESHOLD_LOCK)
    if lock["lock_sha256"] != THRESHOLD_LOCK_SHA256 or lock["policy"] != POLICY or lock["budget_ms"] != DEADLINE_MS:
        raise ValueError("s2_threshold_lock_mismatch")
    return {"file_sha256": _sha256(THRESHOLD_LOCK.read_bytes()), "lock_sha256": lock["lock_sha256"]}


def _config(out_dir: Path, cell: str, settings: Mapping[str, Any]) -> AgentConfig:
    model, arm, seed = _parts(cell)
    multiscale, early_stop = ARMS[arm]
    return AgentConfig(
        run_id=f"m5_s2_{model}_{arm}_s{seed}",
        output_dir=str(_output_path(out_dir, f"runs/{model}/{seed}/{arm}")),
        arm_id=arm, search_seed=seed, planner_model=model, eoh_model=model,
        allowed_templates=TEMPLATES, allowed_postprocess_modes=POSTPROCESS_MODES,
        dev_suite_id=DEV_SUITE_ID, dev_split="dev_train", use_benchmark_dev_suite=True, dev_instance_count=24,
        max_rounds=MAX_ROUNDS, total_request_cap=REQUEST_CAP, instance_time_budget_ms=DEADLINE_MS,
        eoh_max_sample_nums=MAX_SAMPLES, strict_checkpoint_barriers=True, checkpoint_budgets=(REQUEST_CAP,),
        kb_enabled=True, kb_store_path=str(REPO / "knowledge_store" / "releases" / RELEASE_ID),
        pinned_kb_release_id=RELEASE_ID, pinned_kb_manifest_sha256=RELEASE_SHA256,
        allow_extended_numpy_whitelist=True, enable_degenerate_constant_screen=True,
        enable_n200_latency_screen=False, stagnation_diagnostic_mode="off",
        enable_multiscale_latency_ratio_screen=multiscale,
        max_n200_n100_ratio=POLICY["max_ratio_200_100"], multiscale_ratio_min_t200_ms=POLICY["min_t200_trigger_ms"],
        multiscale_n200_abs_cap_ms=POLICY["n200_abs_cap_ms"],
        early_stop_no_jump_requests=24 if early_stop else None, basin_restart_on_stagnation=early_stop,
        **settings,
    )


def _analysis_spec() -> dict[str, Any]:
    return {
        "timing_views": list(TIMING_VIEWS), "denominators": list(DENOMINATORS),
        "arm_order": list(ARMS), "contrasts": {name: list(weights) for name, weights in _EFFECTS.items()},
        "holm_family": ["model", "seed"], "bootstrap_replicates": BOOTSTRAP_REPLICATES,
        "confidence_level": 0.95, "blind_sizes": list(BLIND_SIZES),
        "public_size_bands": [list(band) for band in PUBLIC_BANDS], "penalty_multiplier": 2.0,
    }


def _protocol(args: argparse.Namespace) -> tuple[dict[str, Any], str]:
    path = _output_path(args.out_dir, PROTOCOL)
    raw = path.read_bytes()
    doc = json.loads(raw)
    if (
        doc.get("schema_version") != "s2-pre-blind-protocol/v1" or doc.get("cells") != _cells()
        or doc.get("blind_suite_id") != BLIND_SUITE_ID or doc.get("threshold_lock") != _read_screen_lock()
        or doc.get("policy") != POLICY or doc.get("analysis") != _analysis_spec() or doc.get("timing_evaluator") != _TIMED_EVAL
        or doc.get("request_cap") != REQUEST_CAP or doc.get("max_rounds") != MAX_ROUNDS
        or doc.get("eoh_max_sample_nums") != MAX_SAMPLES or doc.get("solve_deadline_ms") != DEADLINE_MS
        or doc.get("dev_suite_id") != DEV_SUITE_ID
    ):
        raise ValueError("s2_pre_blind_protocol_mismatch")
    settings = doc["settings"]
    if set(settings) != {"mode", "endpoint", "api_key_env", "request_timeout_s", "wall_seconds"}:
        raise ValueError("s2_protocol_settings_mismatch")
    for key in ("endpoint", "api_key_env", "request_timeout_s", "wall_seconds"):
        explicit = getattr(args, key)
        if explicit is not None and explicit != settings[key]:
            raise ValueError(f"s2_protocol_settings_mismatch:{key}")
    if settings["mode"] not in {"mock", "live"} or (args.mock and settings["mode"] != "mock"):
        raise ValueError("s2_protocol_mode_mismatch")
    args.mock = settings["mode"] == "mock"
    config_hashes = {cell: _sha256_payload(_config(args.out_dir, cell, settings).to_dict()) for cell in doc["cells"]}
    if doc.get("config_sha256_by_cell") != config_hashes:
        raise ValueError("s2_protocol_config_fingerprint_mismatch")
    read_public_milestone_blind_commitment(
        _output_path(args.out_dir, COMMITMENT), expected_sha256=doc["commitment_sha256"], expected_suite_id=BLIND_SUITE_ID,
    )
    return doc, _sha256(raw)


def cmd_seal_blind(args: argparse.Namespace) -> int:
    root = _custody(args)
    path = _output_path(args.out_dir, PROTOCOL)
    if path.exists():
        protocol, _ = _protocol(args)
        if protocol["custody_location_sha256"] != _sha256_payload(str(root)):
            raise ValueError("s2_custody_location_mismatch")
        return _show({"protocol_path": str(path), "suite_id": BLIND_SUITE_ID, "reused": True})
    settings = {
        "mode": "mock" if args.mock else "live",
        "endpoint": args.endpoint or os.environ.get("PARATERA_ENDPOINT") or DEFAULT_ENDPOINT,
        "api_key_env": args.api_key_env or "PARATERA_API_KEY",
        "request_timeout_s": 60.0 if args.request_timeout_s is None else args.request_timeout_s,
        "wall_seconds": 43_200.0 if args.wall_seconds is None else args.wall_seconds,
    }
    if any(_positive(settings[key]) is None for key in ("request_timeout_s", "wall_seconds")):
        raise ValueError("s2_invalid_timeout")
    threshold = _read_screen_lock()
    public = _public_suites()
    for suite_id, suite in public.items():
        _validate_suite(suite, suite_id)
    dev = load_dev_or_public_suite(DEV_SUITE_ID, split="dev_train", role="diagnostic_interactive")
    if len(dev["instances"]) != 24:
        raise ValueError("s2_dev_suite_count_mismatch")
    cells = _cells()
    configs = {cell: _sha256_payload(_config(args.out_dir, cell, settings).to_dict()) for cell in cells}

    sealed_path = _private_path(root, f"{BLIND_SUITE_ID}_sealed.json")
    commitment_path = _output_path(args.out_dir, COMMITMENT)
    registration_path = _private_path(root, SEAL_REGISTRATION)
    registration = {
        "schema_version": "s2-seal-registration/v1", "output_sha256": _sha256_payload(str(args.out_dir)),
        "threshold_lock": threshold, "config_sha256_by_cell": configs,
        "public_suite_sha256": {suite_id: _suite_hash(suite) for suite_id, suite in public.items()},
        "dev_suite_sha256": _suite_hash(dev),
    }
    allowed = {registration_path, sealed_path}
    if root.exists() and any(path not in allowed for path in root.iterdir()):
        raise FileExistsError("s2_custody_root_must_be_fresh")
    if (sealed_path.exists() or commitment_path.exists()) and not registration_path.is_file():
        raise FileExistsError("s2_seal_registration_required_for_recovery")
    _publish_once(registration_path, registration)
    if not sealed_path.exists():
        if commitment_path.exists():
            raise FileExistsError("s2_commitment_without_custody_seal")
        sealed = _generate_blind()
        _validate_suite(sealed, BLIND_SUITE_ID)
        _write_once(sealed_path, sealed)
    else:
        sealed = _json(sealed_path)
        _validate_suite(sealed, BLIND_SUITE_ID)
        if sealed.get("suite_id") != BLIND_SUITE_ID or sealed["suite_content_sha256"] != _sha256_payload(sealed["instances"]):
            raise ValueError("s2_invalid_custody_seal")
    sizes = {str(size): 30 for size in BLIND_SIZES}
    if sealed["stratification_spec"]["by_size"] != sizes:
        raise ValueError("s2_blind_size_stratification_mismatch")
    commitment = {
        **{key: sealed[key] for key in (
            "suite_id", "suite_role", "exposure_status", "problem_family", "protocol_id", "split",
            "distance_convention", "vehicle_limit_policy", "generator_version", "generator_source_sha256",
            "instance_count", "suite_content_sha256", "stratification_spec", "reference_baseline", "exact_k_reference",
        )},
        "schema_version": "milestone-blind-commitment/v1", "commitment_status": "sealed",
        "instances": [
            {"instance_id": row["instance_id"], "cell": row["cell"], "instance_sha256": _sha256_payload(row)}
            for row in sealed["instances"]
        ],
    }
    _publish_once(commitment_path, commitment)
    protocol = {
        "schema_version": "s2-pre-blind-protocol/v1", "settings": settings, "cells": cells,
        "config_sha256_by_cell": configs, "blind_suite_id": BLIND_SUITE_ID,
        "commitment_sha256": _sha256(commitment_path.read_bytes()), "custody_location_sha256": _sha256_payload(str(root)),
        "threshold_lock": threshold, "policy": POLICY, "online_probe_order": [[100, 0], [200, 0], [100, 1], [200, 1]],
        "public_suite_sha256": registration["public_suite_sha256"], "dev_suite_sha256": registration["dev_suite_sha256"],
        "analysis": _analysis_spec(), "timing_evaluator": _TIMED_EVAL,
        "request_cap": REQUEST_CAP, "max_rounds": MAX_ROUNDS, "eoh_max_sample_nums": MAX_SAMPLES,
        "solve_deadline_ms": DEADLINE_MS, "dev_suite_id": DEV_SUITE_ID,
        "pinned_kb_release": {"release_id": RELEASE_ID, "manifest_sha256": RELEASE_SHA256},
    }
    _publish_once(path, protocol)
    return _show({"protocol_path": str(path), "suite_id": BLIND_SUITE_ID, "registered_cell_count": len(cells)})


def cmd_emit_mux(args: argparse.Namespace) -> int:
    protocol, digest = _protocol(args)
    panes = []
    for cell in protocol["cells"]:
        config = _config(args.out_dir, cell, protocol["settings"])
        model, arm, seed = _parts(cell)
        panes.append({
            "id": config.run_id, "cwd": str(REPO),
            "command": [
                sys.executable, str(Path(__file__).resolve()), "run-cell", "--out-dir", str(args.out_dir),
                "--model", model, "--arm", arm, "--seed", str(seed), "--resume",
            ],
        })
    path = _output_path(args.out_dir, args.manifest_path or "mux_s2_multiscale.json")
    _publish_once(path, {"protocol_sha256": digest, "panes": panes})
    return _show({"manifest_path": str(path), "pane_count": len(panes)})


def _binding(protocol: Mapping[str, Any], protocol_sha: str, cell: str) -> dict[str, str]:
    return {"cell": cell, "protocol_sha256": protocol_sha, "config_sha256": protocol["config_sha256_by_cell"][cell]}


def _record_cell_failure(config: AgentConfig, binding: Mapping[str, str], reason: str) -> None:
    run_dir = Path(config.output_dir)
    ledger_path = _output_path(run_dir, "agent_budget.sqlite3")
    requests = 0
    if ledger_path.is_file():
        with closing(_open_ledger(ledger_path)) as ledger:
            requests = ledger.execute(
                "SELECT COUNT(*) FROM budget_requests WHERE run_id=?", (config.run_id,),
            ).fetchone()[0]
    checkpoint_path = _output_path(run_dir, "agent_checkpoint.json")
    checkpoint = _json(checkpoint_path) if checkpoint_path.is_file() else {}
    atomic_write_json(_output_path(run_dir, RUN_FAILURE), {
        **binding, "stop_reason": reason, "realized_request_spend": requests,
        "restart_count": sum(
            event.get("event") == "basin_restart" for event in checkpoint.get("trajectory_control_events", [])
        ),
    })


def cmd_run_cell(args: argparse.Namespace) -> int:
    protocol, digest = _protocol(args)
    cell = _id(args.model, args.arm, args.seed)
    if cell not in protocol["cells"]:
        raise ValueError(f"s2_unregistered_cell:{cell}")
    if _output_path(args.out_dir, LOCK).exists():
        raise ValueError("s2_roster_is_already_locked")
    config = _config(args.out_dir, cell, protocol["settings"])
    run_dir = Path(config.output_dir)
    receipt = _output_path(run_dir, RUN_BINDING)
    binding = _binding(protocol, digest, cell)
    stored_config = _output_path(run_dir, "agent_config.json")
    checkpoint = _output_path(run_dir, "agent_checkpoint.json")
    summary_path = _output_path(run_dir, "research_summary.json")
    if stored_config.exists() or checkpoint.exists() or summary_path.exists():
        if _json(receipt) != binding or AgentConfig.from_dict(_json(stored_config)) != config:
            raise ValueError(f"s2_cell_binding_mismatch:{cell}")
    dev = load_dev_or_public_suite(DEV_SUITE_ID, split="dev_train", role="diagnostic_interactive")
    if _suite_hash(dev) != protocol["dev_suite_sha256"]:
        raise ValueError("s2_dev_suite_hash_mismatch")
    if summary_path.exists():
        stored = _json(summary_path)
        if stored.get("final_phase") in TERMINAL_PHASES:
            if stored.get("realized_request_spend") != REQUEST_CAP:
                _show({"cell": cell, "status": "under_spent", "realized_request_spend": stored.get("realized_request_spend")})
                return 1
            return _show({"cell": cell, "status": stored["final_phase"], "reused": True})
    if checkpoint.exists() and not args.resume:
        raise ValueError("s2_existing_cell_requires_resume")
    if config.mode == "live":
        load_local_env()
        if not config.endpoint.startswith("https://") or os.environ.get("AGENT_SKILL_M2_MOCK") == "1":
            raise ValueError("s2_live_cell_requires_https_and_live_environment")
    _publish_once(receipt, binding)
    try:
        summary = run_research_agent(config, resume=checkpoint.is_file())
    except ProviderFailure as exc:
        _record_cell_failure(config, binding, "provider_failure")
        _show({"cell": cell, "status": "resumable", "reason": exc.error_code})
        return RESUMABLE_EXIT_CODE
    except Exception:
        _record_cell_failure(config, binding, "cell_execution_failed")
        raise
    _show({
        "cell": cell, "status": summary["final_phase"], "stop_reason": summary["stop_reason"],
        "restart_count": summary["restart_count"], "realized_request_spend": summary["realized_request_spend"],
    })
    return int(summary["realized_request_spend"] != REQUEST_CAP)


def _collected_rounds(root: Path, ledger: Any) -> list[tuple[int, dict[str, Any], Path]]:
    tasks = ledger.execute(
        """
        SELECT r.round_id, t.*, r.evaluation_facts_ref, r.evaluation_facts_sha256 FROM rounds AS r
        JOIN tasks AS t ON t.task_id=r.task_id AND t.run_id=r.run_id AND t.round_id=r.round_id
        WHERE r.state='ROUND_COMPLETED' AND t.state='COLLECTED'
        ORDER BY r.round_id ASC
        """,
    ).fetchall()
    collected: list[tuple[int, dict[str, Any], Path]] = []
    for task in tasks:
        local_round_id = int(task["round_id"])
        path = _output_path(root, task["evaluation_facts_ref"])
        facts = _read_pinned(path, task["evaluation_facts_sha256"], "s2_restart_round_evidence")
        if facts.get("round_id") != local_round_id:
            raise ValueError(f"s2_restart_round_evidence_mismatch:{local_round_id}")
        collected.append((local_round_id, facts, task_output(root, ledger, task)))
    return collected


def _epoch_sort_key(path: Path) -> tuple[int, int | str]:
    suffix = path.name.rsplit("_", 1)[-1]
    return (0, int(suffix)) if suffix.isdigit() else (1, path.name)


def _restart_receipts(run_dir: Path, config: AgentConfig, summary: Mapping[str, Any]) -> list[dict[str, Any]]:
    events = summary["trajectory_control_events"]
    stops = {
        (event["round_id"], event["stagnation_trigger_ordinal"])
        for event in events if event["event"] == "stagnation_early_stop"
    }
    restarts = [event for event in events if event["event"] == "basin_restart"]
    if (
        len(restarts) != summary["restart_count"]
        or (not config.basin_restart_on_stagnation and (restarts or stops))
        or len({event["round_id"] for event in restarts}) != len(restarts)
    ):
        raise ValueError(f"s2_restart_count_mismatch:{config.run_id}")
    if not stops and not restarts:
        interrupted = sorted(run_dir.glob("session_run_interrupted_*"), key=_epoch_sort_key)
        session_roots = [
            _output_path(run_dir, candidate.name)
            for candidate in [*interrupted, run_dir / "session_run"]
            if (candidate / "session.sqlite3").is_file()
        ]
        for root in session_roots:
            with closing(_open_ledger(_output_path(root, "session.sqlite3"))) as ledger:
                for _, facts, _ in _collected_rounds(root, ledger):
                    if facts.get("stop_reason") == "stagnation_early_stop":
                        raise ValueError(f"s2_restart_count_mismatch:{config.run_id}")
        return []
    interrupted = sorted(run_dir.glob("session_run_interrupted_*"), key=_epoch_sort_key)
    session_roots = [
        _output_path(run_dir, candidate.name)
        for candidate in [*interrupted, run_dir / "session_run"]
        if (candidate / "session.sqlite3").is_file()
    ]
    if not session_roots:
        raise ValueError(f"s2_missing_session_ledger:{config.run_id}")

    records: list[tuple[int, int, dict[str, Any], Path]] = []
    for root in session_roots:
        with closing(_open_ledger(_output_path(root, "session.sqlite3"))) as ledger:
            for local_round_id, facts, output in _collected_rounds(root, ledger):
                records.append((len(records), local_round_id, facts, output))
    single_epoch = len(session_roots) == 1

    stop_record_idx: dict[tuple[int, int], int] = {}
    used_stop_indices: set[int] = set()
    for round_id, ordinal in sorted(stops):
        if type(ordinal) is not int or not 1 <= ordinal <= REQUEST_CAP:
            raise ValueError(f"s2_early_stop_evidence_mismatch:{config.run_id}:{round_id}")
        matched_idx = None
        for rec_idx, local_round_id, facts, _ in records:
            if rec_idx in used_stop_indices:
                continue
            if single_epoch and local_round_id != round_id:
                continue
            if facts.get("stop_reason") == "stagnation_early_stop" and facts.get("stagnation_trigger_ordinal") == ordinal:
                matched_idx = rec_idx
                break
        if matched_idx is None:
            raise ValueError(f"s2_early_stop_evidence_mismatch:{config.run_id}:{round_id}")
        stop_record_idx[(round_id, ordinal)] = matched_idx
        used_stop_indices.add(matched_idx)

    ordered_stop_pairs = sorted(stop_record_idx.items(), key=lambda kv: (kv[1], kv[0]))
    next_stop_bound: dict[tuple[int, int], int] = {}
    for pos, (stop_key, _) in enumerate(ordered_stop_pairs):
        next_stop_bound[stop_key] = ordered_stop_pairs[pos + 1][1] if pos + 1 < len(ordered_stop_pairs) else len(records)

    receipts = []
    used_restart_indices: set[int] = set()
    for event in sorted(restarts, key=lambda item: int(item["round_id"])):
        round_id, trigger_round = event["round_id"], event["trigger_round_id"]
        trigger_ordinal = event["stagnation_trigger_ordinal"]
        if round_id != trigger_round + 1 or (trigger_round, trigger_ordinal) not in stops or trigger_ordinal >= REQUEST_CAP:
            raise ValueError(f"s2_restart_trigger_mismatch:{config.run_id}:{round_id}")
        req_ts, res_ts = event.get("requested_at"), event.get("restarted_at")
        if isinstance(req_ts, (int, float)) and isinstance(res_ts, (int, float)) and req_ts > res_ts:
            raise ValueError(f"s2_restart_timestamp_mismatch:{config.run_id}:{round_id}")
        stop_key = (trigger_round, trigger_ordinal)
        after_idx = stop_record_idx[stop_key]
        upper_idx = next_stop_bound[stop_key]
        valid_candidates: list[tuple[int, dict[str, Any], Path]] = []
        for rec_idx, local_round_id, facts, output in records:
            if rec_idx <= after_idx or rec_idx > upper_idx or rec_idx in used_restart_indices:
                continue
            if single_epoch and local_round_id != round_id:
                continue
            if facts.get("fresh_template_applied") is not True:
                continue
            path = _output_path(run_dir, output / "interface_seed_receipt.json")
            if not path.is_file():
                continue
            receipt = _json(path)
            if (
                receipt.get("reason") != "fresh_template"
                or any(type(receipt.get(field)) is not int or receipt.get(field) != 0 for field in ("requested_inherited_seeds", "used_inherited_seeds"))
            ):
                continue
            valid_candidates.append((rec_idx, facts, path))
        if not valid_candidates:
            raise ValueError(f"s2_restart_receipt_mismatch:{config.run_id}:{round_id}")
        chosen_idx, _, chosen_path = next(
            (item for item in valid_candidates if item[1].get("stop_reason") != "request_deadline"),
            valid_candidates[0],
        )
        used_restart_indices.add(chosen_idx)
        receipts.append({
            **event,
            "receipt_ref": chosen_path.relative_to(run_dir).as_posix(),
            "receipt_sha256": _sha256(chosen_path.read_bytes()),
        })
    return receipts


def _freeze_cell(config: AgentConfig, binding: Mapping[str, str]) -> tuple[dict[str, Any], dict[str, Any] | None]:
    run_dir = Path(config.output_dir)
    summary = _json(_output_path(run_dir, "research_summary.json"))
    if (
        _json(_output_path(run_dir, RUN_BINDING)) != binding
        or AgentConfig.from_dict(_json(_output_path(run_dir, "agent_config.json"))) != config
        or summary.get("run_id") != config.run_id or summary.get("final_phase") not in TERMINAL_PHASES
    ):
        raise ValueError(f"s2_cell_binding_mismatch:{config.run_id}")
    with closing(_open_ledger(_output_path(run_dir, "agent_budget.sqlite3"))) as ledger:
        requests = ledger.execute(
            "SELECT idx, state FROM budget_requests WHERE run_id=? ORDER BY idx", (config.run_id,),
        ).fetchall()
        if (
            [row["idx"] for row in requests] != list(range(1, REQUEST_CAP + 1))
            or any(row["state"] in {"reserved", "sent"} for row in requests)
            or summary.get("realized_request_spend") != REQUEST_CAP
            or summary["budget_summary"]["attempted_requests"] != REQUEST_CAP
        ):
            raise ValueError(f"s2_cell_requires_full_settled_request_budget:{config.run_id}")
        checkpoint = ledger.execute(
            "SELECT * FROM milestone_checkpoints WHERE run_id=? AND ckpt_budget=?", (config.run_id, REQUEST_CAP),
        ).fetchone()
        if checkpoint is None or checkpoint["state"] != "sealed" or checkpoint["settled_through_ordinal"] != REQUEST_CAP:
            raise ValueError(f"s2_cell_requires_sealed_checkpoint:{config.run_id}")
    path = _output_path(run_dir, f"checkpoints/frozen_checkpoint_{REQUEST_CAP}.json")
    payload = _read_pinned(path, checkpoint["payload_sha256"], "s2_frozen_checkpoint")
    if (
        payload.get("schema_version") != "m32-frozen-checkpoint/v1" or payload.get("run_id") != config.run_id
        or payload.get("checkpoint_budget") != REQUEST_CAP or payload.get("settled_through_ordinal") != REQUEST_CAP
        or payload.get("winner_source_ordinal") != checkpoint["winner_source_ordinal"]
        or payload.get("winner_solver_sha256") != checkpoint["winner_solver_sha256"]
    ):
        raise ValueError(f"s2_frozen_checkpoint_identity_mismatch:{config.run_id}")
    snapshot = payload.get("frozen_solver")
    if snapshot is not None:
        solver = FrozenInterfaceSolver.from_dict(snapshot)
        winner_ordinal = payload["winner_source_ordinal"]
        if (
            payload.get("eligibility_status") != "eligible_champion"
            or type(winner_ordinal) is not int or not 0 <= winner_ordinal <= REQUEST_CAP
            or _sha256_payload(snapshot) != payload["winner_solver_sha256"]
            or solver.problem_family != "cvrp" or solver.template_id not in TEMPLATES
            or solver.postprocess_mode not in POSTPROCESS_MODES or solver.default_budget_ms != DEADLINE_MS
            or solver.template_options.get("allow_extended_numpy_whitelist", True) is not True
        ):
            raise ValueError(f"s2_invalid_champion_identity:{config.run_id}")
        expected_options = {
            "enable_degenerate_constant_screen": True,
            "enable_multiscale_latency_ratio_screen": config.enable_multiscale_latency_ratio_screen,
            "max_n200_n100_ratio": config.max_n200_n100_ratio,
            "multiscale_ratio_min_t200_ms": config.multiscale_ratio_min_t200_ms,
            "multiscale_n200_abs_cap_ms": config.multiscale_n200_abs_cap_ms,
            "early_stop_no_jump_requests": config.early_stop_no_jump_requests,
        }
        defaults = {
            "enable_multiscale_latency_ratio_screen": False, "max_n200_n100_ratio": 8.0,
            "multiscale_ratio_min_t200_ms": 10.0,
        }
        if winner_ordinal == 0:
            if solver.to_dict() != _build_initial_baseline_solver(config).to_dict():
                raise ValueError(f"s2_champion_baseline_mismatch:{config.run_id}")
        elif any(solver.template_options.get(key, defaults.get(key)) != value for key, value in expected_options.items()):
            raise ValueError(f"s2_champion_policy_mismatch:{config.run_id}")
        template = get_template_spec(solver.template_id, solver.template_version)
        if (
            solver.template_source_sha256 != template.template_source_sha256
            or solver.hook_name != template.hook_name or solver.hook_specs != template.hook_specs
        ):
            raise ValueError(f"s2_champion_template_mismatch:{config.run_id}")
    elif (
        payload.get("eligibility_status") != "no_eligible_solver"
        or payload.get("winner_source_ordinal") is not None or payload.get("winner_solver_sha256") is not None
    ):
        raise ValueError(f"s2_missing_champion_provenance_mismatch:{config.run_id}")
    provenance = {
        **binding,
        "stop_reason": summary["stop_reason"], "final_phase": summary["final_phase"],
        "restart_count": summary["restart_count"], "realized_request_spend": len(requests),
        "restart_receipts": _restart_receipts(run_dir, config, summary),
        "checkpoint_sha256": checkpoint["payload_sha256"], "winner_source_ordinal": checkpoint["winner_source_ordinal"],
    }
    return provenance, snapshot


def _locked_roster(
    args: argparse.Namespace, protocol: Mapping[str, Any], protocol_sha: str,
) -> tuple[dict[str, Any], str, dict[str, FrozenInterfaceSolver]]:
    raw = _output_path(args.out_dir, LOCK).read_bytes()
    lock = json.loads(raw)
    if (
        lock.get("schema_version") != "s2-roster-lock/v1" or lock.get("protocol_sha256") != protocol_sha
        or [row["cell"] for row in lock["roster"]] != protocol["cells"]
    ):
        raise ValueError("s2_roster_does_not_match_protocol")
    solvers = {}
    for row in lock["roster"]:
        cell = row["cell"]
        if (
            row.get("config_sha256") != protocol["config_sha256_by_cell"][cell]
            or row.get("realized_request_spend") != REQUEST_CAP
            or row.get("final_phase") not in TERMINAL_PHASES
            or type(row.get("restart_count")) is not int
            or not isinstance(row.get("restart_receipts"), list)
            or len(row["restart_receipts"]) != row["restart_count"]
        ):
            raise ValueError(f"s2_roster_cell_provenance_mismatch:{cell}")
        if row.get("missing_reason") == "no_eligible_snapshot":
            if row.get("winner_source_ordinal") is not None or "snapshot_ref" in row:
                raise ValueError(f"s2_missing_champion_provenance_mismatch:{cell}")
            continue
        expected_ref = f"roster_snapshots/{_config(args.out_dir, cell, protocol['settings']).run_id}.json"
        if row.get("snapshot_ref") != expected_ref:
            raise ValueError(f"s2_roster_snapshot_ref_mismatch:{cell}")
        path = _output_path(args.out_dir, expected_ref)
        solver = _read_pinned(path, row["snapshot_sha256"], "s2_snapshot")
        solvers[cell] = FrozenInterfaceSolver.from_dict(solver)
    return lock, _sha256(raw), solvers


def cmd_lock_roster(args: argparse.Namespace) -> int:
    protocol, protocol_sha = _protocol(args)
    lock_path = _output_path(args.out_dir, LOCK)
    if lock_path.exists():
        lock, _, solvers = _locked_roster(args, protocol, protocol_sha)
        return _show({"roster_path": str(lock_path), "cell_count": len(lock["roster"]), "champions": len(solvers)})
    rows, snapshots = [], {}
    for cell in protocol["cells"]:
        config = _config(args.out_dir, cell, protocol["settings"])
        row, snapshot = _freeze_cell(config, _binding(protocol, protocol_sha, cell))
        if snapshot is None:
            row["missing_reason"] = "no_eligible_snapshot"
        else:
            ref = f"roster_snapshots/{config.run_id}.json"
            snapshots[ref] = snapshot
            row["snapshot_ref"] = ref
        rows.append(row)
    for row in rows:
        if "snapshot_ref" in row:
            ref = row["snapshot_ref"]
            path = _output_path(args.out_dir, ref)
            _publish_once(path, snapshots[ref])
            row["snapshot_sha256"] = _sha256(path.read_bytes())
    _publish_once(lock_path, {
        "schema_version": "s2-roster-lock/v1", "protocol_sha256": protocol_sha, "roster": rows,
    })
    return _show({"roster_path": str(lock_path), "cell_count": len(rows), "champions": len(snapshots)})


def _claim_blind(
    args: argparse.Namespace, protocol: Mapping[str, Any], roster_sha: str,
) -> dict[str, Any]:
    root = _custody(args)
    if protocol["custody_location_sha256"] != _sha256_payload(str(root)):
        raise ValueError("s2_custody_location_mismatch")
    commitment_path = _output_path(args.out_dir, COMMITMENT)
    commitment_sha = protocol["commitment_sha256"]
    commitment = read_public_milestone_blind_commitment(
        commitment_path, expected_sha256=commitment_sha, expected_suite_id=BLIND_SUITE_ID,
    )
    content_sha = commitment["suite_content_sha256"]
    if (
        type(content_sha) is not str or len(content_sha) != 64
        or any(letter not in "0123456789abcdef" for letter in content_sha)
        or commitment["instance_count"] != SUITE_COUNTS[BLIND_SUITE_ID]
    ):
        raise ValueError("s2_invalid_commitment")
    sealed_path = _private_path(root, f"{BLIND_SUITE_ID}_sealed.json")
    if not sealed_path.is_file():
        raise FileNotFoundError("s2_custody_seal_missing")
    marker = _private_path(root, f"{BLIND_SUITE_ID}.{content_sha}.consumed")
    try:
        _write_once(marker, {"commitment_sha256": commitment_sha, "roster_lock_sha256": roster_sha})
    except FileExistsError:
        raise FileExistsError("s2_blind_attempt_already_consumed") from None
    try:
        sealed, _, _ = read_verified_milestone_blind_payload(
            sealed_path=sealed_path, commitment_path=commitment_path, expected_commitment_sha256=commitment_sha,
            expected_suite_id=BLIND_SUITE_ID, repo_root=REPO,
        )
        _validate_suite(sealed, BLIND_SUITE_ID)
        counts = dict(Counter(row["size"] for row in sealed["instances"]))
        if counts != {size: 30 for size in BLIND_SIZES}:
            raise ValueError("s2_blind_size_stratification_mismatch")
        return sealed
    except Exception:
        raise RuntimeError("s2_blind_payload_invalid_attempt_consumed") from None


def _time(value: Any) -> float | None:
    return float(value) if type(value) in (int, float) and math.isfinite(value) and value >= 0 else None


def _timing_record(
    instance: Mapping[str, Any], result: Mapping[str, Any], *, exact_applicable: bool,
) -> dict[str, Any]:
    is_outer = result.get("timeout_kind") == "outer_worker"
    row = {
        "instance_id": instance["instance_id"], "size": instance["size"],
        "reference_objective": float(instance["reference_objective"]), "budget_ms": DEADLINE_MS,
        "solve_ms": None if is_outer else _time(result.get("solve_ms")),
        "preprocess_ms": None if is_outer else _time(result.get("preprocess_ms")),
        "verify_ms": None if is_outer else _time(result.get("verify_ms")),
        "solve_censored": is_outer or result.get("solve_censored") is True,
        "exact_k_applicable": exact_applicable,
    }
    for view in TIMING_VIEWS:
        for suffix in ("", "_exact_k"):
            key = view + suffix
            if suffix and not exact_applicable:
                row[key] = row[f"{key}_objective"] = None
                continue
            eligible = result.get(key) is True
            obj = _positive(result.get(f"{key}_objective")) if eligible else None
            if eligible and obj is None:
                raise ValueError(f"s2_timing_view_requires_verified_objective:{key}")
            row[key], row[f"{key}_objective"] = eligible, obj
    return row


def _score_suite(
    suite: Mapping[str, Any], cells: Sequence[str], solvers: Mapping[str, FrozenInterfaceSolver],
) -> dict[str, Any]:
    policy = suite["vehicle_limit_policy"]
    records = {cell: [] for cell in cells}
    for index, instance in enumerate(suite["instances"]):
        offset = index % len(cells)
        for cell in (*cells[offset:], *cells[:offset]):
            solver = solvers.get(cell)
            result = (
                evaluate_frozen_interface_solver(
                    solver, instance, distance_convention=suite["distance_convention"], vehicle_limit_policy=policy,
                    solve_deadline_ms=DEADLINE_MS, enforce_wall_deadline=True, capture_timed_incumbents=True,
                )
                if solver is not None else {}
            )
            if result.get("error_code") in {"worker_protocol", "worker_crash", "worker_start_failed"}:
                raise RuntimeError("s2_frozen_worker_failed")
            records[cell].append(_timing_record(instance, result, exact_applicable=policy != "free_fleet_min_k_lb"))
    return {"vehicle_limit_policy": policy, "records": records}


def cmd_unseal_eval(args: argparse.Namespace) -> int:
    protocol, protocol_sha = _protocol(args)
    evaluation_path = _output_path(args.out_dir, EVALUATION)
    if evaluation_path.exists():
        raise FileExistsError("s2_blind_attempt_already_consumed")
    _, roster_sha, solvers = _locked_roster(args, protocol, protocol_sha)
    suites = {}
    public = _public_suites()
    for suite_id, suite in public.items():
        _validate_suite(suite, suite_id)
        if _suite_hash(suite) != protocol["public_suite_sha256"][suite_id]:
            raise ValueError(f"s2_public_suite_hash_mismatch:{suite_id}")
    for suite_id, suite in public.items():
        suites[suite_id] = _score_suite(suite, protocol["cells"], solvers)
    blind = _claim_blind(args, protocol, roster_sha)
    try:
        suites[BLIND_SUITE_ID] = _score_suite(blind, protocol["cells"], solvers)
        _write_once(evaluation_path, {
            "schema_version": "s2-evaluation/v1", "protocol_sha256": protocol_sha,
            "roster_lock_sha256": roster_sha, "suites": suites, "suites_sha256": _sha256_payload(suites),
        })
    except Exception:
        raise RuntimeError("s2_blind_evaluation_failed_attempt_consumed") from None
    return _show({"evaluation_path": str(evaluation_path), "suite_count": len(suites)})

def _objective(row: Mapping[str, Any], view: str, fleet: str) -> float | None:
    key = view + ("_exact_k" if fleet == "exact_k" else "")
    return _positive(row[f"{key}_objective"]) if row[key] is True else None


def _cell_metrics(rows: Sequence[Mapping[str, Any]], suite_id: str) -> dict[str, Any]:
    bands = [(size, size) for size in BLIND_SIZES] if suite_id == BLIND_SUITE_ID else PUBLIC_BANDS
    size_latency = []
    for lower, upper in bands:
        subset = [row for row in rows if row["size"] >= lower and (upper is None or row["size"] <= upper)]
        size_latency.append({
            "size_min": lower, "size_max": upper, "instance_count": len(subset), **summarize_solve_timing(subset),
        })
    metrics = {}
    for fleet in ("free_fleet", "exact_k"):
        if fleet == "exact_k" and rows[0]["exact_k_applicable"] is not True:
            metrics[fleet] = None
            continue
        timing = {}
        for view in TIMING_VIEWS:
            paired = [(_objective(row, view, fleet), row["reference_objective"]) for row in rows]
            eligible = [cost for cost, _ in paired if cost is not None]
            timing[view] = {
                "eligible_count": len(eligible), "instance_count": len(rows), "rate": len(eligible) / len(rows),
                "eligible_mean_objective": sum(eligible) / len(eligible) if eligible else None,
                "penalized_2x_mean_objective": sum(
                    cost if cost is not None else 2.0 * ref for cost, ref in paired
                ) / len(rows),
            }
        metrics[fleet] = timing
    return {"timing_views": metrics, "solve_latency_by_size": size_latency}


def _contrast_samples(
    ordered_rows: Sequence[Sequence[Mapping[str, Any]]], weights: Sequence[float],
    *, view: str, fleet: str, denominator: str,
) -> list[float]:
    included = [(rows, weight) for rows, weight in zip(ordered_rows, weights, strict=True) if weight]
    samples = []
    for paired_rows in zip(*(rows for rows, _ in included), strict=True):
        objectives = [_objective(row, view, fleet) for row in paired_rows]
        if denominator == "common_completed" and any(cost is None for cost in objectives):
            continue
        samples.append(math.fsum(
            weight * (cost if cost is not None else 2.0 * row["reference_objective"])
            for (_, weight), row, cost in zip(included, paired_rows, objectives, strict=True)
        ))
    return samples


def _paired_test(samples: Sequence[float], *, seed: int) -> dict[str, Any]:
    if not samples:
        return {"n_pairs": 0, "mean_contrast": None, "wilcoxon": None, "bootstrap": None}
    values = np.asarray(samples, dtype=np.float64)
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(samples), size=(BOOTSTRAP_REPLICATES, len(samples)))
    bounds = np.quantile(values[draws].mean(axis=1), (0.025, 0.975))
    return {
        "n_pairs": len(samples), "mean_contrast": float(values.mean()),
        "wilcoxon": paired_wilcoxon_signed_rank(values, np.zeros_like(values)),
        "bootstrap": {
            "replicates": BOOTSTRAP_REPLICATES, "seed": seed, "ci95": [float(x) for x in bounds],
        },
    }


def _contrast_report(
    suites: Mapping[str, Any], protocol: Mapping[str, Any],
) -> list[dict[str, Any]]:
    indexed = {}
    for suite_id, suite in suites.items():
        rows = suite["records"]
        if set(rows) != set(protocol["cells"]) or any(len(items) != SUITE_COUNTS[suite_id] for items in rows.values()):
            raise ValueError(f"s2_evaluation_roster_or_suite_count_mismatch:{suite_id}")
        by_cell = {cell: _indexed(records) for cell, records in rows.items()}
        first = by_cell[protocol["cells"][0]]
        instance_ids = sorted(first)
        for cell, index in by_cell.items():
            if index.keys() != first.keys() or any(
                index[key][field] != first[key][field]
                for key in instance_ids for field in ("size", "reference_objective", "exact_k_applicable")
            ):
                raise ValueError(f"s2_paired_reference_mismatch:{suite_id}:{cell}")
        exact = suite["vehicle_limit_policy"] != "free_fleet_min_k_lb"
        if any(row["exact_k_applicable"] is not exact for row in first.values()):
            raise ValueError(f"s2_fleet_applicability_mismatch:{suite_id}")
        indexed[suite_id] = (
            exact, {cell: [records[key] for key in instance_ids] for cell, records in by_cell.items()},
        )
    results = []
    for model in MODELS:
        for seed in SEEDS:
            family = []
            for suite_id, (exact, records) in indexed.items():
                rows = [records[_id(model, arm, seed)] for arm in ARMS]
                for fleet in ("free_fleet", "exact_k") if exact else ("free_fleet",):
                    for view in TIMING_VIEWS:
                        for denominator in DENOMINATORS:
                            for effect, weights in _EFFECTS.items():
                                samples = _contrast_samples(rows, weights, view=view, fleet=fleet, denominator=denominator)
                                family.append({
                                    "model": model, "seed": seed, "suite_id": suite_id, "fleet": fleet,
                                    "timing_view": view, "denominator": denominator, "contrast": effect,
                                    **_paired_test(samples, seed=seed),
                                })
            adjusted = holm_bonferroni_adjust([
                row["wilcoxon"]["p_two_sided"] if row["wilcoxon"] else 1.0 for row in family
            ])
            for row, p_value in zip(family, adjusted, strict=True):
                row["wilcoxon_p_holm"] = p_value if row["wilcoxon"] else None
            results.extend(family)
    return results


def _report_markdown(report: Mapping[str, Any]) -> str:
    def fmt(value: float | None) -> str:
        return f"{value:.4g}" if value is not None else "—"

    lines = [
        "# Experiment 2C · CVRP multiscale × early-stop ablation", "",
        "Each model and seed has its own paired inference and Holm family.", "",
        "## Realized search budget", "",
        "| Cell | Stop reason | Requests | Restarts | Checkpoint winner ordinal |",
        "|---|---|---:|---:|---:|",
    ]
    for cell, row in report["search"].items():
        lines.append(
            f"| {cell} | {row['stop_reason']} | {row['realized_request_spend']} | "
            f"{row['restart_count']} | {fmt(row['winner_source_ordinal'])} |"
        )
    lines.extend([
        "", "## Deadline outcomes", "",
        "| Suite | Cell | Fleet | Timing view | Eligible | Eligible mean | 2×-penalized mean |",
        "|---|---|---|---|---:|---:|---:|",
    ])
    for suite_id, cells in report["per_seed"].items():
        for cell, stats in cells.items():
            for fleet, timing in stats["timing_views"].items():
                if timing is None:
                    continue
                for view, row in timing.items():
                    lines.append(
                        f"| {suite_id} | {cell} | {fleet} | {view} | "
                        f"{row['eligible_count']}/{row['instance_count']} | {fmt(row['eligible_mean_objective'])} | "
                        f"{fmt(row['penalized_2x_mean_objective'])} |"
                    )
    lines.extend([
        "", "## Solve latency by size", "",
        "| Suite | Cell | Size range | P95 (ms) | Lower bound | Observed | Censored | Missing |",
        "|---|---|---|---:|---|---:|---:|---:|",
    ])
    for suite_id, cells in report["per_seed"].items():
        for cell, stats in cells.items():
            for row in stats["solve_latency_by_size"]:
                lower, upper = row["size_min"], row["size_max"]
                label = f"{lower}+" if upper is None else str(lower) if lower == upper else f"{lower}–{upper}"
                lines.append(
                    f"| {suite_id} | {cell} | {label} | {fmt(row['solve_ms_p95'])} | "
                    f"{'yes' if row['solve_ms_p95_is_lower_bound'] else 'no'} | "
                    f"{row['solve_ms_observation_count']} | {row['solve_ms_censored_count']} | "
                    f"{row['solve_ms_missing_count']} |"
                )
    lines.extend([
        "", "## Paired contrasts", "",
        "Contrast signs are relative to objective cost. For `B_minus_A` (or a factor main effect), a negative value favors B (the enabled factor).", "",
        "| Model | Seed | Suite | Fleet | Timing view | Denominator | Contrast | Pairs | Mean | 95% CI | Wilcoxon p | Holm p |",
        "|---|---:|---|---|---|---|---|---:|---:|---|---:|---:|",
    ])
    for row in report["contrasts"]:
        bounds = " / ".join(map(fmt, row["bootstrap"]["ci95"])) if row["bootstrap"] else "—"
        p_raw = row["wilcoxon"]["p_two_sided"] if row["wilcoxon"] else None
        lines.append(
            f"| {row['model']} | {row['seed']} | {row['suite_id']} | {row['fleet']} | {row['timing_view']} | "
            f"{row['denominator']} | {row['contrast']} | {row['n_pairs']} | {fmt(row['mean_contrast'])} | "
            f"{bounds} | {fmt(p_raw)} | {fmt(row['wilcoxon_p_holm'])} |"
        )
    return "\n".join(lines) + "\n"


def cmd_report(args: argparse.Namespace) -> int:
    protocol, protocol_sha = _protocol(args)
    lock, roster_sha, _ = _locked_roster(args, protocol, protocol_sha)
    evaluation_path = _output_path(args.out_dir, EVALUATION)
    evaluation = _json(evaluation_path)
    suites = evaluation["suites"]
    if (
        evaluation.get("schema_version") != "s2-evaluation/v1" or evaluation.get("protocol_sha256") != protocol_sha
        or evaluation.get("roster_lock_sha256") != roster_sha or suites.keys() != SUITE_COUNTS.keys()
        or evaluation.get("suites_sha256") != _sha256_payload(suites)
    ):
        raise ValueError("s2_evaluation_binding_mismatch")
    contrasts = _contrast_report(suites, protocol)
    report = {
        "schema_version": "s2-report/v1", "run_mode": protocol["settings"]["mode"],
        "protocol_sha256": protocol_sha, "roster_lock_sha256": roster_sha,
        "evaluation_sha256": _sha256(evaluation_path.read_bytes()), "analysis": protocol["analysis"],
        "search": {row["cell"]: row for row in lock["roster"]},
        "per_seed": {
            suite_id: {cell: _cell_metrics(rows, suite_id) for cell, rows in suite["records"].items()}
            for suite_id, suite in suites.items()
        },
        "contrasts": contrasts,
    }
    path = _output_path(args.out_dir, f"{REPORT}.json")
    atomic_write_json(path, report)
    atomic_write_text(_output_path(args.out_dir, f"{REPORT}.md"), _report_markdown(report))
    return _show({"report_path": str(path), "contrast_count": len(contrasts)})


def _common_args(parser: argparse.ArgumentParser, *, suppress: bool = False) -> None:
    parser.add_argument("--out-dir", "--output-dir", type=Path, default=argparse.SUPPRESS if suppress else DEFAULT_OUTPUT)
    for flag, parser_type in (
        ("--custody-dir", Path), ("--endpoint", str), ("--api-key-env", str),
        ("--request-timeout-s", float), ("--wall-seconds", float),
    ):
        parser.add_argument(flag, type=parser_type, default=argparse.SUPPRESS if suppress else None)
    parser.add_argument("--mock", action="store_true", default=argparse.SUPPRESS if suppress else False)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    _common_args(parser)
    commands = parser.add_subparsers(dest="stage", required=True)
    for stage, function in (
        ("seal-blind", cmd_seal_blind), ("emit-mux", cmd_emit_mux), ("run-cell", cmd_run_cell),
        ("lock-roster", cmd_lock_roster), ("unseal-eval", cmd_unseal_eval), ("report", cmd_report),
    ):
        subparser = commands.add_parser(stage)
        _common_args(subparser, suppress=True)
        subparser.set_defaults(func=function)
        if stage == "emit-mux":
            subparser.add_argument("--manifest-path", type=Path)
        if stage == "run-cell":
            canonical = {model.casefold(): model for model in MODELS}
            subparser.add_argument("--model", required=True, type=lambda value: canonical.get(value.casefold(), value), choices=MODELS)
            subparser.add_argument("--arm", required=True, choices=ARMS)
            subparser.add_argument("--seed", type=int, required=True, choices=SEEDS)
            subparser.add_argument("--resume", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    args.out_dir = args.out_dir.resolve()
    _output_path(args.out_dir, ".")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())



