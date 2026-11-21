def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return int(depot)

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes].astype(float)

    savings = d_cur - 0.6 * d_dep

    safe_cap = rest_capacity if rest_capacity > 0 else 1.0
    fill = dem / safe_cap

    denom = d_cur + d_dep + 1e-9
    align = d_dep / denom

    scale = float(np.max(np.abs(savings))) + 1e-9
    utility = -(savings / scale) + 0.35 * fill + 0.15 * align

    return int(unvisited_nodes[int(np.argmax(utility))])