"""Guards that every registered benchmark profile resolves to real, hash-matching bytes.

The island605_bp entry shipped with hashes computed from an earlier draft of its
manifests (commit d876c791), so ``catalog.load_profile_suite`` raised
``data_manifest_hash_mismatch`` for every caller and the profile was unreachable
even though the assets were committed.  These tests fail loudly if a registry
hash stops matching the bytes on disk, instead of letting the profile rot.
"""

import hashlib
import json
from pathlib import Path

import pytest

from agent_skill_loop.benchmark import catalog, harness
from agent_skill_loop.benchmark.contracts import MetricSpec
from agent_skill_loop.problems import bp_island605

ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_ROOT = ROOT / "benchmarks" / "eohs_v1"


def _registry_entries():
    registry = catalog.load_benchmark_registry()
    return registry["benchmarks"]


def _profile_ids():
    return [(entry["benchmark_id"], entry["profile"]) for entry in _registry_entries()]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_registry_entries_declare_existing_manifests():
    for entry in _registry_entries():
        paths = entry.get("manifest_paths")
        assert isinstance(paths, dict), f"{entry['benchmark_id']}/{entry['profile']} has no manifest_paths"
        for split, relative in paths.items():
            target = BENCHMARK_ROOT / relative
            assert target.is_file(), f"{entry['profile']}:{split} missing {relative}"
            json.loads(target.read_text(encoding="utf-8"))


def test_declared_manifest_hashes_match_committed_bytes():
    for entry in _registry_entries():
        paths = entry["manifest_paths"]
        declared = entry["manifests"]
        assert _sha256(BENCHMARK_ROOT / paths["train"]) == declared["train_hash"], (
            f"{entry['profile']}: train_hash does not match {paths['train']}"
        )
        assert _sha256(BENCHMARK_ROOT / paths["test"]) == declared["test_hash"], (
            f"{entry['profile']}: test_hash does not match {paths['test']}"
        )
        assert _sha256(BENCHMARK_ROOT / paths["reference"]) == declared["reference_hash"], (
            f"{entry['profile']}: reference_hash does not match {paths['reference']}"
        )


def test_metric_spec_hash_matches_declared_manifest():
    for entry in _registry_entries():
        metric_spec = entry["metric_spec"]
        assert MetricSpec(**metric_spec).content_hash == entry["metric_spec_hash"], (
            f"{entry['profile']}: metric_spec_hash is stale"
        )
        assert metric_spec["reference_manifest_hash"] == entry["manifests"]["reference_hash"], (
            f"{entry['profile']}: metric reference hash diverged from manifests.reference_hash"
        )


@pytest.mark.parametrize("benchmark_id,profile", _profile_ids())
def test_profile_loads_dev_train(benchmark_id, profile):
    suite = catalog.load_profile_suite(benchmark_id, profile, split="dev_train")
    assert suite["split"] == "dev_train"
    assert suite["instances"], f"{profile}: empty dev_train suite"


def test_island605_bp_is_reachable_and_locked():
    suite = catalog.load_profile_suite(
        "island605_bp", "historically_exposed_train_v1", split="dev_train"
    )
    assert suite["problem"] == "bp_online_island605"
    assert len(suite["instances"]) == 5
    assert suite["data_manifest_hash"] == _sha256(
        BENCHMARK_ROOT / "manifests" / "island605_bp_train.json"
    )
    assert suite["reference_manifest_hash"] == _sha256(
        BENCHMARK_ROOT / "manifests" / "island605_bp_references.json"
    )
    with pytest.raises(ValueError, match="heldout_locked_no_access"):
        catalog.load_profile_suite(
            "island605_bp", "historically_exposed_train_v1", split="test"
        )


def test_island605_bp_baseline_matches_reference_scale():
    suite = catalog.load_profile_suite(
        "island605_bp", "historically_exposed_train_v1", split="dev_train"
    )
    result = harness.evaluate_candidate(bp_island605.BASELINE_CODE, suite)
    assert result["valid"] is True
    assert result["objective"] == pytest.approx(0.03984304255961364, abs=1e-12)
    assert result["instance_objectives"] == pytest.approx(
        [
            0.04125163497333736,
            0.03823322265821511,
            0.039742428815776235,
            0.04074856625415032,
            0.039239360096589196,
        ],
        abs=1e-12,
    )
