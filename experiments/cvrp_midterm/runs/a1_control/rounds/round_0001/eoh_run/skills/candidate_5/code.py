def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return depot

    d_current = distance_matrix[current_node][unvisited_nodes]
    d_depot = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes]

    # Capacity-aware term: prefer nodes that use up remaining capacity
    # without disqualifying close options. Normalize by remaining capacity.
    cap = max(rest_capacity, 1e-9)
    fill = dem / cap

    # Score: mostly nearest-neighbor, plus a pull toward the depot
    # and a mild preference for demand that fills the vehicle.
    score = d_current + 0.35 * d_depot - 0.25 * (fill * d_current.mean() if d_current.size else 0.0)

    best = int(np.argmin(score))
    return int(unvisited_nodes[best])