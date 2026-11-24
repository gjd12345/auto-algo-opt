"""External custody and one-shot evaluation for the M3.1 and M3.2 blind suites."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import secrets
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from agent_skill_loop.cvrp_workbench import m31_suites as m31
from agent_skill_loop.cvrp_workbench.solvers import evaluate_algorithm_on_instance
from agent_skill_loop.cvrp_workbench.suites import MANIFESTS_DIR

from .blind_commitment import (
    ALL_BLIND_SUITE_IDS as _LEGACY_BLIND_SUITE_IDS,
    SEALED_M32_BLIND_SUITE_ID,
    _CAPACITY_LEVELS,
    _gen_coords,
    _gen_demands,
    _seeded_rng,
    _sha256_payload,
    assert_suite_not_blind as _assert_legacy_suite_not_blind,
    build_m2_blind_120_design,
    require_external_custody_path,
)
from .contracts import FrozenInterfaceSolver
from .runtime import derive_outer_timeout_s, evaluate_frozen_interface_solver
from .templates import get_template_spec

_REPO = Path(__file__).resolve().parents[2]
_M31_CUSTODY_NAME = ".agent_skill_custody_m31"
_M32_CUSTODY_NAME = ".agent_skill_custody_m32"
M32_BLIND_COMMITMENT_PATH = MANIFESTS_DIR / f"{SEALED_M32_BLIND_SUITE_ID}_commitment.json"
M32_PROTOCOL_ID = "cvrp_m32_scaling_blind/v1"
M32_CHECKPOINTS = (36, 100, 200, 400)
M32_SEEDS = (20261124, 20261125, 20261126)
M32_CONTROLS = ("model_routing", "l3b_dual_hook", "timeout_2000ms")
M32_REQUEST_CAP = M32_CHECKPOINTS[-1]
MILESTONE_BLIND_SUITE_IDS = m31.M31_BLIND_SUITE_IDS | {SEALED_M32_BLIND_SUITE_ID}
ALL_BLIND_SUITE_IDS = _LEGACY_BLIND_SUITE_IDS | MILESTONE_BLIND_SUITE_IDS
SELECTION_ROLES = frozenset({"selection", "selection_tuning"})
_M32_GENERATOR_VERSION = "cvrp_m32_blind_generator/v1"
_CVRP_PROTOCOL_ID = "cvrp/v1"
_LOCK_SCHEMA = "m32-blind-roster-lock/v1"
_TIMING_FIELDS = ("preprocess_ms", "solve_ms", "verify_ms")
_MISSING_REASONS = frozenset({"early_stop", "infrastructure_failure", "no_eligible_snapshot"})


def _write_once(path: Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    data = (json.dumps(payload, indent=2, allow_nan=False) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    return {"path": str(path), "sha256": hashlib.sha256(data).hexdigest()}


def _read_pinned(path: Path, expected_sha256: str, label: str) -> dict[str, Any]:
    data = Path(path).read_bytes()
    if hashlib.sha256(data).hexdigest() != expected_sha256:
        raise ValueError(f"{label}_sha256_mismatch")
    doc = json.loads(data)
    if not isinstance(doc, dict):
        raise ValueError(f"invalid_{label}")
    return doc


def _custody_path(root: Path, name: str, repo_root: Path) -> Path:
    root = require_external_custody_path(root, repo_root=repo_root)
    path = require_external_custody_path(root / name, repo_root=repo_root)
    if not path.is_relative_to(root) or any(part.casefold() == ".agent_skill_custody" for part in path.parts):
        raise ValueError("invalid_milestone_custody_path")
    return path


def read_public_milestone_blind_commitment(
    commitment_path: Path,
    *,
    expected_sha256: str | None = None,
    expected_suite_id: str | None = None,
) -> dict[str, Any]:
    """Read an M3.1 or M3.2 public commitment without opening custody."""
    data = Path(commitment_path).read_bytes()
    if expected_sha256 is not None and hashlib.sha256(data).hexdigest() != expected_sha256:
        raise ValueError("pre_blind_commitment_file_hash_mismatch")
    commitment = json.loads(data)
    forbidden_keys = {
        "sealed_seed_token", "seed", "seed_token", "depot", "coordinates", "customer_coordinates",
        "demands", "items", "item_sizes", "reference_objective",
    }

    def check_public(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in forbidden_keys:
                    raise ValueError(f"public_commitment_leaked_key:{key}")
                check_public(value)
        elif isinstance(node, list):
            for value in node:
                check_public(value)

    check_public(commitment)
    if not isinstance(commitment, dict):
        raise ValueError("invalid_milestone_blind_commitment")
    suite_id, rows = commitment.get("suite_id"), commitment.get("instances")
    if (
        not isinstance(suite_id, str) or suite_id not in MILESTONE_BLIND_SUITE_IDS
        or (expected_suite_id is not None and suite_id != expected_suite_id)
        or commitment.get("schema_version") != "milestone-blind-commitment/v1"
        or commitment.get("commitment_status") != "sealed"
        or not isinstance(rows, list) or not rows or len(rows) != commitment.get("instance_count")
    ):
        raise ValueError("invalid_milestone_blind_commitment")
    return commitment


def read_verified_milestone_blind_payload(
    *,
    sealed_path: Path,
    commitment_path: Path,
    expected_commitment_sha256: str | None = None,
    expected_suite_id: str | None = None,
    repo_root: Path = _REPO,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Read the private payload in custody and check every committed digest."""
    commitment = read_public_milestone_blind_commitment(
        commitment_path, expected_sha256=expected_commitment_sha256, expected_suite_id=expected_suite_id,
    )
    sealed_path = require_external_custody_path(sealed_path, repo_root=repo_root)
    sealed = json.loads(sealed_path.read_bytes())
    if not isinstance(sealed, dict) or sealed.get("schema_version") != "milestone-blind-sealed/v1":
        raise ValueError("invalid_milestone_blind_sealed_payload")
    for field in (
        "suite_id", "problem_family", "protocol_id", "distance_convention", "vehicle_limit_policy",
        "generator_version", "generator_source_sha256", "instance_count", "suite_content_sha256",
    ):
        if sealed.get(field) != commitment.get(field):
            raise ValueError(f"blind_protocol_field_mismatch:{field}")
    instances, commitment_rows = sealed.get("instances"), commitment["instances"]
    if not isinstance(instances, list) or len(instances) != len(commitment_rows):
        raise ValueError("blind_instance_count_mismatch")
    suite_sha = _sha256_payload(instances)
    if suite_sha != commitment["suite_content_sha256"]:
        raise ValueError("blind_suite_sha256_mismatch")
    for instance, row in zip(instances, commitment_rows, strict=True):
        if instance["instance_id"] != row["instance_id"]:
            raise ValueError("blind_instance_id_mismatch")
        if _sha256_payload(instance) != row["instance_sha256"]:
            raise ValueError("blind_instance_sha256_mismatch")
    return sealed, commitment, {
        "ok": True, "suite_id": commitment["suite_id"], "instance_count": len(instances),
        "suite_content_sha256": suite_sha, "verified_instances": len(instances),
    }


def verify_milestone_sealed_against_commitment(
    *,
    sealed_path: Path,
    commitment_path: Path,
    repo_root: Path = _REPO,
) -> dict[str, Any]:
    """Return the verification summary for a custody-held milestone suite."""
    _, _, verification = read_verified_milestone_blind_payload(
        sealed_path=sealed_path, commitment_path=commitment_path, repo_root=repo_root,
    )
    return verification


def assert_milestone_suite_not_blind(suite_id: str | None, suite_meta: Mapping[str, Any] | None = None) -> None:
    if suite_id in MILESTONE_BLIND_SUITE_IDS:
        raise ValueError(f"blind_suite_forbidden_in_dev_pipeline:{suite_id}")
    _assert_legacy_suite_not_blind(suite_id, suite_meta)


def assert_milestone_suite_allowed_for_interactive_role(
    suite_id: str | None,
    suite_meta: Mapping[str, Any] | None = None,
    *,
    role: str = "interactive_sandbox",
) -> None:
    """Reserve selection suites for explicit selection roles and blind data for custody."""
    assert_milestone_suite_not_blind(suite_id, suite_meta)
    is_selection = (
        suite_id == "cvrp_select_multiscale_64"
        or suite_id in m31.M31_SELECTION_SUITE_IDS
        or (isinstance(suite_meta, Mapping) and suite_meta.get("suite_role") in SELECTION_ROLES)
    )
    if is_selection and role not in SELECTION_ROLES:
        raise ValueError(f"selection_suite_forbidden_in_interactive_role:{suite_id}")


def _cell(size: int, spatial: str, depot: str, capacity: str, demand: str) -> str:
    return f"n{size}_{spatial}_{depot}_{capacity}_{demand}"


def m32_blind_suite_design() -> dict[str, Any]:
    return {
        "suite_id": SEALED_M32_BLIND_SUITE_ID,
        "problem_family": "cvrp",
        "problem_id": "cvrp_construct",
        "protocol_id": _CVRP_PROTOCOL_ID,
        "blind_protocol_id": M32_PROTOCOL_ID,
        "suite_role": "final_blind_acceptance",
        "exposure_status": "locked_m32_blind",
        "split": "blind",
        "distance_convention": "euc_2d_float",
        "vehicle_limit_policy": "unconstrained",
        "generator_version": _M32_GENERATOR_VERSION,
        "instance_count": 120,
        "stratification_spec": {"by_cell": dict(Counter(_cell(*cell) for cell in build_m2_blind_120_design()))},
        "reference_baseline": "nearest_neighbor",
        "exact_k_reference": "nearest_neighbor_route_count",
    }


def _seal(
    design: Mapping[str, Any],
    instances: Sequence[Mapping[str, Any]],
    *,
    seed_token: str,
    generator_source_sha256: str,
    commitment_path: Path,
    custody_dir: Path,
    repo_root: Path,
) -> dict[str, Any]:
    suite_id = design["suite_id"]
    sealed_path = _custody_path(custody_dir, f"{suite_id}_sealed.json", repo_root)
    commitment_path = Path(commitment_path).resolve()
    if sealed_path == commitment_path:
        raise ValueError("blind_commitment_and_private_paths_must_differ")
    if commitment_path.exists():
        raise FileExistsError("public_blind_commitment_already_exists")
    if Counter(row["cell"] for row in instances) != design["stratification_spec"]["by_cell"]:
        raise ValueError("blind_achieved_cell_counts_mismatch")
    metadata = {
        **design,
        "generator_source_sha256": generator_source_sha256,
        "suite_content_sha256": _sha256_payload(instances),
    }
    commitment = {
        **metadata,
        "schema_version": "milestone-blind-commitment/v1",
        "commitment_status": "sealed",
        "instances": [
            {"instance_id": row["instance_id"], "cell": row["cell"], "instance_sha256": _sha256_payload(row)}
            for row in instances
        ],
    }
    _write_once(sealed_path, {
        **metadata, "schema_version": "milestone-blind-sealed/v1",
        "sealed_seed_token": seed_token, "instances": instances,
    })
    public_file = _write_once(commitment_path, commitment)
    return {
        "suite_id": suite_id,
        "instance_count": len(instances),
        "sealed_path": str(sealed_path),
        "commitment_path": public_file["path"],
        "commitment_sha256": public_file["sha256"],
        "suite_content_sha256": commitment["suite_content_sha256"],
    }


def seal_m31_blind_suite(
    problem_family: str,
    *,
    commitment_path: Path | None = None,
    custody_dir: Path | None = None,
    seed_token: str | None = None,
    repo_root: Path = _REPO,
) -> dict[str, Any]:
    """Create a new external seal and hash-only M3.1 commitment."""
    design = {**m31.m31_suite_design(problem_family, "blind"), "exposure_status": "locked_m31_blind"}
    seed = secrets.token_hex(32) if seed_token is None else seed_token
    instances = m31.build_m31_suite(problem_family, "blind", seed_token=seed)
    public_splits = [
        m31.build_m31_suite(family, split)
        for family in m31.M31_PROTOCOL_IDS for split in ("dev", "select")
    ]
    m31.assert_m31_splits_disjoint(*public_splits, instances)
    return _seal(
        design, instances, seed_token=seed,
        generator_source_sha256=hashlib.sha256(Path(m31.__file__).read_bytes()).hexdigest(),
        commitment_path=commitment_path or MANIFESTS_DIR / f"{design['suite_id']}_commitment.json",
        custody_dir=custody_dir if custody_dir is not None else Path.home() / _M31_CUSTODY_NAME,
        repo_root=repo_root,
    )


def seal_m32_blind_120(
    *,
    commitment_path: Path = M32_BLIND_COMMITMENT_PATH,
    custody_dir: Path | None = None,
    seed_token: str | None = None,
    repo_root: Path = _REPO,
) -> dict[str, Any]:
    """Generate the M3.2 holdout in its own seed namespace and external custody."""
    design = m32_blind_suite_design()
    seed = secrets.token_hex(32) if seed_token is None else seed_token
    if not seed:
        raise ValueError("m32_blind_requires_private_seed")
    instances = []
    for index, (size, spatial, depot_style, capacity_level, demand_dist) in enumerate(build_m2_blind_120_design()):
        cell = _cell(size, spatial, depot_style, capacity_level, demand_dist)
        rng = _seeded_rng(seed, f"{SEALED_M32_BLIND_SUITE_ID}/{cell}", index)
        instance = {
            "instance_id": f"m32blind_{cell}-{index:03d}",
            "cell": cell,
            "size": size,
            "spatial": spatial,
            "depot_style": depot_style,
            "capacity_level": capacity_level,
            "demand_dist": demand_dist,
            "source_tag": SEALED_M32_BLIND_SUITE_ID,
            "protocol_id": _CVRP_PROTOCOL_ID,
            "depot": [0.5, 0.5] if depot_style == "centre" else [0.05, 0.95],
            "customer_coordinates": _gen_coords(spatial, rng, size),
            "demands": _gen_demands(demand_dist, rng, size),
            "capacity": _CAPACITY_LEVELS[capacity_level],
        }
        reference = evaluate_algorithm_on_instance("nn", instance, record_trace=False)
        if not reference["valid"] or reference["tour_length"] is None:
            raise RuntimeError("m32_nn_reference_failed")
        instance.update(reference_objective=float(reference["tour_length"]),
                        reference_kind="solver_reference", k_vehicles=reference["route_count"])
        instances.append(instance)
    return _seal(
        design, instances, seed_token=seed,
        generator_source_sha256=_sha256_payload([
            hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            hashlib.sha256(Path(_seeded_rng.__code__.co_filename).read_bytes()).hexdigest(),
        ]),
        commitment_path=commitment_path,
        custody_dir=custody_dir if custody_dir is not None else Path.home() / _M32_CUSTODY_NAME,
        repo_root=repo_root,
    )


def _roster_cells(seeds: Sequence[int], controls: Sequence[str]) -> list[str]:
    return [
        f"{seed}:{cell}"
        for seed in seeds
        for cell in [*(f"checkpoint:{n}" for n in M32_CHECKPOINTS), *(f"control:{name}" for name in controls)]
    ]


def _validate_plan(seeds: Sequence[int], controls: Sequence[str], time_budget_ms: float) -> None:
    if not seeds or any(type(seed) is not int or seed < 0 for seed in seeds) or len(set(seeds)) != len(seeds):
        raise ValueError("invalid_m32_seeds")
    if not controls or any(not isinstance(name, str) or not re.fullmatch(r"[a-zA-Z0-9_-]+", name) for name in controls):
        raise ValueError("invalid_m32_controls")
    if len(set(controls)) != len(controls):
        raise ValueError("duplicate_m32_controls")
    if not _valid_deadline(time_budget_ms):
        raise ValueError("invalid_m32_solver_deadline")


def _valid_deadline(value: Any) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def _rules(
    time_budget_ms: float,
    controls: Sequence[str],
    roster_cells: Sequence[str],
    control_deadlines_ms: Mapping[str, float] | None,
    cell_deadlines_ms: Mapping[str, float] | None,
) -> dict[str, Any]:
    control_overrides = {"timeout_2000ms": 2000.0} if "timeout_2000ms" in controls else {}
    control_overrides.update(control_deadlines_ms or {})
    cell_overrides = dict(cell_deadlines_ms or {})
    if set(control_overrides) - set(controls) or set(cell_overrides) - set(roster_cells):
        raise ValueError("m32_deadline_override_has_unknown_control_or_cell")
    if any(not _valid_deadline(value) for value in (*control_overrides.values(), *cell_overrides.values())):
        raise ValueError("invalid_m32_solver_deadline_override")
    cell_execution = {}
    for cell in roster_cells:
        _, kind, name = cell.split(":", 2)
        deadline = control_overrides.get(name, time_budget_ms) if kind == "control" else time_budget_ms
        deadline = float(cell_overrides.get(cell, deadline))
        cell_execution[cell] = {
            "solve_deadline_ms": deadline,
            "outer_timeout_s": derive_outer_timeout_s(1, deadline, minimum_s=5.0),
        }
    return {
        "solver_rules": {
            "problem_family": "cvrp", "runtime_protocol_id": _CVRP_PROTOCOL_ID,
            "distance_convention": "euc_2d_float", "vehicle_limit_policy": "unconstrained",
            "solve_deadline_ms": time_budget_ms, "snapshot_type": "frozen_interface_solver_manifest",
            "control_deadlines_ms": control_overrides, "cell_deadlines_ms": cell_overrides,
            "cell_execution": cell_execution,
        },
        "metric_rules": {
            "objective": "verified_tour_length_minimize",
            "invalid_or_missing_raw_objective": None,
            "overall_noncompletion_penalty": "2 * reference_objective",
            "completed_comparison": "same_seed_paired_common_completed",
            "fleet_reporting": ["free_fleet", "exact_k_against_nn_reference"],
            "inference_unit": "paired_blind_instances_within_each_seed",
            "paired_test": "two_sided_wilcoxon_signed_rank",
            "paired_bootstrap_draws": 10_000,
            "multiple_testing": "holm_bonferroni_within_predeclared_family",
        },
        "stopping_rules": {
            "stop_search_at_requests": M32_REQUEST_CAP,
            "stop_earlier_on": ["predeclared_run_stop", "unrecoverable_infrastructure_failure"],
            "unreached_cells": "lock_as_explicit_missing_no_backfill",
            "after_unseal": "evaluate_locked_snapshots_only_no_search_or_retry",
        },
    }


def freeze_pre_blind_protocol_m32(
    out_path: Path,
    *,
    commitment_path: Path = M32_BLIND_COMMITMENT_PATH,
    seeds: Sequence[int] = M32_SEEDS,
    controls: Sequence[str] = M32_CONTROLS,
    time_budget_ms: float = 500.0,
    control_deadlines_ms: Mapping[str, float] | None = None,
    cell_deadlines_ms: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    """Freeze the study plan and deadlines before opening any blind data.

    A roster cell override takes precedence over a control override and the
    study-wide deadline. The timeout_2000ms control defaults to 2,000 ms.
    """
    _validate_plan(seeds, controls, time_budget_ms)
    roster_cells = _roster_cells(seeds, controls)
    rules = _rules(time_budget_ms, controls, roster_cells, control_deadlines_ms, cell_deadlines_ms)
    commitment_sha = hashlib.sha256(Path(commitment_path).read_bytes()).hexdigest()
    commitment = read_public_milestone_blind_commitment(
        commitment_path, expected_sha256=commitment_sha, expected_suite_id=SEALED_M32_BLIND_SUITE_ID,
    )
    design = m32_blind_suite_design()
    if any(commitment.get(key) != value for key, value in design.items()):
        raise ValueError("m32_blind_commitment_design_mismatch")
    protocol = {
        "schema_version": "m32-pre-blind-protocol/v1",
        "protocol_id": M32_PROTOCOL_ID,
        "blind_commitment": {
            "suite_id": SEALED_M32_BLIND_SUITE_ID, "instance_count": commitment["instance_count"],
            "commitment_file_sha256": commitment_sha, "suite_content_sha256": commitment["suite_content_sha256"],
        },
        "request_cap": M32_REQUEST_CAP,
        "checkpoints": list(M32_CHECKPOINTS),
        "seeds": list(seeds),
        "controls": list(controls),
        "roster_cells": roster_cells,
        "one_shot_attempt": {"scope": "external_custody", "key": commitment_sha, "claim_before": "sealed_file_open"},
        **rules,
    }
    written = _write_once(Path(out_path), protocol)
    return {"protocol_path": written["path"], "protocol_sha256": written["sha256"], "protocol": protocol}


def _read_protocol(path: Path, expected_sha256: str) -> dict[str, Any]:
    doc = _read_pinned(path, expected_sha256, "m32_protocol")
    seeds, controls = doc["seeds"], doc["controls"]
    solver_rules = doc["solver_rules"]
    deadline = solver_rules["solve_deadline_ms"]
    _validate_plan(seeds, controls, deadline)
    roster_cells = _roster_cells(seeds, controls)
    rules = _rules(
        deadline, controls, roster_cells, solver_rules["control_deadlines_ms"], solver_rules["cell_deadlines_ms"],
    )
    commitment = doc["blind_commitment"]
    if (
        doc.get("schema_version") != "m32-pre-blind-protocol/v1"
        or doc.get("protocol_id") != M32_PROTOCOL_ID
        or commitment.get("suite_id") != SEALED_M32_BLIND_SUITE_ID
        or doc.get("request_cap") != M32_REQUEST_CAP
        or doc.get("checkpoints") != list(M32_CHECKPOINTS)
        or doc.get("roster_cells") != roster_cells
        or doc.get("one_shot_attempt") != {
            "scope": "external_custody", "key": commitment["commitment_file_sha256"], "claim_before": "sealed_file_open",
        }
        or any(doc.get(key) != value for key, value in rules.items())
    ):
        raise ValueError("invalid_m32_pre_blind_protocol")
    return doc


def _read_roster(
    protocol: Mapping[str, Any],
    snapshot_paths: Mapping[str, Path],
    missing_cells: Mapping[str, str],
) -> tuple[list[dict[str, Any]], dict[str, FrozenInterfaceSolver]]:
    cells = protocol["roster_cells"]
    if not snapshot_paths or set(snapshot_paths) & set(missing_cells) or set(snapshot_paths) | set(missing_cells) != set(cells):
        raise ValueError("m32_roster_must_cover_every_cell_once")
    roster, solvers = [], {}
    for cell in cells:
        if cell in missing_cells:
            reason = missing_cells[cell]
            if reason not in _MISSING_REASONS:
                raise ValueError("invalid_m32_missing_cell_reason")
            roster.append({"cell": cell, "missing_reason": reason})
            continue
        data = Path(snapshot_paths[cell]).read_bytes()
        solver = FrozenInterfaceSolver.from_dict(json.loads(data))
        template = get_template_spec(solver.template_id, solver.template_version)
        if (
            solver.problem_family != "cvrp" or solver.protocol_id not in (None, _CVRP_PROTOCOL_ID)
            or template.problem_family != "cvrp"
            or template.effective_protocol_id != _CVRP_PROTOCOL_ID
            or solver.template_source_sha256 != template.template_source_sha256
            or solver.hook_name != template.hook_name or solver.hook_specs != template.hook_specs
        ):
            raise ValueError("invalid_m32_frozen_solver_identity")
        solvers[cell] = solver
        roster.append({"cell": cell, "snapshot_sha256": hashlib.sha256(data).hexdigest()})
    return roster, solvers


def freeze_m32_roster_lock(
    out_path: Path,
    *,
    protocol_path: Path,
    expected_protocol_sha256: str,
    snapshot_paths: Mapping[str, Path],
    missing_cells: Mapping[str, str],
) -> dict[str, Any]:
    """Bind every predeclared cell to exact snapshot bytes or an explicit missing reason.

    Cells use ``<seed>:checkpoint:<requests>`` or ``<seed>:control:<name>``.
    Missing reasons are ``early_stop``, ``infrastructure_failure`` or ``no_eligible_snapshot``.
    """
    protocol = _read_protocol(protocol_path, expected_protocol_sha256)
    roster, _ = _read_roster(protocol, snapshot_paths, missing_cells)
    lock = {"schema_version": _LOCK_SCHEMA, "protocol_sha256": expected_protocol_sha256, "roster": roster}
    written = _write_once(Path(out_path), lock)
    return {"roster_lock_path": written["path"], "roster_lock_sha256": written["sha256"], "roster_lock": lock}


def _claim_and_open(
    *,
    suite_id: str,
    custody_dir: Path,
    commitment_path: Path,
    commitment_sha256: str,
    repo_root: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    sealed_path = _custody_path(custody_dir, f"{suite_id}_sealed.json", repo_root)
    commitment = read_public_milestone_blind_commitment(
        commitment_path, expected_sha256=commitment_sha256, expected_suite_id=suite_id,
    )
    # The marker lives beside the sealed suite and is independent of any report
    # directory. The content digest also catches re-serialized commitments.
    content_sha = commitment["suite_content_sha256"]
    if not isinstance(content_sha, str) or not re.fullmatch(r"[0-9a-f]{64}", content_sha):
        raise ValueError("invalid_blind_suite_content_sha256")
    marker = _custody_path(custody_dir, f"{suite_id}.{commitment_sha256}.attempt", repo_root)
    content_marker = _custody_path(custody_dir, f"{suite_id}.{content_sha}.consumed", repo_root)
    # Claim the content identity first; this exclusive create is the one-shot
    # gate even if equivalent commitment bytes carry a different file hash.
    try:
        _write_once(content_marker, {"commitment_sha256": commitment_sha256})
        _write_once(marker, {"suite_content_sha256": content_sha})
    except FileExistsError:
        raise FileExistsError("blind_attempt_already_consumed") from None
    try:
        sealed, _, verification = read_verified_milestone_blind_payload(
            sealed_path=sealed_path, commitment_path=commitment_path, expected_commitment_sha256=commitment_sha256,
            expected_suite_id=suite_id, repo_root=repo_root,
        )
    except Exception:
        raise RuntimeError("blind_payload_verification_failed_attempt_consumed") from None
    return sealed, verification


def _number(value: Any) -> int | float | None:
    if type(value) in (int, float) and math.isfinite(value) and value >= 0:
        return value
    return None


def _public_record(instance: Mapping[str, Any], result: Mapping[str, Any]) -> dict[str, Any]:
    valid = result.get("valid") is True
    raw_objective = next((result[key] for key in ("objective", "tour_length", "bins_used") if result.get(key) is not None), None)
    objective = _number(raw_objective) if valid else None
    return {
        "instance_id": instance["instance_id"],
        "objective": objective,
        "reference_objective": _number(instance.get("reference_objective")),
        "feasible": valid and objective is not None,
        "completed": valid and objective is not None and (
            result.get("completed") is True if "completed" in result else result.get("status") == "ok"
        ),
        "budget_exhausted": result.get("budget_exhausted") is True,
        **{key: _number(result.get(key)) for key in _TIMING_FIELDS},
    }


def unseal_and_evaluate_m32(
    *,
    protocol_path: Path,
    expected_protocol_sha256: str,
    roster_lock_path: Path,
    expected_roster_lock_sha256: str,
    snapshot_paths: Mapping[str, Path],
    output_dir: Path,
    commitment_path: Path = M32_BLIND_COMMITMENT_PATH,
    custody_dir: Path | None = None,
    repo_root: Path = _REPO,
    baseline_algorithms: Sequence[tuple[str, float]] = (),
    comparator_solvers: Sequence[tuple[str, FrozenInterfaceSolver, float]] = (),
) -> dict[str, Any]:
    """Verify both locks, consume the attempt atomically, and publish metric records."""
    protocol = _read_protocol(protocol_path, expected_protocol_sha256)
    lock = _read_pinned(roster_lock_path, expected_roster_lock_sha256, "m32_roster_lock")
    if lock.get("schema_version") != _LOCK_SCHEMA or lock.get("protocol_sha256") != expected_protocol_sha256:
        raise ValueError("m32_roster_lock_protocol_mismatch")
    missing = {row["cell"]: row["missing_reason"] for row in lock["roster"] if "missing_reason" in row}
    current_roster, solvers = _read_roster(protocol, snapshot_paths, missing)
    if current_roster != lock["roster"]:
        raise ValueError("m32_locked_snapshot_roster_mismatch")
    pinned = protocol["blind_commitment"]
    report_path = Path(output_dir) / "m32_blind_evaluation.json"
    if report_path.exists():
        raise FileExistsError("blind_evaluation_output_exists")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    sealed, verification = _claim_and_open(
        suite_id=SEALED_M32_BLIND_SUITE_ID, commitment_path=commitment_path,
        custody_dir=custody_dir if custody_dir is not None else Path.home() / _M32_CUSTODY_NAME,
        commitment_sha256=pinned["commitment_file_sha256"], repo_root=repo_root,
    )
    if verification["suite_content_sha256"] != pinned["suite_content_sha256"] or verification["instance_count"] != pinned["instance_count"]:
        raise ValueError("m32_verified_suite_does_not_match_protocol")
    records = []
    baseline_records: dict[str, list[dict[str, Any]]] = {}
    try:
        for cell, solver in solvers.items():
            execution = protocol["solver_rules"]["cell_execution"][cell]
            for instance in sealed["instances"]:
                result = evaluate_frozen_interface_solver(
                    solver, instance, distance_convention=sealed["distance_convention"],
                    vehicle_limit_policy=sealed["vehicle_limit_policy"],
                    solve_deadline_ms=execution["solve_deadline_ms"], outer_timeout_s=execution["outer_timeout_s"],
                )
                if result.get("error_code") in {"worker_protocol", "worker_crash"}:
                    raise RuntimeError("m32_frozen_worker_failed")
                row = _public_record(instance, result)
                row["exact_k_feasible"] = row["feasible"] and result.get("exact_vehicle_count") is True
                records.append({"cell": cell, **row})
        if baseline_algorithms:
            from agent_skill_loop.cvrp_workbench.solvers import evaluate_algorithm_on_instance
            for alg_id, deadline_ms in baseline_algorithms:
                key = f"{alg_id}@{int(round(float(deadline_ms)))}ms"
                rows_b = []
                for instance in sealed["instances"]:
                    res_b = evaluate_algorithm_on_instance(
                        alg_id,
                        instance,
                        distance_convention=sealed["distance_convention"],
                        vehicle_limit_policy=sealed["vehicle_limit_policy"],
                        time_budget_ms=float(deadline_ms),
                        record_trace=False,
                        enforce_wall_deadline=False,
                    )
                    pub_b = _public_record(instance, res_b)
                    pub_b["exact_k_feasible"] = pub_b["feasible"] and res_b.get("exact_vehicle_count") is True
                    rows_b.append(pub_b)
                baseline_records[key] = rows_b
        for comp_label, comp_solver, comp_deadline_ms in comparator_solvers:
            outer_s = derive_outer_timeout_s(1, float(comp_deadline_ms), minimum_s=max(15.0, 4.0 * float(comp_deadline_ms) / 1000.0 + 3.0))
            rows_c = []
            for instance in sealed["instances"]:
                res_c = evaluate_frozen_interface_solver(
                    comp_solver, instance, distance_convention=sealed["distance_convention"],
                    vehicle_limit_policy=sealed["vehicle_limit_policy"],
                    solve_deadline_ms=float(comp_deadline_ms), outer_timeout_s=outer_s,
                    enforce_wall_deadline=False,
                )
                if res_c.get("error_code") in {"worker_protocol", "worker_crash"}:
                    raise RuntimeError("m32_comparator_worker_failed")
                pub_c = _public_record(instance, res_c)
                pub_c["exact_k_feasible"] = pub_c["feasible"] and res_c.get("exact_vehicle_count") is True
                rows_c.append(pub_c)
            baseline_records[comp_label] = rows_c
    except Exception:
        raise RuntimeError("m32_blind_evaluation_failed_attempt_consumed") from None
    report = {
        "schema_version": "m32-blind-evaluation/v1", "suite_id": SEALED_M32_BLIND_SUITE_ID,
        "protocol_sha256": expected_protocol_sha256, "roster_lock_sha256": expected_roster_lock_sha256,
        "missing_cells": missing, "records": records,
    }
    if baseline_records:
        report["baseline_records"] = baseline_records
    output = _write_once(report_path, report)
    return {"report_path": output["path"], "report_sha256": output["sha256"], **report}


def unseal_and_evaluate_m31(
    suite_id: str,
    *,
    commitment_path: Path,
    expected_commitment_sha256: str,
    evaluator: Callable[[Mapping[str, Any]], Mapping[str, Any]],
    output_dir: Path,
    custody_dir: Path | None = None,
    repo_root: Path = _REPO,
    extra_evaluators: Mapping[str, Callable[[Mapping[str, Any]], Mapping[str, Any]]] | None = None,
) -> dict[str, Any]:
    """Run a trusted in-custody evaluator once on an M3.1 suite."""
    if suite_id not in m31.M31_BLIND_SUITE_IDS:
        raise ValueError("unexpected_m31_blind_suite_id")
    report_path = Path(output_dir) / "m31_blind_evaluation.json"
    if report_path.exists():
        raise FileExistsError("blind_evaluation_output_exists")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    sealed, _ = _claim_and_open(
        suite_id=suite_id, commitment_path=commitment_path,
        custody_dir=custody_dir if custody_dir is not None else Path.home() / _M31_CUSTODY_NAME,
        commitment_sha256=expected_commitment_sha256, repo_root=repo_root,
    )
    extra_records: dict[str, list[dict[str, Any]]] = {}
    try:
        records = [_public_record(instance, evaluator(instance)) for instance in sealed["instances"]]
        if extra_evaluators:
            for label, fn in extra_evaluators.items():
                extra_records[str(label)] = [_public_record(instance, fn(instance)) for instance in sealed["instances"]]
    except Exception:
        raise RuntimeError("m31_blind_evaluation_failed_attempt_consumed") from None
    report = {"schema_version": "m31-blind-evaluation/v1", "suite_id": suite_id, "records": records}
    if extra_records:
        report["extra_solver_records"] = extra_records
    output = _write_once(report_path, report)
    return {"report_path": output["path"], "report_sha256": output["sha256"], **report}
