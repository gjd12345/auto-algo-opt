def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes]

    cap = max(rest_capacity, 1e-9)
    fill = dem / cap

    score = d_cur + 0.30 * d_dep - 0.25 * d_cur * fill + 0.10 * d_dep * fill
    return int(unvisited_nodes[np.argmin(score)])