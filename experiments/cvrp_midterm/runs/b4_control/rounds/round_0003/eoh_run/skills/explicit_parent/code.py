def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes].astype(float)

    cap = float(rest_capacity)
    if cap <= 0.0:
        return depot

    load_after = (cap - dem) / cap

    # Explore a different distance/load combination:
    # prioritize near customers, slightly prefer those farther from depot,
    # and softly favor customers whose removal leaves a balanced residual load.
    score = d_cur - 0.15 * d_dep - 0.35 * d_cur * np.abs(load_after - 0.5)
    return int(unvisited_nodes[np.argmin(score)])