"""Calibrate a CVRP latency screen on synthetic probes, then validate a locked policy."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import math
import os
import re
import sys
import tempfile
from collections.abc import Mapping, Sequence
from itertools import product
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from agent_skill_loop.cvrp_workbench.baselines_2026 import dual_timing_fields, summarize_solve_timing
from agent_skill_loop.interface_design.contracts import FrozenInterfaceSolver
from agent_skill_loop.interface_design.multiscale import (
    PROBE_DOMAIN, PROBE_SIZES, generate_stress_probe, reject as _reject, screening_pairs,
)
from agent_skill_loop.interface_design.runtime import evaluate_frozen_interface_solver
from agent_skill_loop.interface_design.templates import get_template_spec

RUNS = REPO / "experiments" / "milestone5_paratera" / "runs"
DEFAULT_LOCK = REPO / "build" / "s2_multiscale" / "multiscale_threshold_lock.json"
LOCK_SCHEMA = "s2-multiscale-threshold-lock/v1"
SET_X_SUITE = "cvrp_ext_cvrplib_x_100"
SIZE_BANDS = ((100, 200), (201, 400), (401, 600), (601, 800), (801, 1000))
FLEET_POLICIES = {"free_fleet": "free_fleet_min_k_lb", "exact-k": "strict_max_vehicles"}
_SOLVER_FIELDS = (
    "schema_version", "solver_id", "problem_family", "paradigm", "template_id", "template_version",
    "template_source_sha256", "postprocess_mode", "template_options", "hook_name", "hook_code",
    "hook_code_sha256", "design_sha256", "origin_run", "kb_release_id", "protocol_id",
    "hook_specs", "hook_implementations", "hook_hashes", "bundle_hash", "hook_contract_sha256",
)
_EXECUTION_FIELDS = (
    "template_id", "template_version", "template_source_sha256", "postprocess_mode", "template_options",
    "hook_name", "hook_code_sha256", "protocol_id", "hook_contract_sha256", "bundle_hash",
)
_PROTECTED_OUTPUTS = (
    "eoh_frozen", "benchmarks/eohs_v1", "knowledge_store", ".secrets", ".git",
    "experiments/milestone5_paratera", "research_agent", "agent_skill_loop/interface_design",
)


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _digest(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _solver(raw: Mapping[str, Any]) -> FrozenInterfaceSolver:
    if (not _digest(raw.get("hook_code_sha256")) or not _digest(raw.get("template_source_sha256"))
            or raw.get("problem_family") != "cvrp"):
        raise ValueError("invalid_frozen_cvrp_candidate")
    solver = FrozenInterfaceSolver.from_dict({key: raw[key] for key in _SOLVER_FIELDS if key in raw})
    template = get_template_spec(solver.template_id, solver.template_version)
    if (template.template_source_sha256 != solver.template_source_sha256
            or template.hook_name != solver.hook_name or template.hook_specs != solver.hook_specs
            or (template.protocol_id is not None and template.protocol_id != solver.protocol_id)):
        raise ValueError(f"candidate_template_contract_mismatch:{solver.solver_id}")
    return solver


def _historical_candidates() -> list[dict[str, Any]]:
    """Read only frozen round solver artifacts and deduplicate by execution identity."""
    roster: dict[str, dict[str, Any]] = {}
    for path in sorted(RUNS.glob("*/agent_artifacts/round_*_frozen_solver.json")):
        if (not re.fullmatch(r"round_\d+_frozen_solver\.json", path.name)
                or path.resolve() != path.absolute() or not path.is_file()):
            continue
        data = path.read_bytes()
        raw = json.loads(data)
        if raw.get("problem_family") != "cvrp":
            continue
        solver = _solver(raw).to_dict()
        candidate_id = _sha256({key: solver.get(key) for key in _EXECUTION_FIELDS})
        if candidate_id not in roster:
            roster[candidate_id] = {"candidate_id": candidate_id, "solver": solver, "sources": []}
        roster[candidate_id]["sources"].append({
            "path": path.relative_to(RUNS).as_posix(), "sha256": hashlib.sha256(data).hexdigest(),
        })
    if not roster:
        raise ValueError("no_historical_cvrp_candidates")
    return [roster[candidate_id] for candidate_id in sorted(roster)]


def _evaluate(solver: FrozenInterfaceSolver, instance: Mapping[str, Any], *, budget_ms: float,
              distance_convention: str, vehicle_limit_policy: str) -> dict[str, Any]:
    result = evaluate_frozen_interface_solver(
        solver, instance, solve_deadline_ms=budget_ms, distance_convention=distance_convention,
        vehicle_limit_policy=vehicle_limit_policy, enforce_wall_deadline=True,
    )
    if result.get("error_code") in {"worker_protocol", "worker_crash", "worker_start_failed"}:
        raise RuntimeError(f"solver_worker_failed:{solver.solver_id}:{result['error_code']}")
    feasible = result.get("valid") is True and (
        vehicle_limit_policy != FLEET_POLICIES["exact-k"] or result.get("exact_vehicle_count") is True
    )
    return {
        "budget_ms": budget_ms, "status": result.get("status"),
        "budget_exhausted": result.get("budget_exhausted") is True,
        "time_limit_reached": result.get("time_limit_reached") is True,
        "timeout_kind": result.get("timeout_kind"),
        **dual_timing_fields(result, budget_ms=budget_ms, feasible=feasible),
    }


def _latency_label(row: Mapping[str, Any]) -> str:
    if row["returned_before_deadline"]:
        return "on_time"
    if row["solve_censored"] or (row["deadline_overrun_ms"] or 0) > 0:
        return "deadline_miss"
    return "unclassified"


def _measure_probes(solver: FrozenInterfaceSolver, budget_ms: float, replicates: int) -> list[dict[str, Any]]:
    observations = []
    for replicate in range(replicates):
        for size in PROBE_SIZES:
            timing = _evaluate(
                solver, generate_stress_probe(size, replicate=replicate), budget_ms=budget_ms,
                distance_convention="euc_2d_float", vehicle_limit_policy=FLEET_POLICIES["free_fleet"],
            )
            observations.append({
                "replicate": replicate, "size": size, "solve_ms": timing["solve_ms"],
                "latency_label": _latency_label(timing),
                "returned_before_deadline": timing["returned_before_deadline"],
            })
    return observations


def _screening_pairs(observations: Sequence[Mapping[str, Any]], floor_ms: float) -> list[dict[str, Any]]:
    return screening_pairs(observations, floor_ms, stride=len(PROBE_SIZES))


def _error_rates(cases: Sequence[tuple[bool, str]]) -> dict[str, Any]:
    misses = [rejected for rejected, label in cases if label == "deadline_miss"]
    on_time = [rejected for rejected, label in cases if label == "on_time"]
    return {
        "deadline_miss_count": len(misses), "intercepted_deadline_miss_count": sum(misses),
        "interception_recall": sum(misses) / len(misses) if misses else None,
        "on_time_count": len(on_time), "false_reject_count": sum(on_time),
        "false_reject_rate": sum(on_time) / len(on_time) if on_time else None,
        "unclassified_count": len(cases) - len(misses) - len(on_time),
    }


def _large_probe_label(observations: Sequence[Mapping[str, Any]]) -> str:
    labels = {row["latency_label"] for row in observations if row["size"] in (400, 500)}
    if "deadline_miss" in labels:
        return "deadline_miss"
    return "on_time" if labels == {"on_time"} else "unclassified"


def _choose_policy(roster: Sequence[Mapping[str, Any]], budget_ms: float) -> tuple[dict[str, float], dict[str, Any]]:
    """Minimize balanced error on N400/500, favoring the central prior on ties."""
    # Midpoint first in each prior grid. The absolute cap extrapolates N200 to
    # N500 with polynomial scaling. The trigger ignores small absolute runtimes.
    exponents = (2.5, 2.0, 3.0)
    grids = product((1.0, 0.5, 2.0), (0.02, 0.01, 0.05), exponents, exponents)
    best_error = math.inf
    for floor, trigger_fraction, ratio_exp, cap_exp in grids:
        policy = {
            "floor_ms": floor, "min_t200_trigger_ms": budget_ms * trigger_fraction,
            "max_ratio_200_100": 2 ** ratio_exp, "n200_abs_cap_ms": budget_ms / (2.5 ** cap_exp),
        }
        rates = _error_rates([
            (_reject(_screening_pairs(row["synthetic_observations"], floor), policy),
             _large_probe_label(row["synthetic_observations"])) for row in roster
        ])
        errors = []
        if rates["interception_recall"] is not None:
            errors.append(1 - rates["interception_recall"])
        if rates["false_reject_rate"] is not None:
            errors.append(rates["false_reject_rate"])
        error = sum(errors) / len(errors) if errors else 0.0
        if error < best_error:
            best_error, best_policy, best_rates = error, policy, rates
    return best_policy, best_rates


def _artifact_path(path: Path) -> Path:
    path = path.resolve()
    if (any(path.is_relative_to(REPO / name) for name in _PROTECTED_OUTPUTS)
            or any(part.casefold() in {".secrets", ".agent_skill_custody"} for part in path.parts)
            or (path.parent == REPO / "agent_skill_loop" and path.name.startswith("session_"))):
        raise ValueError(f"protected_artifact_path:{path}")
    return path


def _write_new_json(path: Path, value: Any) -> None:
    """Publish a complete file atomically and fail if another writer got there first."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, indent=2, allow_nan=False).encode("utf-8") + b"\n"
    with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".tmp", delete=False) as handle:
        temporary = Path(handle.name)
        try:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        except BaseException:
            handle.close()
            temporary.unlink()
            raise
    try:
        if os.name == "nt":
            os.rename(temporary, path)  # Windows rename fails if the destination exists.
        else:
            os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _is_number(value: Any, *, allow_zero: bool = False) -> bool:
    return (type(value) in (float, int) and math.isfinite(value)
            and (value >= 0 if allow_zero else value > 0))


def calibrate_lock(path: Path, *, budget_ms: float = 500, replicates: int = 3) -> dict[str, Any]:
    path = _artifact_path(path)
    if path.exists():
        raise FileExistsError(f"threshold_lock_already_exists:{path}")
    if not _is_number(budget_ms) or budget_ms < 1 or type(replicates) is not int or replicates < 1:
        raise ValueError("budget_ms_must_be_at_least_one_and_replicates_positive")
    roster = _historical_candidates()
    for candidate in roster:
        candidate["synthetic_observations"] = _measure_probes(_solver(candidate["solver"]), budget_ms, replicates)
    policy, fit_metrics = _choose_policy(roster, budget_ms)
    for candidate in roster:
        candidate["screening_pairs"] = _screening_pairs(candidate["synthetic_observations"], policy["floor_ms"])
        candidate["screen_reject"] = _reject(candidate["screening_pairs"], policy)
    payload = {
        "schema_version": LOCK_SCHEMA, "set_x_untouched": True, "probe_domain": PROBE_DOMAIN,
        "probe_sizes": list(PROBE_SIZES), "probe_replicates": replicates, "budget_ms": budget_ms,
        "calibration_fleet_policy": FLEET_POLICIES["free_fleet"], "validation_fleet_policies": FLEET_POLICIES,
        "validation_size_bands": [list(band) for band in SIZE_BANDS], "policy": policy,
        "synthetic_fit_metrics": fit_metrics, "candidates": roster,
    }
    lock = {**payload, "lock_sha256": _sha256(payload)}
    _write_new_json(path, lock)
    return lock


def _matching_screening_pairs(saved: Any, computed: Sequence[Mapping[str, Any]]) -> bool:
    # log2 is diagnostic and can differ by one ULP across platform libms.
    if not isinstance(saved, list) or len(saved) != len(computed):
        return False
    for recorded, current in zip(saved, computed, strict=True):
        if not isinstance(recorded, dict) or recorded.keys() != current.keys():
            return False
        for key, value in current.items():
            old = recorded[key]
            if key == "estimated_exponent" and value is not None:
                if type(old) not in (int, float) or not math.isclose(old, value, rel_tol=1e-15, abs_tol=1e-15):
                    return False
            elif old != value:
                return False
    return True


def _locked_candidates(lock: Mapping[str, Any]) -> list[tuple[Mapping[str, Any], FrozenInterfaceSolver]]:
    roster = lock["candidates"]
    if not isinstance(roster, list) or not roster:
        raise ValueError("missing_candidate_roster")
    locked_candidates = []
    seen = set()
    for candidate in roster:
        solver = _solver(candidate["solver"])
        manifest = solver.to_dict()
        candidate_id = _sha256({key: manifest.get(key) for key in _EXECUTION_FIELDS})
        if candidate_id != candidate["candidate_id"] or candidate_id in seen:
            raise ValueError("invalid_or_duplicate_candidate_id")
        seen.add(candidate_id)
        sources = candidate["sources"]
        if not isinstance(sources, list) or not sources or any(
            not _digest(source["sha256"])
            or not re.fullmatch(r"[^/\\]+/agent_artifacts/round_\d+_frozen_solver\.json", source["path"])
            or source["path"].split("/")[0] in {".", ".."}
            for source in sources
        ):
            raise ValueError("invalid_candidate_provenance")
        observations = candidate["synthetic_observations"]
        if len(observations) != lock["probe_replicates"] * len(PROBE_SIZES):
            raise ValueError("unexpected_synthetic_probe_count")
        expected = list(product(range(lock["probe_replicates"]), PROBE_SIZES))
        if [(row["replicate"], row["size"]) for row in observations] != expected:
            raise ValueError("unexpected_synthetic_probe_observations")
        for row in observations:
            label = row["latency_label"]
            if (label not in {"on_time", "deadline_miss", "unclassified"}
                    or row["returned_before_deadline"] is not (label == "on_time")
                    or (row["solve_ms"] is not None and not _is_number(row["solve_ms"], allow_zero=True))):
                raise ValueError("invalid_synthetic_probe_observation")
        pairs = _screening_pairs(observations, lock["policy"]["floor_ms"])
        if (not _matching_screening_pairs(candidate["screening_pairs"], pairs)
                or candidate["screen_reject"] is not _reject(pairs, lock["policy"])):
            raise ValueError("lock_screening_decision_mismatch")
        locked_candidates.append((candidate, solver))
    return locked_candidates


def read_threshold_lock(path: Path) -> dict[str, Any]:
    """Verify integrity, lock semantics, and executable candidate identities."""
    try:
        lock = json.loads(_artifact_path(path).read_bytes())
        if not isinstance(lock, dict):
            raise ValueError("lock_must_be_a_json_object")
        digest = lock.get("lock_sha256")
        payload = {key: value for key, value in lock.items() if key != "lock_sha256"}
        if not _digest(digest) or not hmac.compare_digest(digest, _sha256(payload)):
            raise ValueError("lock_sha256_mismatch")
        if (lock["schema_version"] != LOCK_SCHEMA or lock["set_x_untouched"] is not True
                or lock["probe_domain"] != PROBE_DOMAIN or lock["probe_sizes"] != list(PROBE_SIZES)
                or lock["calibration_fleet_policy"] != FLEET_POLICIES["free_fleet"]
                or lock["validation_fleet_policies"] != FLEET_POLICIES
                or lock["validation_size_bands"] != [list(band) for band in SIZE_BANDS]
                or not _is_number(lock["budget_ms"]) or lock["budget_ms"] < 1
                or type(lock["probe_replicates"]) is not int or lock["probe_replicates"] < 1):
            raise ValueError("lock_configuration_mismatch")
        policy = lock["policy"]
        if (set(policy) != {"floor_ms", "min_t200_trigger_ms", "max_ratio_200_100", "n200_abs_cap_ms"}
                or not all(_is_number(value) for value in policy.values())):
            raise ValueError("invalid_locked_threshold_policy")
        _locked_candidates(lock)
        expected_policy, expected_metrics = _choose_policy(lock["candidates"], lock["budget_ms"])
        if (policy, lock["synthetic_fit_metrics"]) != (expected_policy, expected_metrics):
            raise ValueError("lock_policy_does_not_match_synthetic_fit")
    except (OSError, KeyError, AttributeError, TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"invalid_threshold_lock:{path}:{exc}") from exc
    return lock


def _load_setx() -> dict[str, Any]:
    from agent_skill_loop.interface_design.session_baseline import load_dev_or_public_suite

    suite = load_dev_or_public_suite(SET_X_SUITE, split="heldout", role="external_evaluation")
    instances = suite["instances"]
    if (suite["suite_id"] != SET_X_SUITE or suite["split"] != "heldout" or len(instances) != 100
            or len({row["instance_id"] for row in instances}) != len(instances)):
        raise ValueError("unexpected_set_x_suite")
    return suite


def _summarize_stratum(rows: Sequence[Mapping[str, Any]], candidate_count: int) -> dict[str, Any]:
    on_time_by_instance: dict[str, int] = {}
    for row in rows:
        instance_id = row["instance_id"]
        on_time_by_instance[instance_id] = on_time_by_instance.get(instance_id, 0) + row["returned_before_deadline"]
    common = [row for row in rows if on_time_by_instance[row["instance_id"]] == candidate_count]
    return {
        "n_instances": len(on_time_by_instance), "n_candidate_instance_pairs": len(rows),
        **_error_rates([(row["screen_reject"], row["latency_label"]) for row in rows]),
        "overall": summarize_solve_timing(rows),
        "common_completed": {
            "n_instances": len(common) // candidate_count,
            **summarize_solve_timing(common),
        },
    }


def validate_setx(path: Path) -> dict[str, Any]:
    """Run every locked candidate, including rejects, on the independent Set X suite."""
    lock = read_threshold_lock(path)
    candidates = _locked_candidates(lock)
    suite = _load_setx()
    instances = []
    band_by_size = {size: f"{low}-{high}" for low, high in SIZE_BANDS for size in range(low, high + 1)}
    for source in suite["instances"]:
        # Exclude archived routes, reference objectives, and BKS metadata from solver inputs.
        instance = {key: source[key] for key in (
            "instance_id", "depot", "customer_coordinates", "demands", "capacity", "k_vehicles",
        )}
        size = len(instance["demands"])
        if size != source["size"] or size not in band_by_size or not instance["k_vehicles"]:
            raise ValueError(f"unexpected_set_x_instance:{source['instance_id']}")
        instances.append({**instance, "size": size})
    fleet_lanes = {}
    for lane, policy in FLEET_POLICIES.items():
        rows = []
        for candidate, solver in candidates:
            for instance in instances:
                timing = _evaluate(solver, instance, budget_ms=lock["budget_ms"],
                                   distance_convention=suite["distance_convention"], vehicle_limit_policy=policy)
                rows.append({
                    "candidate_id": candidate["candidate_id"], "solver_id": solver.solver_id,
                    "instance_id": instance["instance_id"], "size": instance["size"],
                    "screen_reject": candidate["screen_reject"], "latency_label": _latency_label(timing),
                    **timing,
                })
        strata = {f"{low}-{high}": [] for low, high in SIZE_BANDS}
        for row in rows:
            strata[band_by_size[row["size"]]].append(row)
        fleet_lanes[lane] = {
            "vehicle_limit_policy": policy,
            "summary": _summarize_stratum(rows, len(candidates)),
            "by_size": {band: _summarize_stratum(subset, len(candidates)) for band, subset in strata.items()},
            "rows": rows,
        }
    return {
        "schema_version": "s2-multiscale-setx-validation/v1", "suite_id": SET_X_SUITE,
        "data_manifest_hash": suite.get("data_manifest_hash"), "lock_sha256": lock["lock_sha256"],
        "budget_ms": lock["budget_ms"], "policy": lock["policy"], "candidate_count": len(candidates),
        "metric_denominators": {
            "unit": "candidate_instance_pair_within_fleet_lane",
            "interception_recall": "right_censored_solves_or_observed_solve_overruns",
            "false_reject_rate": "verified_returns_before_deadline",
            "unclassified": "neither_deadline_miss_nor_verified_return_before_deadline",
            "common_completed": "instances_with_verified_returns_before_deadline_from_every_candidate",
        },
        "fleet_lanes": fleet_lanes,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    calibrate = commands.add_parser("calibrate-lock", help="Fit and freeze a screen using synthetic probes")
    validate = commands.add_parser("validate-setx", help="Evaluate frozen screening decisions on Set X")
    for command in (calibrate, validate):
        command.add_argument("--lock-file", type=Path, default=DEFAULT_LOCK)
    calibrate.add_argument("--budget-ms", type=float, default=500)
    calibrate.add_argument("--replicates", type=int, default=3)
    validate.add_argument("--output", type=Path, help="Defaults to setx_validation.json beside the lock")
    args = parser.parse_args(argv)
    try:
        if args.command == "calibrate-lock":
            calibrate_lock(args.lock_file, budget_ms=args.budget_ms, replicates=args.replicates)
            path = args.lock_file
        else:
            path = _artifact_path(args.output or args.lock_file.with_name("setx_validation.json"))
            if path == args.lock_file.resolve() or path.exists():
                raise ValueError(f"validation_output_already_exists_or_is_lock:{path}")
            _write_new_json(path, validate_setx(args.lock_file))
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
