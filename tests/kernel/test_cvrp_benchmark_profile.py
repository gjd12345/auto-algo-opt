"""The frozen CVRP profile must be reachable, locked, and reference-scored."""

from pathlib import Path

import pytest

from agent_skill_loop.benchmark import catalog, harness
from agent_skill_loop.problems import cvrp

ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_ROOT = ROOT / "benchmarks" / "eohs_v1"
PROFILE = "cvrp_construct_mini"

FARTHEST_CODE = """def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    return unvisited_nodes[np.argmax(distance_matrix[current_node][unvisited_nodes])]
"""


def _suite():
    return catalog.load_profile_suite("eohs_v1", PROFILE, split="dev_train")


def test_profile_is_frozen_and_locked():
    suite = _suite()
    assert suite["problem"] == "cvrp_construct"
    assert len(suite["instances"]) == 4
    assert all(instance["reference_kind"] == "solver_reference" for instance in suite["instances"])
    with pytest.raises(ValueError, match="heldout_locked_no_access"):
        catalog.load_profile_suite("eohs_v1", PROFILE, split="test")


def test_baseline_reference_scores_zero_gap():
    suite = _suite()
    result = harness.evaluate_candidate(cvrp.BASELINE_CODE, suite)
    assert result["valid"] is True
    # The reference values are the baseline itself, so the baseline is exactly
    # on the reference point of the frozen metric.
    assert result["objective"] == pytest.approx(0.0, abs=1e-12)
    assert result["raw_objectives"] == pytest.approx(
        [instance["reference_objective"] for instance in suite["instances"]], abs=1e-12
    )


def test_worse_heuristic_scores_positive_gap():
    suite = _suite()
    result = harness.evaluate_candidate(FARTHEST_CODE, suite)
    assert result["valid"] is True
    assert result["objective"] > 0.0
    assert all(raw > reference for raw, reference in zip(result["raw_objectives"], result["reference_objectives"]))


def test_plain_suite_keeps_raw_objective():
    """Without frozen references the CVRP objective stays the raw distance."""
    from agent_skill_loop import evaluator

    suite = cvrp.build_suite(7, split="dev_train", count=2, size=12)
    result = evaluator.evaluate_candidate_request(
        {"problem": "cvrp_construct", "suite": suite, "code": cvrp.BASELINE_CODE}
    )
    assert result["valid"] is True
    assert result["objective"] > 0.0
    assert result["metrics"] is None
    assert result["instance_objectives"][0] > 0.0


def test_manifest_matches_declared_hashes():
    import hashlib
    import json

    registry = catalog.load_benchmark_registry()
    entry = next(
        item for item in registry["benchmarks"]
        if item["benchmark_id"] == "eohs_v1" and item["profile"] == PROFILE
    )
    for key, relative in (
        ("train_hash", entry["manifest_paths"]["train"]),
        ("test_hash", entry["manifest_paths"]["test"]),
        ("reference_hash", entry["manifest_paths"]["reference"]),
    ):
        raw = (BENCHMARK_ROOT / relative).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == entry["manifests"][key]
        json.loads(raw.decode("utf-8"))
