"""CVRP Construct — 历史最优代码 (best=12.705, gen=4, pop=4)

来源: tocc_corrected, cards=[cvrp_far_first, cvrp_regret_insertion]
策略: far-first depot seeding + regret-nearest hybrid on-route
"""
import numpy as np


def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    # Phase 1: Starting a new route (current at depot) -> far-first seeding
    if current_node == depot:
        depot_dists = distance_matrix[depot, unvisited_nodes]
        return unvisited_nodes[np.argmax(depot_dists)]

    # Phase 2: On-route -> blend nearest with far-from-depot priority
    cur_dists = distance_matrix[current_node, unvisited_nodes]

    max_depot_dist = np.max(distance_matrix[depot, unvisited_nodes])
    min_cur_dist = np.min(cur_dists)
    max_cur_dist = np.max(cur_dists)

    if max_cur_dist > min_cur_dist + 1e-9:
        norm_cur = (cur_dists - min_cur_dist) / (max_cur_dist - min_cur_dist)
    else:
        norm_cur = np.zeros_like(cur_dists)

    if max_depot_dist > 1e-9:
        norm_depot = distance_matrix[depot, unvisited_nodes] / max_depot_dist
    else:
        norm_depot = np.ones_like(cur_dists)

    # Minimize: close to current AND far from depot
    scores = norm_cur - norm_depot
    best_idx = np.argmin(scores)
    return unvisited_nodes[best_idx]
