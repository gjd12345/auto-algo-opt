import json
from pathlib import Path

from eoh_rag.experiments.cvrp_fresh_diagnostic import (
    evaluate_instance,
    exact_sign_test_p,
    generate_instance,
    load_candidates,
    paired_summary,
    select_passing_candidate,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_exact_sign_test_and_paired_summary():
    report = paired_summary([100.0] * 10, [90.0] * 8 + [110.0] * 2)

    assert report["wins"] == 8
    assert report["losses"] == 2
    assert report["ties"] == 0
    assert report["mean_relative_improvement_pct"] == 6.0
    assert report["sign_test_p_two_sided"] == exact_sign_test_p(8, 2)


def test_generated_instances_are_reproducible_and_environment_specific():
    manifest = json.loads(
        (
            REPO_ROOT
            / "eoh_rag_workspace/experiments/manifests/cvrp_fresh_generated_diagnostic_v1.json"
        ).read_text(encoding="utf-8")
    )
    uniform = manifest["environments"][0]
    clustered = manifest["environments"][1]

    coords_a, demands_a = generate_instance(uniform, uniform["seed_start"])
    coords_b, demands_b = generate_instance(uniform, uniform["seed_start"])
    clustered_coords, _ = generate_instance(clustered, clustered["seed_start"])

    assert (coords_a == coords_b).all()
    assert (demands_a == demands_b).all()
    assert coords_a.shape == (51, 2)
    assert clustered_coords.shape == (101, 2)


def test_frozen_candidate_hashes_match_code():
    candidate_path = (
        REPO_ROOT
        / "official_eoh/examples/cvrp_construct/seeds/cvrp_agent_numeric_candidates_v1.json"
    )
    candidates = load_candidates(candidate_path)

    assert [item["candidate_id"] for item in candidates] == ["seed", "n1", "n2"]


def test_fresh_instance_evaluator_builds_feasible_route():
    environment = {
        "geometry": "uniform_square",
        "n_customers": 10,
        "capacity": 8,
        "demand_max": 3,
    }
    coords, demands = generate_instance(environment, 123)

    def nearest(current_node, depot, unvisited_nodes, rest_capacity, all_demands, distances):
        del depot, rest_capacity, all_demands
        return int(unvisited_nodes[distances[current_node][unvisited_nodes].argmin()])

    assert evaluate_instance(nearest, coords, demands, capacity=8) > 0


def test_passing_candidate_selection_uses_frozen_median_rule():
    reports = {
        "n1": {"passed": True, "overall": {"median_relative_improvement_pct": 0.2}},
        "n2": {"passed": True, "overall": {"median_relative_improvement_pct": 0.5}},
    }

    assert select_passing_candidate(reports) == "n2"
    assert select_passing_candidate({"n1": {"passed": False, "overall": {}}}) is None
