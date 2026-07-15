import json
from pathlib import Path

from eoh_rag.experiments.cvrp_core_final_report import (
    file_sha256,
    load_candidates,
    load_core_instances,
    summarize_pairs,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_final_report_manifest_freezes_registry_candidates_and_timeout():
    manifest = json.loads(
        (
            REPO_ROOT
            / "eoh_rag_workspace/experiments/manifests/cvrp_core_final_report_v1.json"
        ).read_text(encoding="utf-8")
    )

    assert file_sha256(REPO_ROOT / manifest["registry_file"]) == manifest["registry_sha256"]
    assert file_sha256(REPO_ROOT / manifest["candidate_file"]) == manifest["candidate_file_sha256"]
    assert manifest["candidate_ids"] == ["seed", "n2"]
    assert manifest["coordinate_timeout_seconds"] == 240
    assert manifest["report_contract"]["held_out_controls_selection"] is False


def test_final_report_loads_all_ten_cvrp_core_instances_and_two_candidates():
    manifest = json.loads(
        (
            REPO_ROOT
            / "eoh_rag_workspace/experiments/manifests/cvrp_core_final_report_v1.json"
        ).read_text(encoding="utf-8")
    )
    instances = load_core_instances(REPO_ROOT / manifest["registry_file"], REPO_ROOT)
    candidates = load_candidates(REPO_ROOT / manifest["candidate_file"], manifest["candidate_ids"])

    assert len(instances) == 10
    assert instances[0]["instance"] == "X-n101-k25"
    assert instances[-1]["instance"] == "X-n1001-k43"
    assert set(candidates) == {"seed", "n2"}


def test_paired_summary_keeps_only_successful_strict_pairs():
    rows = [
        {"candidate_id": "seed", "instance": "a", "ok": True, "route_cost": 100.0},
        {"candidate_id": "n2", "instance": "a", "ok": True, "route_cost": 90.0},
        {"candidate_id": "seed", "instance": "b", "ok": True, "route_cost": 100.0},
        {"candidate_id": "n2", "instance": "b", "ok": False},
    ]

    report = summarize_pairs(rows, "seed", "n2")

    assert report["paired_instances"] == 1
    assert report["wins"] == 1
    assert report["losses"] == 0
    assert report["median_relative_improvement_pct"] == 10.0
