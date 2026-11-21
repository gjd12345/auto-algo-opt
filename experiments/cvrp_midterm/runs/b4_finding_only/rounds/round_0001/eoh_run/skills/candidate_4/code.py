def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return depot

    cur = distance_matrix[current_node]
    dep = distance_matrix[depot]

    # Extra distance incurred by inserting the customer on the current leg
    # instead of heading straight back to the depot.
    detour = cur[unvisited_nodes] + dep[unvisited_nodes] - cur[depot]

    # Relative demand pressure: prefer low-demand customers now so that
    # heavy customers are pushed to fresh (full-capacity) loads.
    dem = demands[unvisited_nodes]
    total_dem = float(np.sum(dem)) if np.sum(dem) > 0 else 1.0
    load_frac = dem / total_dem

    # Normalised detour so absolute scale does not dominate.
    scale = float(np.max(detour)) if np.max(detour) > 0 else 1.0
    score = detour / scale + load_frac

    return int(unvisited_nodes[np.argmin(score)])