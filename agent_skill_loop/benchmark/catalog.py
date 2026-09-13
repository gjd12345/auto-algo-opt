"""Small, inspectable benchmark registry used by the v1.1 CLI and Session."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .contracts import BenchmarkSpec, MetricSpec, sha256_json


_ROOT = Path(__file__).resolve().parents[2]
_REGISTRY = _ROOT / "benchmarks" / "eohs_v1" / "registry.json"


def load_benchmark_registry(path: Path | None = None) -> dict[str, Any]:
    target = Path(path) if path is not None else _REGISTRY
    payload = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("benchmarks"), list):
        raise ValueError("benchmark_registry_invalid")
    return payload


def benchmark_profile(benchmark_id: str = "eohs_v1", profile: str = "obp_mini") -> tuple[BenchmarkSpec, MetricSpec, dict[str, Any]]:
    registry = load_benchmark_registry()
    item = next((x for x in registry["benchmarks"] if x.get("benchmark_id") == benchmark_id and x.get("profile") == profile), None)
    if not isinstance(item, dict):
        raise ValueError("benchmark_profile_not_found")
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
        benchmark_id=benchmark_id,
        profile=profile,
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
    )
    return benchmark, metric, item


def benchmark_for_spec_hash(benchmark_spec_hash: str) -> tuple[BenchmarkSpec, MetricSpec, dict[str, Any]]:
    """Resolve a registered benchmark identity without trusting a report label."""
    if not isinstance(benchmark_spec_hash, str) or len(benchmark_spec_hash) != 64:
        raise ValueError("benchmark_spec_hash_invalid")
    for item in load_benchmark_registry()["benchmarks"]:
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


def load_profile_suite(benchmark_id: str = "eohs_v1", profile: str = "obp_mini", *, split: str = "dev_train") -> dict[str, Any]:
    """Load a frozen benchmark manifest and attach its deterministic suite hash."""
    benchmark, metric, item = benchmark_profile(benchmark_id, profile)
    paths = item.get("manifest_paths")
    if not isinstance(paths, dict) or split not in paths:
        raise ValueError("benchmark_split_not_found")
    target = _ROOT / "benchmarks" / "eohs_v1" / str(paths[split])
    expected_data_hash = (
        benchmark.train_manifest_hash
        if split in {"train", "dev_train"}
        else benchmark.test_manifest_hash
    )
    if hashlib.sha256(target.read_bytes()).hexdigest() != expected_data_hash:
        raise ValueError("data_manifest_hash_mismatch")
    payload = json.loads(target.read_text(encoding="utf-8"))
    instances = payload.get("instances") if isinstance(payload, dict) else None
    if not isinstance(instances, list) or not instances:
        raise ValueError("benchmark_manifest_invalid")
    reference_path = paths.get("reference")
    if not isinstance(reference_path, str):
        raise ValueError("reference_manifest_missing")
    reference_file = _ROOT / "benchmarks" / "eohs_v1" / reference_path
    reference_payload = json.loads(reference_file.read_text(encoding="utf-8"))
    if hashlib.sha256(reference_file.read_bytes()).hexdigest() != benchmark.reference_manifest_hash:
        raise ValueError("reference_manifest_hash_mismatch")
    if not isinstance(reference_payload, dict) or not isinstance(reference_payload.get("instances"), dict):
        raise ValueError("reference_manifest_invalid")
    reference_values = reference_payload["instances"]
    for instance in instances:
        instance_id = instance.get("instance_id") if isinstance(instance, dict) else None
        if (instance_id not in reference_values
                or instance.get("reference_objective") != reference_values[instance_id]
                or instance.get("reference_kind") != metric.reference_kind):
            raise ValueError("reference_manifest_mismatch")
    result_split = "dev_train" if split in {"train", "dev_train"} else "heldout" if split == "test" else split
    result = {"benchmark_id": benchmark.benchmark_id, "profile": benchmark.profile,
              "problem": benchmark.problem_id, "split": result_split, "instances": instances,
              "benchmark_spec_hash": benchmark.content_hash,
              "metric_spec_hash": benchmark.metric_spec_hash,
              "data_manifest_hash": benchmark.train_manifest_hash if result_split == "dev_train" else benchmark.test_manifest_hash,
              "reference_manifest_hash": benchmark.reference_manifest_hash}
    from agent_skill_loop.problems.base import get_problem
    result["problem_spec_hash"] = get_problem(benchmark.problem_id).content_hash
    # The OBP ProblemSpec uses this exact canonical suite hash.
    from agent_skill_loop.problems.obp import suite_hash
    result["content_hash"] = suite_hash(benchmark.problem_id, result["split"], instances)
    return result
