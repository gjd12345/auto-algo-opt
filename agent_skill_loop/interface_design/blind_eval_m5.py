"""External custody for the M5 CVRP trajectory-control holdout."""

from __future__ import annotations

import hashlib
import json
import math
import re
import secrets
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

from agent_skill_loop.cvrp_workbench.solvers import evaluate_algorithm_on_instance
from agent_skill_loop.cvrp_workbench.suites import MANIFESTS_DIR

from .blind_commitment import (
    _CAPACITY_LEVELS,
    _gen_coords,
    _gen_demands,
    _seeded_rng,
    _sha256_payload,
    build_m2_blind_120_design,
    require_external_custody_path,
)
from .blind_eval_m32 import (
    _cell,
    _claim_and_open,
    _custody_path,
    _public_record,
    _read_pinned,
    _seal,
    _write_once,
    read_public_milestone_blind_commitment,
)
from .contracts import FrozenInterfaceSolver
from .runtime import evaluate_frozen_interface_solver
from .templates import get_template_spec

_REPO = Path(__file__).resolve().parents[2]
M5_BLIND_SUITE_ID = "cvrp_m5_control_blind_120"
M5_PROTOCOL_ID = "cvrp_m5_trajectory_control_blind/v1"
M5_BLIND_COMMITMENT_PATH = MANIFESTS_DIR / f"{M5_BLIND_SUITE_ID}_commitment.json"
M5_DEFAULT_CUSTODY_DIR = Path.home() / ".agent_skill_custody_m5"
M5_SOLVE_DEADLINE_MS = 500.0
M5_REQUEST_CAP = 100
M5_DEEPSEEK_ARMS = ("legacy_baseline_500ms", "whitelist_latency_500ms", "trajectory_ctrl_full_500ms")
M5_MODEL2_ARMS = ("model2_legacy_500ms", "model2_ctrl_full_500ms")
M5_DEEPSEEK_SEEDS = (20261124, 20261125, 20261126, 20261127, 20261128)
M5_MODEL2_SEEDS = (20261124, 20261125, 20261126)
M5_ARM_SEEDS = {
    **dict.fromkeys(M5_DEEPSEEK_ARMS, M5_DEEPSEEK_SEEDS),
    **dict.fromkeys(M5_MODEL2_ARMS, M5_MODEL2_SEEDS),
}
M5_COMPARATOR_LABELS = ("l3_ctrl@500ms", "m32_champion_raw@500ms", "m32_champion_pruned@500ms")
M5_BASELINE_ALGORITHMS = (("cw_parallel_merge", M5_SOLVE_DEADLINE_MS), ("cw_relocate_2opt", M5_SOLVE_DEADLINE_MS))
_ARM_CONTRASTS = (
    ("whitelist_latency_500ms", "legacy_baseline_500ms"),
    ("trajectory_ctrl_full_500ms", "whitelist_latency_500ms"),
    ("trajectory_ctrl_full_500ms", "legacy_baseline_500ms"),
    ("model2_ctrl_full_500ms", "model2_legacy_500ms"),
)
M5_CONTRAST_FAMILIES = {
    **{f"{left}_vs_{right}": ((left, right),) for left, right in _ARM_CONTRASTS},
    "arm_vs_comparators": tuple(
        (arm, comparator)
        for arm in M5_ARM_SEEDS
        for comparator in ("l3_ctrl@500ms", "m32_champion_pruned@500ms")
    ),
}
_CVRP_PROTOCOL_ID = "cvrp/v1"
_PROTOCOL_SCHEMA = "m5-pre-blind-protocol/v1"
_LOCK_SCHEMA = "m5-blind-roster-lock/v1"


def _blind_design_rows() -> list[tuple[int, str, str, str, str]]:
    # Reuse the M2 factorial. For each size, replicate a complementary pair
    # of binary factor levels per spatial style, giving 30 instances per size.
    factorial = build_m2_blind_120_design()[:24]
    rows = []
    for size_index, size in enumerate((50, 100, 150, 200)):
        cells = [(size, spatial, depot, capacity, demand) for _, spatial, depot, capacity, demand in factorial]
        rows.extend(cells)
        rows.extend(cell for index, cell in enumerate(cells) if index % 8 in (size_index, 7 - size_index))
    return rows


def _suite_design(rows: Sequence[tuple[int, str, str, str, str]]) -> dict[str, Any]:
    return {
        "suite_id": M5_BLIND_SUITE_ID,
        "problem_family": "cvrp",
        "problem_id": "cvrp_construct",
        "protocol_id": _CVRP_PROTOCOL_ID,
        "blind_protocol_id": M5_PROTOCOL_ID,
        "suite_role": "final_blind_acceptance",
        "exposure_status": "locked_m5_blind",
        "split": "blind",
        "distance_convention": "euc_2d_float",
        "vehicle_limit_policy": "unconstrained",
        "generator_version": "cvrp_m5_blind_generator/v1",
        "instance_count": len(rows),
        "stratification_spec": {"by_cell": dict(Counter(_cell(*row) for row in rows))},
        "reference_baseline": "nearest_neighbor",
        "exact_k_reference": "nearest_neighbor_route_count",
    }


def _m5_custody_dir(custody_dir: Path | None, repo_root: Path) -> Path:
    root = require_external_custody_path(
        M5_DEFAULT_CUSTODY_DIR if custody_dir is None else custody_dir,
        repo_root=repo_root,
    )
    for part in root.parts:
        label = part.casefold()
        if label.startswith(".agent_skill_custody") and label != M5_DEFAULT_CUSTODY_DIR.name:
            raise ValueError("m5_custody_must_use_its_own_root")
    return root


def seal_m5_blind_120(
    *,
    commitment_path: Path = M5_BLIND_COMMITMENT_PATH,
    custody_dir: Path | None = None,
    repo_root: Path = _REPO,
) -> dict[str, Any]:
    """Create a write-once public commitment and a private external seal."""
    root = _m5_custody_dir(custody_dir, repo_root)
    rows = _blind_design_rows()
    design = _suite_design(rows)
    seed = secrets.token_hex(32)
    instances = []
    for index, (size, spatial, depot, capacity, demand) in enumerate(rows):
        cell = _cell(size, spatial, depot, capacity, demand)
        rng = _seeded_rng(seed, f"{M5_BLIND_SUITE_ID}/{cell}", index)
        instance = {
            "instance_id": f"m5blind_{cell}-{index:03d}",
            "cell": cell,
            "size": size,
            "spatial": spatial,
            "depot_style": depot,
            "capacity_level": capacity,
            "demand_dist": demand,
            "source_tag": M5_BLIND_SUITE_ID,
            "protocol_id": _CVRP_PROTOCOL_ID,
            "depot": [0.5, 0.5] if depot == "centre" else [0.05, 0.95],
            "customer_coordinates": _gen_coords(spatial, rng, size),
            "demands": _gen_demands(demand, rng, size),
            "capacity": _CAPACITY_LEVELS[capacity],
        }
        reference = evaluate_algorithm_on_instance("nn", instance, record_trace=False)
        objective = reference["tour_length"]
        fleet = reference["route_count"]
        if (
            reference["valid"] is not True or type(objective) not in (int, float)
            or not math.isfinite(objective) or objective <= 0 or type(fleet) is not int or fleet <= 0
        ):
            raise RuntimeError("m5_nn_reference_failed")
        instance.update(
            reference_objective=float(objective),
            reference_kind="solver_reference",
            k_vehicles=fleet,
        )
        instances.append(instance)
    return _seal(
        design,
        instances,
        seed_token=seed,
        generator_source_sha256=_sha256_payload([
            hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            hashlib.sha256(Path(_seeded_rng.__code__.co_filename).read_bytes()).hexdigest(),
        ]),
        commitment_path=commitment_path,
        custody_dir=root,
        repo_root=repo_root,
    )


def _arm_plan(arm_seeds: Mapping[str, Sequence[int]]) -> tuple[dict[str, list[int]], list[str]]:
    if not isinstance(arm_seeds, Mapping) or not arm_seeds:
        raise ValueError("invalid_m5_arm_seeds")
    approved = {}
    cells = []
    for arm, seeds in arm_seeds.items():
        if arm not in M5_ARM_SEEDS or not isinstance(seeds, Sequence) or not seeds:
            raise ValueError("invalid_m5_arm_seeds")
        if any(type(seed) is not int or seed < 0 for seed in seeds) or len(set(seeds)) != len(seeds):
            raise ValueError("invalid_m5_arm_seeds")
        approved[arm] = list(seeds)
        cells.extend(f"{arm}:{seed}" for seed in seeds)
    return approved, cells


def _sha256(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _protocol(arm_seeds: Mapping[str, Sequence[int]], model2: str, blind_commitment: dict[str, Any]) -> dict[str, Any]:
    plan, cells = _arm_plan(arm_seeds)
    if not isinstance(model2, str) or not model2.strip() or model2 != model2.strip():
        raise ValueError("invalid_m5_model2")
    if (
        not isinstance(blind_commitment, dict)
        or blind_commitment.get("suite_id") != M5_BLIND_SUITE_ID
        or blind_commitment.get("instance_count") != 120
        or not _sha256(blind_commitment.get("commitment_file_sha256"))
        or not _sha256(blind_commitment.get("suite_content_sha256"))
    ):
        raise ValueError("invalid_m5_protocol_commitment")
    return {
        "schema_version": _PROTOCOL_SCHEMA,
        "protocol_id": M5_PROTOCOL_ID,
        "blind_commitment": blind_commitment,
        "arm_seeds": plan,
        "model2": model2,
        "roster_cells": cells,
        "request_cap": M5_REQUEST_CAP,
        "checkpoints": [M5_REQUEST_CAP],
        "solver_rules": {
            "solve_deadline_ms": M5_SOLVE_DEADLINE_MS,
            "enforce_wall_deadline": True,
            "comparator_solvers": list(M5_COMPARATOR_LABELS),
            "baseline_algorithms": [name for name, _ in M5_BASELINE_ALGORITHMS],
        },
        "metric_rules": {
            "overall_noncompletion_penalty": "2 * reference_objective",
            "inference_unit": "paired_blind_instances_within_each_seed",
            "paired_test": "two_sided_wilcoxon_signed_rank",
            "paired_bootstrap_draws": 10_000,
            "multiple_testing": "holm_bonferroni_within_predeclared_family",
        },
        "contrast_families": {
            name: [list(pair) for pair in pairs] for name, pairs in M5_CONTRAST_FAMILIES.items()
        },
        "one_shot_attempt": {"scope": "external_custody", "claim_before": "sealed_file_open"},
    }


def freeze_pre_blind_protocol_m5(
    out_path: Path,
    *,
    commitment_path: Path = M5_BLIND_COMMITMENT_PATH,
    arm_seeds: Mapping[str, Sequence[int]] = M5_ARM_SEEDS,
    model2: str = "qwen4-max",
) -> dict[str, Any]:
    commitment_sha = hashlib.sha256(Path(commitment_path).read_bytes()).hexdigest()
    commitment = read_public_milestone_blind_commitment(
        commitment_path, expected_sha256=commitment_sha, expected_suite_id=M5_BLIND_SUITE_ID,
    )
    if any(commitment.get(key) != value for key, value in _suite_design(_blind_design_rows()).items()):
        raise ValueError("m5_blind_commitment_design_mismatch")
    protocol = _protocol(arm_seeds, model2, {
        "suite_id": M5_BLIND_SUITE_ID,
        "instance_count": commitment["instance_count"],
        "commitment_file_sha256": commitment_sha,
        "suite_content_sha256": commitment["suite_content_sha256"],
    })
    written = _write_once(Path(out_path), protocol)
    return {"protocol_path": written["path"], "protocol_sha256": written["sha256"], "protocol": protocol}


def read_m5_protocol(path: Path, expected_sha256: str) -> dict[str, Any]:
    protocol = _read_pinned(path, expected_sha256, "m5_protocol")
    if protocol != _protocol(protocol.get("arm_seeds"), protocol.get("model2"), protocol.get("blind_commitment")):
        raise ValueError("invalid_m5_pre_blind_protocol")
    return protocol


def _validate_solver_identity(solver: FrozenInterfaceSolver) -> None:
    template = get_template_spec(solver.template_id, solver.template_version)
    if (
        solver.problem_family != "cvrp" or solver.protocol_id not in (None, _CVRP_PROTOCOL_ID)
        or template.problem_family != "cvrp" or template.effective_protocol_id != _CVRP_PROTOCOL_ID
        or solver.template_source_sha256 != template.template_source_sha256
        or solver.hook_name != template.hook_name or solver.hook_specs != template.hook_specs
    ):
        raise ValueError("invalid_m5_frozen_solver_identity")


def _read_roster(
    protocol: Mapping[str, Any], snapshot_paths: Mapping[str, Path], missing_cells: Mapping[str, str],
) -> tuple[list[dict[str, str]], dict[str, FrozenInterfaceSolver]]:
    cells = protocol["roster_cells"]
    if set(snapshot_paths) & set(missing_cells) or (set(snapshot_paths) | set(missing_cells)) != set(cells):
        raise ValueError("m5_roster_must_cover_every_cell_once")
    if any(reason != "no_eligible_snapshot" for reason in missing_cells.values()):
        raise ValueError("invalid_m5_missing_cell_reason")
    roster = []
    solvers = {}
    for cell in cells:
        if cell in missing_cells:
            roster.append({"cell": cell, "missing_reason": missing_cells[cell]})
            continue
        data = Path(snapshot_paths[cell]).read_bytes()
        solver = FrozenInterfaceSolver.from_dict(json.loads(data))
        _validate_solver_identity(solver)
        roster.append({"cell": cell, "snapshot_sha256": hashlib.sha256(data).hexdigest()})
        solvers[cell] = solver
    return roster, solvers


def freeze_m5_roster_lock(
    out_path: Path,
    *,
    protocol_path: Path,
    expected_protocol_sha256: str,
    snapshot_paths: Mapping[str, Path],
    missing_cells: Mapping[str, str],
) -> dict[str, Any]:
    protocol = read_m5_protocol(protocol_path, expected_protocol_sha256)
    roster, _ = _read_roster(protocol, snapshot_paths, missing_cells)
    lock = {"schema_version": _LOCK_SCHEMA, "protocol_sha256": expected_protocol_sha256, "roster": roster}
    written = _write_once(Path(out_path), lock)
    return {"roster_lock_path": written["path"], "roster_lock_sha256": written["sha256"], "roster_lock": lock}


def load_locked_m5_roster(
    *,
    protocol_path: Path,
    expected_protocol_sha256: str,
    roster_lock_path: Path,
    expected_roster_lock_sha256: str,
    snapshot_paths: Mapping[str, Path],
) -> tuple[dict[str, Any], dict[str, FrozenInterfaceSolver], dict[str, str]]:
    protocol = read_m5_protocol(protocol_path, expected_protocol_sha256)
    lock = _read_pinned(roster_lock_path, expected_roster_lock_sha256, "m5_roster_lock")
    if lock.get("schema_version") != _LOCK_SCHEMA or lock.get("protocol_sha256") != expected_protocol_sha256:
        raise ValueError("m5_roster_lock_protocol_mismatch")
    missing = {row["cell"]: row["missing_reason"] for row in lock["roster"] if "missing_reason" in row}
    current, solvers = _read_roster(protocol, snapshot_paths, missing)
    if current != lock["roster"]:
        raise ValueError("m5_locked_snapshot_roster_mismatch")
    return protocol, solvers, missing


def build_m5_public_record(
    instance: Mapping[str, Any],
    result: Mapping[str, Any],
    *,
    exact_k_applicable: bool = True,
    solve_deadline_ms: float | None = M5_SOLVE_DEADLINE_MS,
) -> dict[str, Any]:
    """Project an evaluator result to an allowlist of public metrics."""
    row = _public_record(instance, result)
    solve_ms = row.get("solve_ms")
    if row["budget_exhausted"] or (
        solve_deadline_ms is not None and solve_ms is not None and float(solve_ms) > float(solve_deadline_ms)
    ):
        row["completed"] = False
        row["budget_exhausted"] = True
    exact_k_feasible = row["feasible"] and result.get("exact_vehicle_count") is True
    return {
        **row,
        "size": int(instance["size"]),
        "exact_k_applicable": exact_k_applicable,
        "exact_k_feasible": exact_k_feasible if exact_k_applicable else None,
    }


def unseal_and_evaluate_m5(
    *,
    protocol_path: Path,
    expected_protocol_sha256: str,
    roster_lock_path: Path,
    expected_roster_lock_sha256: str,
    snapshot_paths: Mapping[str, Path],
    output_dir: Path,
    commitment_path: Path = M5_BLIND_COMMITMENT_PATH,
    custody_dir: Path | None = None,
    repo_root: Path = _REPO,
    baseline_algorithms: Sequence[tuple[str, float]] = M5_BASELINE_ALGORITHMS,
    comparator_solvers: Sequence[tuple[str, FrozenInterfaceSolver, float]] = (),
) -> dict[str, Any]:
    """Verify the roster, consume the custody attempt, and publish metrics."""
    root = _m5_custody_dir(custody_dir, repo_root)
    protocol = read_m5_protocol(protocol_path, expected_protocol_sha256)
    pinned = protocol["blind_commitment"]
    content_marker = _custody_path(root, f"{M5_BLIND_SUITE_ID}.{pinned['suite_content_sha256']}.consumed", repo_root)
    if content_marker.exists():
        raise FileExistsError("blind_attempt_already_consumed")
    _, solvers, missing = load_locked_m5_roster(
        protocol_path=protocol_path,
        expected_protocol_sha256=expected_protocol_sha256,
        roster_lock_path=roster_lock_path,
        expected_roster_lock_sha256=expected_roster_lock_sha256,
        snapshot_paths=snapshot_paths,
    )
    report_path = Path(output_dir) / "m5_blind_evaluation.json"
    if report_path.exists():
        if content_marker.exists():
            raise FileExistsError("blind_attempt_already_consumed")
        raise FileExistsError("blind_evaluation_output_exists")
    labels = [label for label, _, _ in comparator_solvers]
    algorithms = [name for name, _ in baseline_algorithms]
    if len(labels) != len(set(labels)) or set(labels) != set(M5_COMPARATOR_LABELS):
        raise ValueError("invalid_m5_comparator_labels")
    if len(algorithms) != len(set(algorithms)) or set(algorithms) != {name for name, _ in M5_BASELINE_ALGORITHMS}:
        raise ValueError("invalid_m5_baseline_algorithms")
    for _, solver, deadline in comparator_solvers:
        _validate_solver_identity(solver)
        if deadline != M5_SOLVE_DEADLINE_MS:
            raise ValueError("invalid_m5_comparator_deadline")
    if any(deadline != M5_SOLVE_DEADLINE_MS for _, deadline in baseline_algorithms):
        raise ValueError("invalid_m5_baseline_deadline")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    sealed, verification = _claim_and_open(
        suite_id=M5_BLIND_SUITE_ID,
        custody_dir=root,
        commitment_path=commitment_path,
        commitment_sha256=pinned["commitment_file_sha256"],
        repo_root=repo_root,
    )
    if (
        verification["suite_content_sha256"] != pinned["suite_content_sha256"]
        or verification["instance_count"] != pinned["instance_count"]
    ):
        raise ValueError("m5_verified_suite_does_not_match_protocol")

    policy = {
        "distance_convention": sealed["distance_convention"],
        "vehicle_limit_policy": sealed["vehicle_limit_policy"],
        "enforce_wall_deadline": True,
    }

    def score_solver(solver: FrozenInterfaceSolver) -> list[dict[str, Any]]:
        rows = []
        for instance in sealed["instances"]:
            result = evaluate_frozen_interface_solver(solver, instance, solve_deadline_ms=M5_SOLVE_DEADLINE_MS, **policy)
            if result.get("error_code") in {"worker_protocol", "worker_crash"}:
                raise RuntimeError("m5_frozen_worker_failed")
            rows.append(build_m5_public_record(instance, result))
        return rows

    try:
        records = [
            {"cell": cell, **row}
            for cell, solver in solvers.items()
            for row in score_solver(solver)
        ]
        baseline_records = {label: score_solver(solver) for label, solver, _ in comparator_solvers}
        for name, deadline in baseline_algorithms:
            baseline_records[f"{name}@500ms"] = [
                build_m5_public_record(instance, evaluate_algorithm_on_instance(
                    name, instance, time_budget_ms=deadline, record_trace=False, **policy,
                ))
                for instance in sealed["instances"]
            ]
    except Exception:
        raise RuntimeError("m5_blind_evaluation_failed_attempt_consumed") from None
    report = {
        "schema_version": "m5-blind-evaluation/v1",
        "suite_id": M5_BLIND_SUITE_ID,
        "protocol_sha256": expected_protocol_sha256,
        "roster_lock_sha256": expected_roster_lock_sha256,
        "missing_cells": missing,
        "records": records,
        "baseline_records": baseline_records,
    }
    output = _write_once(report_path, report)
    return {"report_path": output["path"], "report_sha256": output["sha256"], **report}
