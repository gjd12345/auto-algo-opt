"""Small, inspectable benchmark registry used by the v1.1+ CLI and Session.

Preserves benchmarks/eohs_v1/registry.json byte-for-byte while supporting
additional versioned registries (such as benchmarks/cvrp_workbench/registry.json)
with independent selection split identities and CVRP protocol metadata.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

from .contracts import BenchmarkSpec, MetricSpec, sha256_json


_ROOT = Path(__file__).resolve().parents[2]
_REGISTRY = _ROOT / "benchmarks" / "eohs_v1" / "registry.json"
_EXTENSION_REGISTRIES: tuple[Path, ...] = (
    _ROOT / "benchmarks" / "cvrp_workbench" / "registry.json",
)


def load_benchmark_registry(path: Path | None = None, *, include_extensions: bool = False) -> dict[str, Any]:
    """Load a benchmark registry JSON.

    Default behavior (path=None, include_extensions=False) returns the frozen
    benchmarks/eohs_v1/registry.json unchanged for legacy callers and tests.
    """
    target = Path(path) if path is not None else _REGISTRY
    payload = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("benchmarks"), list):
        raise ValueError("benchmark_registry_invalid")
    if path is None and include_extensions:
        combined = list(payload["benchmarks"])
        for ext_path in _EXTENSION_REGISTRIES:
            if ext_path.is_file():
                ext_payload = json.loads(ext_path.read_text(encoding="utf-8"))
                if not isinstance(ext_payload, dict) or not isinstance(ext_payload.get("benchmarks"), list):
                    raise ValueError("benchmark_registry_invalid")
                combined.extend(ext_payload["benchmarks"])
        return {**payload, "benchmarks": combined}
    return payload


def load_all_benchmark_registries() -> list[tuple[Path, dict[str, Any]]]:
    """Return every active registry file together with its parsed payload."""
    registries: list[tuple[Path, dict[str, Any]]] = [(_REGISTRY.parent, load_benchmark_registry(_REGISTRY))]
    for ext_path in _EXTENSION_REGISTRIES:
        if ext_path.is_file():
            registries.append((ext_path.parent, load_benchmark_registry(ext_path)))
    return registries


def list_benchmark_profiles(*, include_extensions: bool = True) -> list[dict[str, Any]]:
    """List registered benchmark profile descriptors across active registries."""
    rows: list[dict[str, Any]] = []
    sources = load_all_benchmark_registries() if include_extensions else [(_REGISTRY.parent, load_benchmark_registry(_REGISTRY))]
    for base_dir, registry in sources:
        for item in registry["benchmarks"]:
            if isinstance(item, dict):
                rows.append({**item, "_registry_base": base_dir.relative_to(_ROOT).as_posix()})
    return rows


def _find_profile_entry(benchmark_id: str, profile: str) -> tuple[Path, dict[str, Any]]:
    for base_dir, registry in load_all_benchmark_registries():
        for item in registry["benchmarks"]:
            if isinstance(item, dict) and item.get("benchmark_id") == benchmark_id and item.get("profile") == profile:
                return base_dir, item
    raise ValueError("benchmark_profile_not_found")


def _build_benchmark_and_metric(item: dict[str, Any]) -> tuple[BenchmarkSpec, MetricSpec]:
    metric_data = item.get("metric_spec")
    if not isinstance(metric_data, dict):
        raise ValueError("metric_spec_missing")
    metric = MetricSpec(**metric_data)
    expected_metric_hash = item.get("metric_spec_hash")
    if expected_metric_hash != metric.content_hash:
        raise ValueError("metric_spec_hash_mismatch")
    manifests = item.get("manifests")
    if not isinstance(manifests, dict):
        raise ValueError("benchmark_manifests_missing")
    benchmark = BenchmarkSpec(
        benchmark_id=str(item["benchmark_id"]),
        profile=str(item["profile"]),
        problem_id=str(item["problem_id"]),
        upstream_repo=str(item.get("upstream_repo", "")),
        upstream_commit=str(item.get("upstream_commit", "")),
        train_manifest_hash=str(manifests["train_hash"]),
        test_manifest_hash=str(manifests["test_hash"]),
        reference_manifest_hash=str(manifests["reference_hash"]),
        metric_spec_hash=metric.content_hash,
        asset_status=str(item.get("asset_status", "regenerated_protocol_compatible")),
        upstream_code_profile=str(item.get("upstream_code_profile", "upstream_code")),
        paper_protocol_profile=str(item.get("paper_protocol_profile", "paper_protocol")),
        deviations=tuple(str(x) for x in item.get("deviations", [])),
        selection_manifest_hash=manifests.get("selection_hash"),
        suite_role=item.get("suite_role"),
        exposure_status=item.get("exposure_status"),
        distance_convention=item.get("distance_convention"),
        vehicle_limit_policy=item.get("vehicle_limit_policy"),
        problem_family=item.get("problem_family"),
        benchmark_tier=item.get("benchmark_tier"),
        published_results_path=item.get("published_results_path"),
        published_results_hash=item.get("published_results_hash"),
    )
    return benchmark, metric


def benchmark_profile(benchmark_id: str = "eohs_v1", profile: str = "obp_mini") -> tuple[BenchmarkSpec, MetricSpec, dict[str, Any]]:
    _base_dir, item = _find_profile_entry(benchmark_id, profile)
    benchmark, metric = _build_benchmark_and_metric(item)
    return benchmark, metric, item


def benchmark_for_spec_hash(benchmark_spec_hash: str) -> tuple[BenchmarkSpec, MetricSpec, dict[str, Any]]:
    """Resolve a registered benchmark identity without trusting a report label."""
    if not isinstance(benchmark_spec_hash, str) or len(benchmark_spec_hash) != 64:
        raise ValueError("benchmark_spec_hash_invalid")
    for _base_dir, registry in load_all_benchmark_registries():
        for item in registry["benchmarks"]:
            if not isinstance(item, dict):
                continue
            benchmark_id = item.get("benchmark_id")
            profile = item.get("profile")
            if not isinstance(benchmark_id, str) or not isinstance(profile, str):
                continue
            benchmark, metric, normalized = benchmark_profile(benchmark_id, profile)
            if benchmark.content_hash == benchmark_spec_hash:
                return benchmark, metric, normalized
    raise ValueError("benchmark_spec_hash_not_registered")


def _reference_values_match(actual: Any, expected: Any) -> bool:
    if actual == expected:
        return True
    if (
        isinstance(actual, (int, float))
        and not isinstance(actual, bool)
        and isinstance(expected, (int, float))
        and not isinstance(expected, bool)
    ):
        return math.isclose(float(actual), float(expected), rel_tol=1e-12, abs_tol=1e-12)
    return False


def load_profile_suite(benchmark_id: str = "eohs_v1", profile: str = "obp_mini", *, split: str = "dev_train") -> dict[str, Any]:
    """Load a frozen benchmark manifest and attach its deterministic suite hash."""
    base_dir, item = _find_profile_entry(benchmark_id, profile)
    benchmark, metric = _build_benchmark_and_metric(item)
    if split not in {"train", "dev_train", "selection"} and item.get("heldout_policy") == "locked_no_access_diagnostic":
        raise ValueError("heldout_locked_no_access")
    paths = item.get("manifest_paths")
    if not isinstance(paths, dict) or split not in paths:
        raise ValueError("benchmark_split_not_found")
    target = base_dir / str(paths[split])
    if split in {"train", "dev_train"}:
        expected_data_hash = benchmark.train_manifest_hash
        result_split = "dev_train"
    elif split == "selection":
        if benchmark.selection_manifest_hash is None:
            raise ValueError("selection_manifest_hash_missing")
        expected_data_hash = benchmark.selection_manifest_hash
        result_split = "selection"
    else:
        expected_data_hash = benchmark.test_manifest_hash
        result_split = "heldout" if split == "test" else split
    if hashlib.sha256(target.read_bytes()).hexdigest() != expected_data_hash:
        raise ValueError("data_manifest_hash_mismatch")
    payload = json.loads(target.read_text(encoding="utf-8"))
    instances = payload.get("instances") if isinstance(payload, dict) else None
    if not isinstance(instances, list) or not instances:
        raise ValueError("benchmark_manifest_invalid")
    reference_path = paths.get("reference")
    if not isinstance(reference_path, str):
        raise ValueError("reference_manifest_missing")
    reference_file = base_dir / reference_path
    reference_payload = json.loads(reference_file.read_text(encoding="utf-8"))
    if hashlib.sha256(reference_file.read_bytes()).hexdigest() != benchmark.reference_manifest_hash:
        raise ValueError("reference_manifest_hash_mismatch")
    if not isinstance(reference_payload, dict) or not isinstance(reference_payload.get("instances"), dict):
        raise ValueError("reference_manifest_invalid")
    reference_values = reference_payload["instances"]
    for instance in instances:
        instance_id = instance.get("instance_id") if isinstance(instance, dict) else None
        if (
            instance_id not in reference_values
            or not _reference_values_match(instance.get("reference_objective"), reference_values[instance_id])
            or instance.get("reference_kind") != metric.reference_kind
        ):
            raise ValueError("reference_manifest_mismatch")
    result: dict[str, Any] = {
        "benchmark_id": benchmark.benchmark_id,
        "profile": benchmark.profile,
        "problem": benchmark.problem_id,
        "split": result_split,
        "instances": instances,
        "benchmark_spec_hash": benchmark.content_hash,
        "metric_spec_hash": benchmark.metric_spec_hash,
        "data_manifest_hash": expected_data_hash,
        "reference_manifest_hash": benchmark.reference_manifest_hash,
    }
    if benchmark.selection_manifest_hash is not None:
        result["selection_manifest_hash"] = benchmark.selection_manifest_hash
    if benchmark.suite_role is not None:
        result["suite_role"] = benchmark.suite_role
    if benchmark.exposure_status is not None:
        result["exposure_status"] = benchmark.exposure_status
    if benchmark.distance_convention is not None:
        result["distance_convention"] = benchmark.distance_convention
    if benchmark.vehicle_limit_policy is not None:
        result["vehicle_limit_policy"] = benchmark.vehicle_limit_policy
    if benchmark.problem_family is not None:
        result["problem_family"] = benchmark.problem_family
    if benchmark.benchmark_tier is not None:
        result["benchmark_tier"] = benchmark.benchmark_tier
    if benchmark.published_results_path is not None:
        pub_file = base_dir / benchmark.published_results_path
        if benchmark.published_results_hash is not None:
            if not pub_file.is_file() or hashlib.sha256(pub_file.read_bytes()).hexdigest() != benchmark.published_results_hash:
                raise ValueError("published_results_hash_mismatch")
        result["published_results_path"] = benchmark.published_results_path
        if benchmark.published_results_hash is not None:
            result["published_results_hash"] = benchmark.published_results_hash
    if isinstance(payload.get("scale_stress_instances"), list):
        result["scale_stress_instances"] = payload["scale_stress_instances"]
    if isinstance(payload.get("metadata"), dict):
        result["metadata"] = payload["metadata"]
    from agent_skill_loop.problems.base import get_problem
    result["problem_spec_hash"] = get_problem(benchmark.problem_id).content_hash
    # The OBP ProblemSpec uses this exact canonical suite hash.
    from agent_skill_loop.problems.obp import suite_hash
    result["content_hash"] = suite_hash(benchmark.problem_id, result["split"], instances)
    return result
