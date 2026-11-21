def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes].astype(float)

    cap = max(rest_capacity, 1e-9)
    fill = dem / cap

    # Different weighting: stronger pull toward far-from-depot customers,
    # heavier penalty on detour, and stronger fill-based packing incentive.
    scores = d_cur - 0.9 * d_dep - 0.45 * fill * d_cur + 0.15 * fill * d_dep

    return int(unvisited_nodes[np.argmin(scores)])