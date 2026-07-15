import importlib.util
import json
from pathlib import Path
import sys

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_problem_module(problem: str):
    """按文件路径隔离加载两个同名 prob_broad 模块，避免测试间模块缓存串扰。"""
    path = REPO_ROOT / "official_eoh" / "examples" / problem / "prob_broad.py"
    # 三个旧问题都把 get_instance 暴露为顶层模块名；测试进程连续加载时必须清掉旧缓存。
    sys.modules.pop("get_instance", None)
    spec = importlib.util.spec_from_file_location(f"_{problem}_prob_broad_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_tsp_broad_returns_independent_confirmation_feedback():
    module = load_problem_module("tsp_construct")
    problem = module.TSPCONSTBroad(
        problem_size=8,
        n_train=2,
        confirmation_feedback=True,
        n_confirm=3,
    )

    def nearest_neighbor(current_node, destination_node, unvisited_nodes, distance_matrix):
        del destination_node
        return int(unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])])

    result = problem.evaluate_program("", nearest_neighbor)

    assert isinstance(result, dict)
    assert result["objective"] > 0
    assert result["feedback"]["confirm_objective"] > 0
    assert result["feedback"]["search_confirm_gap"] == (
        result["feedback"]["confirm_objective"] - result["objective"]
    )
    assert len(problem.instance_data) == 2
    assert len(problem.confirmation_data) == 3
    assert problem.instance_data[0][0] != problem.confirmation_data[0][0]


def test_cvrp_broad_returns_independent_confirmation_feedback():
    module = load_problem_module("cvrp_construct")
    problem = module.CVRPCONSTBroad(
        n_customers=8,
        capacity=10,
        n_train=2,
        confirmation_feedback=True,
        n_confirm=3,
    )

    def nearest_feasible(current_node, depot, unvisited_nodes, rest_capacity, demands, distance_matrix):
        del depot, rest_capacity, demands
        return int(unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])])

    result = problem.evaluate_program("", nearest_feasible)

    assert isinstance(result, dict)
    assert result["objective"] > 0
    assert result["feedback"]["confirm_objective"] > 0
    assert result["feedback"]["search_confirm_gap"] == (
        result["feedback"]["confirm_objective"] - result["objective"]
    )
    assert len(problem.instance_data) == 2
    assert len(problem.confirmation_data) == 3
    assert not np.array_equal(problem.instance_data[0][0], problem.confirmation_data[0][0])


def test_confirmation_feedback_is_opt_in_for_construct_problems():
    tsp_module = load_problem_module("tsp_construct")
    cvrp_module = load_problem_module("cvrp_construct")

    tsp_problem = tsp_module.TSPCONSTBroad(problem_size=8, n_train=1)
    cvrp_problem = cvrp_module.CVRPCONSTBroad(n_customers=8, capacity=10, n_train=1)

    def tsp_nearest(current_node, destination_node, unvisited_nodes, distance_matrix):
        del destination_node
        return int(unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])])

    def cvrp_nearest(current_node, depot, unvisited_nodes, rest_capacity, demands, distance_matrix):
        del depot, rest_capacity, demands
        return int(unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])])

    assert isinstance(tsp_problem.evaluate_program("", tsp_nearest), float)
    assert isinstance(cvrp_problem.evaluate_program("", cvrp_nearest), float)
    assert tsp_problem.confirmation_data == []
    assert cvrp_problem.confirmation_data == []


def test_cvrp_portability_manifest_freezes_feedback_and_provenance_contracts():
    manifest_path = (
        REPO_ROOT
        / "eoh_rag_workspace"
        / "experiments"
        / "manifests"
        / "cvrp_confirmation_portability_proxy_v1.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    seed_path = REPO_ROOT / manifest["arms"][0]["seed_codes"]
    seeds = json.loads(seed_path.read_text(encoding="utf-8"))

    assert [arm["operators"] for arm in manifest["arms"]] == ["n1", "n2"]
    assert all(arm["evolution_feedback_policy"] == "confirmation_gate_only" for arm in manifest["arms"])
    assert manifest["discovery_contract"]["held_out_controls_selection"] is False
    assert manifest["discovery_contract"]["held_out_is_reused_diagnostic"] is True
    assert seeds[0]["provenance"]["actor"] == "research_agent_eoh"
    assert seeds[0]["provenance"]["selection_used_held_out"] is False
