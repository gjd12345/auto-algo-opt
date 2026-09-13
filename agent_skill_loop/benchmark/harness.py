"""Offline benchmark harness and independent OBP calibration."""

from __future__ import annotations

import json
import hashlib
import math
from pathlib import Path
from typing import Any, Callable, Mapping

from agent_skill_loop.evaluator import SubprocessEvaluator
from agent_skill_loop.evaluator import evaluator_source_hash
from agent_skill_loop.problems.base import get_problem

from .catalog import benchmark_profile, load_profile_suite
from .contracts import FrozenSelection, MetricSpec, evaluation_identity, sha256_json, sha256_text


def load_suite(path: Path | None = None, *, benchmark_id: str = "eohs_v1", profile: str = "obp_mini", split: str = "dev_train") -> dict[str, Any]:
    if path is None:
        return load_profile_suite(benchmark_id, profile, split=split)
    benchmark, metric, _item = benchmark_profile(benchmark_id, profile)
    target = Path(path)
    raw = target.read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("instances"), list):
        raise ValueError("benchmark_suite_invalid")
    actual_data_hash = hashlib.sha256(raw).hexdigest()
    expected_data_hash = (
        benchmark.train_manifest_hash
        if split in {"train", "dev_train"}
        else benchmark.test_manifest_hash
        if split in {"test", "heldout"}
        else None
    )
    if expected_data_hash is None:
        raise ValueError("benchmark_split_not_supported")
    # A path supplied to the benchmark harness is still a registered frozen
    # manifest, not an arbitrary suite with a caller-assigned label.  The
    # standalone asset files identify themselves by their own bytes; a
    # Session-produced ``dev_suite.json`` is a container around that asset and
    # therefore carries the registry hash explicitly instead of hashing the
    # container a second time.
    declared_data_hash = payload.get("data_manifest_hash")
    if declared_data_hash is None:
        if actual_data_hash != expected_data_hash:
            raise ValueError("data_manifest_hash_not_registered")
        declared_data_hash = actual_data_hash
    elif declared_data_hash != expected_data_hash:
        raise ValueError("data_manifest_hash_mismatch")
    payload["data_manifest_hash"] = declared_data_hash
    if payload.get("benchmark_id") is not None and payload.get("benchmark_id") != benchmark_id:
        raise ValueError("benchmark_id_mismatch")
    payload["benchmark_id"] = benchmark_id
    if payload.get("profile") is not None and payload.get("profile") != profile:
        raise ValueError("benchmark_profile_mismatch")
    payload["profile"] = profile
    problem_id = payload.get("problem")
    if not isinstance(problem_id, str) or not problem_id.strip():
        raise ValueError("benchmark_suite_problem_missing")
    if problem_id != benchmark.problem_id:
        raise ValueError("benchmark_problem_mismatch")
    split_value = payload.get("split")
    if not isinstance(split_value, str) or not split_value.strip():
        raise ValueError("benchmark_suite_split_missing")
    expected_split = "dev_train" if split in {"train", "dev_train"} else "heldout"
    if split_value != expected_split:
        raise ValueError("benchmark_split_mismatch")
    problem = get_problem(problem_id)
    if payload.get("problem_spec_hash") is not None and payload.get("problem_spec_hash") != problem.content_hash:
        raise ValueError("problem_spec_hash_mismatch")
    payload["problem_spec_hash"] = problem.content_hash
    if payload.get("reference_manifest_hash") is not None and payload.get("reference_manifest_hash") != benchmark.reference_manifest_hash:
        raise ValueError("reference_manifest_hash_mismatch")
    payload["reference_manifest_hash"] = benchmark.reference_manifest_hash
    if payload.get("metric_spec_hash") is not None and payload.get("metric_spec_hash") != metric.content_hash:
        raise ValueError("metric_spec_hash_mismatch")
    payload["metric_spec_hash"] = metric.content_hash
    expected_suite_hash = problem.suite_hash(problem_id, split_value, payload["instances"])
    if payload.get("content_hash") is not None and payload.get("content_hash") != expected_suite_hash:
        raise ValueError("suite_hash_mismatch")
    payload["content_hash"] = expected_suite_hash
    problem.validate_suite(payload)
    return payload


def _upstream_pack(items: list[float], capacity: float, choose: Callable[[float, list[float]], int]) -> int:
    """Independent imperative implementation of the upstream OBP loop.

    This intentionally does not call the production candidate evaluator. It
    is the expected-value side of the differential calibration.
    """
    remaining: list[float] = []
    for item in items:
        feasible = [index for index, value in enumerate(remaining) if value + 1e-12 >= item]
        if not feasible:
            remaining.append(capacity - item)
            continue
        local_remaining = [remaining[index] for index in feasible]
        chosen_local = choose(item, local_remaining)
        if not isinstance(chosen_local, int) or not 0 <= chosen_local < len(feasible):
            raise ValueError("upstream_heuristic_return_invalid")
        remaining[feasible[chosen_local]] -= item
    return len(remaining)


def _first_fit(_item: float, _bins: list[float]) -> int:
    return 0


def _best_fit(_item: float, bins: list[float]) -> int:
    return min(range(len(bins)), key=lambda index: (bins[index], index))


def calibrate_upstream(suite: Mapping[str, Any]) -> dict[str, Any]:
    rows: dict[str, list[dict[str, Any]]] = {"first_fit": [], "best_fit": []}
    for instance in suite["instances"]:
        items = [float(item) for item in instance["items"]]
        capacity = float(instance["capacity"])
        reference = float(instance["reference_objective"])
        for name, chooser in (("first_fit", _first_fit), ("best_fit", _best_fit)):
            bins_used = _upstream_pack(items, capacity, chooser)
            rows[name].append({
                "instance_id": instance["instance_id"],
                "bins_used": bins_used,
                "reference": reference,
                "gap": (bins_used - reference) / reference,
            })
    return {
        "schema_version": "algorithm-optimization-obp-gold/v1",
        "benchmark_id": suite.get("benchmark_id"),
        "profile": suite.get("profile"),
        "problem": suite.get("problem"),
        "suite_hash": suite.get("content_hash"),
        "reference_kind": "upstream_compatibility_reference",
        "heuristics": rows,
    }


def calibrate_differential(suite: Mapping[str, Any], gold: Mapping[str, Any]) -> dict[str, Any]:
    expected = calibrate_upstream(suite)
    mismatches: list[dict[str, Any]] = []
    if not isinstance(gold, Mapping):
        raise ValueError("obp_gold_invalid")
    for key in ("benchmark_id", "profile", "problem", "suite_hash", "reference_kind"):
        if gold.get(key) != expected.get(key):
            mismatches.append({"field": key, "expected": expected.get(key), "actual": gold.get(key)})
    given = gold.get("heuristics") if isinstance(gold, Mapping) else None
    if not isinstance(given, Mapping):
        raise ValueError("obp_gold_invalid")
    try:
        actual = calibrate_production(suite)
    except Exception as exc:
        # A production evaluator mismatch must be reported as a failed
        # calibration, not as an unstructured traceback. This keeps the
        # zero-provider audit usable when the subprocess boundary regresses.
        return {
            "passed": False,
            "mismatches": [*mismatches, {
                "source": "production_evaluator",
                "error_code": "production_calibration_failed",
                "error_detail": str(exc)[:240],
            }],
            "expected_sha256": sha256_json(expected),
            "gold_sha256": sha256_json(gold),
            "production_sha256": None,
            "production_identity": None,
        }
    for name, expected_rows in expected["heuristics"].items():
        actual_rows = given.get(name, [])
        for index, expected_row in enumerate(expected_rows):
            gold_row = actual_rows[index] if index < len(actual_rows) else None
            if gold_row != expected_row:
                mismatches.append({"source": "gold", "heuristic": name, "index": index, "expected": expected_row, "actual": gold_row})
            production_row = actual["heuristics"].get(name, [])[index] if index < len(actual["heuristics"].get(name, [])) else None
            if production_row != expected_row:
                mismatches.append({"source": "production_evaluator", "heuristic": name, "index": index, "expected": expected_row, "actual": production_row})
    return {
        "passed": not mismatches,
        "mismatches": mismatches,
        "expected_sha256": sha256_json(expected),
        "gold_sha256": sha256_json(gold),
        "production_sha256": sha256_json(actual),
        "production_identity": actual["identity"],
    }


def _metric_for_suite(suite: Mapping[str, Any], metric_spec: MetricSpec | None = None) -> MetricSpec:
    if metric_spec is None:
        benchmark_id = suite.get("benchmark_id")
        profile = suite.get("profile")
        if not isinstance(benchmark_id, str) or not isinstance(profile, str):
            raise ValueError("metric_spec_required")
        _benchmark, metric_spec, _item = benchmark_profile(benchmark_id, profile)
    if suite.get("metric_spec_hash") != metric_spec.content_hash:
        raise ValueError("metric_spec_suite_mismatch")
    if suite.get("reference_manifest_hash") != metric_spec.reference_manifest_hash:
        raise ValueError("metric_reference_manifest_mismatch")
    kinds = {item.get("reference_kind") for item in suite.get("instances", []) if isinstance(item, Mapping)}
    if kinds and kinds != {metric_spec.reference_kind}:
        raise ValueError("metric_reference_kind_mismatch")
    if metric_spec.aggregation != "mean_instance_relative_gap":
        raise ValueError("metric_aggregation_not_supported")
    return metric_spec


def _benchmark_identity(suite: Mapping[str, Any], metric_spec: MetricSpec, code: str) -> dict[str, str]:
    problem = get_problem(str(suite.get("problem")))
    problem_hash = suite.get("problem_spec_hash") or problem.content_hash
    if problem_hash != problem.content_hash:
        raise ValueError("problem_spec_hash_mismatch")
    data_hash = suite.get("data_manifest_hash")
    if not isinstance(data_hash, str) or len(data_hash) != 64:
        raise ValueError("data_manifest_hash_required")
    evaluator_hash = evaluator_source_hash()
    code_hash = sha256_text(code)
    return {
        "candidate_code_sha256": code_hash,
        "problem_spec_hash": str(problem_hash),
        "data_manifest_hash": data_hash,
        "evaluator_hash": evaluator_hash,
        "metric_spec_hash": metric_spec.content_hash,
    }


def _calibration_code(name: str) -> str:
    if name == "first_fit":
        return "def priority(item, bins):\n    return -np.arange(len(bins), dtype=float)\n"
    if name == "best_fit":
        return "def priority(item, bins):\n    return -bins\n"
    raise ValueError("unknown_calibration_heuristic")


def calibrate_production(suite: Mapping[str, Any]) -> dict[str, Any]:
    """Run calibration candidates through the production subprocess evaluator."""
    metric = _metric_for_suite(suite)
    rows: dict[str, list[dict[str, Any]]] = {"first_fit": [], "best_fit": []}
    identities: dict[str, dict[str, str]] = {}
    for name in rows:
        code = _calibration_code(name)
        result = evaluate_candidate(code, suite, metric_spec=metric)
        identities[name] = result["identity"]
        if result.get("valid") is not True:
            raise ValueError(f"production_calibration_invalid:{name}:{result.get('error_code')}")
        metrics = result.get("metrics") or {}
        bins = metrics.get("bins_used")
        references = metrics.get("reference_objectives")
        if not isinstance(bins, list) or not isinstance(references, list):
            raise ValueError(f"production_calibration_metrics_missing:{name}")
        rows[name] = [
            {
                "instance_id": instance["instance_id"],
                "bins_used": int(bins[index]),
                "reference": float(references[index]),
                "gap": float(result["instance_objectives"][index]),
            }
            for index, instance in enumerate(suite["instances"])
        ]
    per_instance = []
    for index, instance in enumerate(suite["instances"]):
        member_gaps = [rows[name][index]["gap"] for name in rows]
        per_instance.append({
            "instance_id": instance["instance_id"],
            "member_gaps": member_gaps,
            "best_gap": min(member_gaps),
            "best_member": min(rows, key=lambda name: (rows[name][index]["gap"], name)),
        })
    return {
        "schema_version": "algorithm-optimization-obp-production-calibration/v1",
        "suite_hash": suite.get("content_hash"),
        "identity": identities,
        "heuristics": rows,
        "heuristic_set": {
            "member_ids": list(rows),
            "per_instance": per_instance,
            "aggregate_fitness": metric.aggregate([item["best_gap"] for item in per_instance]),
        },
    }


def evaluate_candidate(code: str, suite: Mapping[str, Any], *, timeout: float = 20.0, metric_spec: MetricSpec | None = None) -> dict[str, Any]:
    metric_spec = _metric_for_suite(suite, metric_spec)
    identity = _benchmark_identity(suite, metric_spec, code)
    result = SubprocessEvaluator(timeout=timeout).evaluate(code, suite)
    payload = result.as_dict()
    if result.valid and isinstance(result.metrics, dict):
        payload["raw_objectives"] = list(result.metrics.get("raw_objectives", []))
        payload["reference_objectives"] = list(result.metrics.get("reference_objectives", []))
        payload["bins_used"] = list(result.metrics.get("bins_used", []))
        payload["reference_kind"] = list(result.metrics.get("reference_kind", []))
    if result.valid:
        metrics = result.metrics or {}
        raw_values = metrics.get("raw_objectives")
        reference_values = metrics.get("reference_objectives")
        if not isinstance(raw_values, list) or not isinstance(reference_values, list) or len(raw_values) != len(reference_values):
            raise ValueError("metric_facts_missing")
        expected_gaps = [metric_spec.score(raw, reference) for raw, reference in zip(raw_values, reference_values)]
        if len(expected_gaps) != len(result.instance_objectives) or any(
            not math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=1e-12)
            for left, right in zip(expected_gaps, result.instance_objectives)
        ):
            raise ValueError("metric_evaluator_mismatch")
        if not math.isclose(metric_spec.aggregate(expected_gaps), float(result.objective), rel_tol=0.0, abs_tol=1e-12):
            raise ValueError("metric_aggregate_mismatch")
        payload["fitness"] = metric_spec.aggregate(expected_gaps)
    payload.update(identity)
    payload["candidate_code_sha256"] = identity["candidate_code_sha256"]
    payload["problem_spec_hash"] = identity["problem_spec_hash"]
    payload["data_manifest_hash"] = identity["data_manifest_hash"]
    payload["evaluator_hash"] = identity["evaluator_hash"]
    payload["metric_spec_hash"] = identity["metric_spec_hash"]
    payload["evaluation_identity"] = evaluation_identity(**identity)
    payload["identity"] = identity
    payload["suite_hash"] = suite.get("content_hash")
    return payload


def evaluate_selection(
    selection: FrozenSelection,
    suite: Mapping[str, Any],
    *,
    metric_spec: MetricSpec | None = None,
    timeout: float = 20.0,
) -> dict[str, Any]:
    """Evaluate a locked selection without mutating training state.

    The result keeps one row per selected member and one column per test
    instance.  Invalid members contribute ``None``; an instance with no valid
    member has no aggregate score rather than being silently dropped.
    """
    if not selection.locked:
        raise ValueError("selection_must_be_locked_before_test")
    metric = _metric_for_suite(suite, metric_spec)
    if selection.training_metric_spec_hash != metric.content_hash:
        raise ValueError("selection_metric_spec_mismatch")
    members = list(selection.members)
    instance_ids = [str(item["instance_id"]) for item in suite.get("instances", [])]
    member_results: list[dict[str, Any]] = []
    matrix = [[] for _ in instance_ids]
    for index, member in enumerate(members):
        if not isinstance(member, Mapping) or not isinstance(member.get("code"), str) or not member["code"].strip():
            raise ValueError("selection_member_code_missing")
        code_hash = sha256_text(member["code"])
        if member.get("code_sha256") != code_hash:
            raise ValueError("selection_member_code_hash_mismatch")
        result = evaluate_candidate(member["code"], suite, timeout=timeout, metric_spec=metric)
        item = {
            "member_index": index,
            "code_sha256": code_hash,
            "valid": result.get("valid") is True,
            "objective": result.get("objective"),
            "instance_objectives": list(result.get("instance_objectives") or []),
            "raw_objectives": list(result.get("raw_objectives") or []),
            "reference_objectives": list(result.get("reference_objectives") or []),
            "bins_used": list(result.get("bins_used") or []),
            "error_code": result.get("error_code"),
            "error_detail": result.get("error_detail"),
            "evaluation_identity": result.get("evaluation_identity"),
        }
        member_results.append(item)
        values = item["instance_objectives"] if item["valid"] else []
        for instance_index in range(len(instance_ids)):
            matrix[instance_index].append(values[instance_index] if instance_index < len(values) else None)
    per_instance = []
    for instance_id, values in zip(instance_ids, matrix):
        valid_values = [float(value) for value in values if value is not None and math.isfinite(float(value))]
        per_instance.append({
            "instance_id": instance_id,
            "member_gaps": values,
            "best_gap": min(valid_values) if valid_values else None,
            "valid_member_count": len(valid_values),
        })
    best_values = [item["best_gap"] for item in per_instance]
    complete = all(value is not None for value in best_values) if best_values else False
    return {
        "schema_version": "algorithm-optimization-benchmark-selection-evaluation/v1",
        "selection_kind": selection.selection_kind,
        "selection_sha256": selection.content_hash,
        "selection_locked_before_test": True,
        "test_suite_hash": suite.get("content_hash"),
        "test_data_manifest_hash": suite.get("data_manifest_hash"),
        "instance_ids": instance_ids,
        "problem_spec_hash": suite.get("problem_spec_hash"),
        "evaluator_hash": evaluator_source_hash(),
        "metric_spec_hash": metric.content_hash,
        "member_results": member_results,
        "per_instance": per_instance,
        "aggregate_fitness": metric.aggregate([float(value) for value in best_values]) if complete else None,
        "valid_member_count": sum(item["valid"] for item in member_results),
        "instance_count": len(instance_ids),
        "complete_instance_coverage": complete,
        "test_evaluation_attempts": len(member_results),
        "test_updates_training": False,
    }


def evaluate_candidate_set(
    candidates: Mapping[str, str] | list[Mapping[str, Any]],
    suite: Mapping[str, Any],
    *,
    metric_spec: MetricSpec | None = None,
    timeout: float = 20.0,
) -> dict[str, Any]:
    """Evaluate a heuristic set and aggregate the best member per instance.

    This is the offline Harness counterpart of a benchmark's set score.  It
    deliberately retains every member result (including invalid members) and
    computes the aggregate only from the per-instance minimum gap, never from
    the minimum whole-suite mean.  It does not mutate a Session, archive, or
    selection lock.
    """
    metric = _metric_for_suite(suite, metric_spec)
    if isinstance(candidates, Mapping):
        items = [{"candidate_id": str(name), "code": code} for name, code in candidates.items()]
    elif isinstance(candidates, list):
        items = [dict(item) for item in candidates]
    else:
        raise ValueError("candidate_set_invalid")
    if not items:
        raise ValueError("candidate_set_empty")
    instance_ids = [str(item["instance_id"]) for item in suite.get("instances", [])]
    member_results: list[dict[str, Any]] = []
    matrix = [[] for _ in instance_ids]
    for index, item in enumerate(items):
        if not isinstance(item, Mapping) or not isinstance(item.get("code"), str) or not item["code"].strip():
            raise ValueError("candidate_set_code_missing")
        result = evaluate_candidate(item["code"], suite, timeout=timeout, metric_spec=metric)
        member = {
            "member_index": index,
            "candidate_id": str(item.get("candidate_id") or f"candidate_{index + 1}"),
            "code_sha256": sha256_text(item["code"]),
            "valid": result.get("valid") is True,
            "objective": result.get("objective"),
            "instance_objectives": list(result.get("instance_objectives") or []),
            "raw_objectives": list(result.get("raw_objectives") or []),
            "reference_objectives": list(result.get("reference_objectives") or []),
            "error_code": result.get("error_code"),
            "error_detail": result.get("error_detail"),
            "evaluation_identity": result.get("evaluation_identity"),
        }
        member_results.append(member)
        values = member["instance_objectives"] if member["valid"] else []
        for instance_index in range(len(instance_ids)):
            matrix[instance_index].append(values[instance_index] if instance_index < len(values) else None)
    per_instance = []
    for instance_id, values in zip(instance_ids, matrix):
        valid_values = [float(value) for value in values if value is not None and math.isfinite(float(value))]
        per_instance.append({
            "instance_id": instance_id,
            "member_gaps": values,
            "best_gap": min(valid_values) if valid_values else None,
            "valid_member_count": len(valid_values),
        })
    best_values = [item["best_gap"] for item in per_instance]
    complete = bool(best_values) and all(value is not None for value in best_values)
    return {
        "schema_version": "algorithm-optimization-benchmark-candidate-set-evaluation/v1",
        "suite_hash": suite.get("content_hash"),
        "problem_spec_hash": suite.get("problem_spec_hash"),
        "data_manifest_hash": suite.get("data_manifest_hash"),
        "evaluator_hash": evaluator_source_hash(),
        "metric_spec_hash": metric.content_hash,
        "member_results": member_results,
        "instance_ids": instance_ids,
        "per_instance": per_instance,
        "aggregate_fitness": metric.aggregate([float(value) for value in best_values]) if complete else None,
        "valid_member_count": sum(item["valid"] for item in member_results),
        "instance_count": len(instance_ids),
        "complete_instance_coverage": complete,
        "evaluation_attempts": len(member_results),
    }


def budget_summary(rows: list[Mapping[str, Any]]) -> dict[str, int]:
    """Return the v1.1 dual budget view from evaluation provenance rows."""
    total = len(rows)
    seen: set[str] = set()
    novel = 0
    seeds = baseline = repairs = 0
    for row in rows:
        code_hash = str(row.get("code_sha256") or "")
        origin = str(row.get("origin") or "")
        revision = str(row.get("revision") or "")
        if origin in {"explicit_parent", "population_seed", "seed"}:
            seeds += 1
        if origin == "baseline":
            baseline += 1
        if origin == "generated_repair" or revision == "repair_1":
            repairs += 1
        elif origin == "generated" and code_hash and code_hash not in seen:
            novel += 1
            seen.add(code_hash)
    return {
        "total_evaluation_attempts": total,
        "novel_candidate_evaluations": novel,
        "seed_reevaluation_attempts": seeds,
        "baseline_attempts": baseline,
        "repair_attempts": repairs,
    }
