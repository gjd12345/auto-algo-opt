import json
from pathlib import Path

from eoh_rag.experiments.cvrp_environment_gate_audit import (
    classify_candidate,
    extract_candidates,
)


def test_candidate_extraction_is_deduplicated_and_reports_parse_errors(tmp_path: Path):
    code = "def select_next_node(current_node, depot, unvisited_nodes, rest_capacity, demands, distance_matrix):\n    return depot"
    (tmp_path / "valid.json").write_text(
        json.dumps([{"code": code}, {"best_code": code}]), encoding="utf-8"
    )
    (tmp_path / "broken.json").write_text("{", encoding="utf-8")

    candidates, inventory = extract_candidates(tmp_path, ["."], 1_000_000)

    assert len(candidates) == 1
    assert inventory == {"scanned_files": 2, "parse_errors": 1}


def test_environment_conflict_requires_current_gate_and_large_regression():
    reference = {
        "search_objective": 10.0,
        "confirm_objective": 10.0,
        "confirm_environment_objectives": {"a": 10.0, "b": 10.0, "c": 10.0},
    }
    candidate = {
        "search_objective": 9.8,
        "confirm_objective": 9.9,
        "confirm_environment_objectives": {"a": 9.0, "b": 9.0, "c": 11.7},
    }

    result = classify_candidate(reference, candidate, regression_limit_pct=1.0)

    assert result["current_gate_accepted"] is True
    assert result["environment_conflict"] is True
    assert result["regressed_environments"] == ["c"]
    assert result["improved_environment_count"] == 2


def test_audit_manifest_freezes_hash_sampling_and_decision_threshold():
    manifest = json.loads(
        Path(
            "eoh_rag_workspace/experiments/manifests/cvrp_environment_gate_audit_v1.json"
        ).read_text(encoding="utf-8")
    )

    assert manifest["sample_size"] == 60
    assert manifest["selection_contract"]["sample_order"] == "ascending_code_sha256"
    assert manifest["environment_regression_limit_pct"] == 1.0
    assert manifest["conflict_rate_trigger"] == 0.2
    assert manifest["selection_contract"]["held_out_used"] is False
