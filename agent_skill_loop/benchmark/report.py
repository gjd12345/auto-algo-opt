"""Small deterministic report payload builder; human rendering is downstream."""

from __future__ import annotations

import math
from typing import Any, Mapping

from .catalog import benchmark_for_spec_hash, load_profile_suite
from .contracts import ExperimentManifest, FrozenSelection, sha256_json


def _finite_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{name}_must_be_finite_number")
    return float(value)


def _validate_training_facts(manifest: ExperimentManifest, metrics: Mapping[str, Any], budget: Mapping[str, Any], selection: FrozenSelection) -> None:
    """Reject a report made from untyped or cross-run training facts."""
    _finite_number(metrics.get("best_training_fitness"), "best_training_fitness")
    total = budget.get("total_evaluation_attempts")
    if isinstance(total, bool) or not isinstance(total, int) or total < 0:
        raise ValueError("total_evaluation_attempts_invalid")
    if total > manifest.evaluation_budget:
        raise ValueError("evaluation_budget_exceeded")
    for name in (
        "novel_candidate_evaluations", "seed_reevaluation_attempts",
        "baseline_attempts", "repair_attempts",
    ):
        if name not in budget:
            raise ValueError(f"{name}_missing")
        value = budget[name]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > total:
            raise ValueError(f"{name}_invalid")
    if metrics.get("selection_kind") is not None and metrics.get("selection_kind") != selection.selection_kind:
        raise ValueError("metrics_selection_kind_mismatch")


def _validate_test_facts(test_result: Mapping[str, Any], selection: FrozenSelection) -> None:
    """Validate the evidence shape emitted by ``evaluate_selection``.

    A caller cannot turn a locked selection into a test claim by supplying only
    ``test_updates_training: false``; the member and per-instance evidence
    matrix must also be present and internally consistent.
    """
    if test_result.get("selection_locked_before_test") is not True:
        raise ValueError("test_selection_lock_missing")
    member_results = test_result.get("member_results")
    per_instance = test_result.get("per_instance")
    if not isinstance(member_results, list) or len(member_results) != len(selection.members):
        raise ValueError("test_member_results_invalid")
    instance_ids = test_result.get("instance_ids")
    if not isinstance(per_instance, list) or not per_instance:
        raise ValueError("test_instance_matrix_invalid")
    if not isinstance(instance_ids, list) or len(instance_ids) != len(per_instance):
        raise ValueError("test_instance_matrix_invalid")
    if test_result.get("instance_count") != len(instance_ids):
        raise ValueError("test_instance_count_mismatch")
    member_values: list[list[float | None]] = []
    for index, member in enumerate(member_results):
        if not isinstance(member, Mapping):
            raise ValueError("test_member_result_invalid")
        selected = selection.members[index]
        if member.get("code_sha256") != selected.get("code_sha256"):
            raise ValueError("test_member_identity_mismatch")
        values = member.get("instance_objectives")
        if member.get("valid") is True:
            if not isinstance(values, list) or len(values) != len(per_instance):
                raise ValueError("test_member_scores_invalid")
        elif values in (None, []):
            values = [None] * len(per_instance)
        elif not isinstance(values, list) or len(values) != len(per_instance):
            raise ValueError("test_member_scores_invalid")
        normalized_values: list[float | None] = []
        for value in values:
            if value is None:
                normalized_values.append(None)
            elif isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                raise ValueError("test_member_scores_invalid")
            else:
                normalized_values.append(float(value))
        member_values.append(normalized_values)
    for instance_index, item in enumerate(per_instance):
        if not isinstance(item, Mapping) or not isinstance(item.get("member_gaps"), list) or len(item["member_gaps"]) != len(selection.members):
            raise ValueError("test_instance_matrix_invalid")
        values = item["member_gaps"]
        raw_valid_values = [value for value in values if value is not None]
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) for value in raw_valid_values):
            raise ValueError("test_instance_matrix_invalid")
        valid_values = [float(value) for value in raw_valid_values]
        if item.get("instance_id") != instance_ids[instance_index]:
            raise ValueError("test_instance_identity_mismatch")
        expected_values = [member_values[member_index][instance_index] for member_index in range(len(member_values))]
        for actual_value, expected_value in zip(values, expected_values):
            if actual_value is None or expected_value is None:
                if actual_value is not None or expected_value is not None:
                    raise ValueError("test_member_matrix_mismatch")
            elif not math.isclose(float(actual_value), float(expected_value), rel_tol=0.0, abs_tol=1e-12):
                raise ValueError("test_member_matrix_mismatch")
        expected_best = min(valid_values) if valid_values else None
        actual_best = item.get("best_gap")
        if actual_best is not None and (
            isinstance(actual_best, bool)
            or not isinstance(actual_best, (int, float))
            or not math.isfinite(float(actual_best))
        ):
            raise ValueError("test_instance_best_mismatch")
        if actual_best != expected_best and not (
            actual_best is not None and expected_best is not None
            and math.isclose(float(actual_best), expected_best, rel_tol=0.0, abs_tol=1e-12)
        ):
            raise ValueError("test_instance_best_mismatch")
        if item.get("valid_member_count") != len(valid_values):
            raise ValueError("test_instance_valid_count_mismatch")
    best_values = [item.get("best_gap") for item in per_instance]
    complete = all(value is not None for value in best_values)
    if test_result.get("complete_instance_coverage") is not complete:
        raise ValueError("test_coverage_mismatch")
    expected_aggregate = (sum(float(value) for value in best_values) / len(best_values)) if complete else None
    actual_aggregate = test_result.get("aggregate_fitness")
    if expected_aggregate is None:
        if actual_aggregate is not None:
            raise ValueError("test_aggregate_mismatch")
    elif actual_aggregate is None or not math.isclose(float(actual_aggregate), expected_aggregate, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError("test_aggregate_mismatch")
    if test_result.get("valid_member_count") != sum(item.get("valid") is True for item in member_results):
        raise ValueError("test_valid_member_count_mismatch")
    if test_result.get("test_evaluation_attempts") != len(member_results):
        raise ValueError("test_attempt_count_mismatch")


def build_report(*, manifest: ExperimentManifest, selection: FrozenSelection,
                 metrics: Mapping[str, Any], budget: Mapping[str, Any], source: str = "artifact_reevaluated",
                 test_result: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if source not in {"published_reported", "artifact_reevaluated", "search_rerun"}:
        raise ValueError("invalid_result_source")
    if not isinstance(metrics, Mapping) or not isinstance(budget, Mapping):
        raise ValueError("benchmark_report_payload_invalid")
    if not selection.locked:
        raise ValueError("selection_must_be_locked_for_report")
    if selection.training_metric_spec_hash != manifest.metric_spec_hash:
        raise ValueError("selection_metric_spec_mismatch")
    for name, payload in (("metrics", metrics), ("budget", budget)):
        if payload.get("experiment_manifest_sha256") != manifest.content_hash:
            raise ValueError(f"{name}_manifest_identity_mismatch")
        if payload.get("selection_sha256") != selection.content_hash:
            raise ValueError(f"{name}_selection_identity_mismatch")
    if metrics.get("metric_spec_hash") != manifest.metric_spec_hash:
        raise ValueError("metrics_metric_spec_mismatch")
    _validate_training_facts(manifest, metrics, budget, selection)
    if test_result is None:
        test_isolation = {
            "selection_locked_before_test": True,
            "test_evaluated": False,
            "test_updates_training": None,
            "status": "training_only",
        }
    else:
        if not isinstance(test_result, Mapping):
            raise ValueError("test_result_invalid")
        if not selection.locked or test_result.get("selection_sha256") != selection.content_hash:
            raise ValueError("test_selection_lock_mismatch")
        if test_result.get("test_updates_training") is not False:
            raise ValueError("test_training_isolation_failed")
        if test_result.get("metric_spec_hash") != manifest.metric_spec_hash:
            raise ValueError("test_metric_spec_mismatch")
        if test_result.get("selection_kind") is not None and test_result.get("selection_kind") != selection.selection_kind:
            raise ValueError("test_selection_kind_mismatch")
        try:
            benchmark, _metric, _item = benchmark_for_spec_hash(manifest.benchmark_spec_hash)
            expected_heldout = load_profile_suite(benchmark.benchmark_id, benchmark.profile, split="heldout")
        except ValueError as exc:
            raise ValueError("test_benchmark_not_registered") from exc
        expected_test_identity = {
            "test_benchmark_id": benchmark.benchmark_id,
            "test_profile": benchmark.profile,
            "test_split": "heldout",
            "test_benchmark_spec_hash": benchmark.content_hash,
            "test_suite_hash": expected_heldout["content_hash"],
            "test_data_manifest_hash": benchmark.test_manifest_hash,
            "test_reference_manifest_hash": benchmark.reference_manifest_hash,
            "problem_spec_hash": expected_heldout["problem_spec_hash"],
        }
        for name, expected in expected_test_identity.items():
            actual_name = name if name != "problem_spec_hash" else "test_problem_spec_hash"
            if test_result.get(actual_name) != expected:
                raise ValueError(f"{actual_name}_mismatch")
        if test_result.get("instance_ids") != [item["instance_id"] for item in expected_heldout["instances"]]:
            raise ValueError("test_instance_identity_mismatch")
        if test_result.get("test_data_manifest_hash") != benchmark.test_manifest_hash:
            raise ValueError("test_data_manifest_hash_mismatch")
        _validate_test_facts(test_result, selection)
        test_isolation = {
            "selection_locked_before_test": True,
            "selection_sha256": selection.content_hash,
            "test_result_sha256": sha256_json(test_result),
            "test_evaluated": True,
            "test_updates_training": False,
            "status": "verified",
        }
    return {
        "schema_version": "algorithm-optimization-benchmark-report/v1",
        "experiment_manifest_sha256": manifest.content_hash,
        "selection_kind": selection.selection_kind,
        "selection_sha256": selection.content_hash,
        "result_source": source,
        "metrics": dict(metrics),
        "budget": dict(budget),
        "test_isolation": test_isolation,
        "test": dict(test_result) if test_result is not None else None,
    }
