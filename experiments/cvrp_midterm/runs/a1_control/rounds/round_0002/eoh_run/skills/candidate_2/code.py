def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction.

    Args:
        current_node:    index of the current node (0 = depot)
        depot:           index of the depot (always 0)
        unvisited_nodes: array of feasible unvisited customer indices
                         (already filtered to satisfy remaining capacity)
        rest_capacity:   remaining vehicle capacity
        demands:         demand of every node (index 0 = depot demand = 0)
        distance_matrix: pairwise Euclidean distance matrix
    Returns:
        Index of the next node to visit, or 0 to return to the depot early.
    """
    if unvisited_nodes.size == 0:
        return 0

    cur_d = distance_matrix[current_node][unvisited_nodes]
    depot_d = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes]

    # Remaining slack after serving each candidate (normalized).
    slack = np.maximum(rest_capacity - dem, 0.0)
    max_slack = rest_capacity if rest_capacity > 0 else 1.0

    # Radial term: customers farther from depot are slightly preferred early
    # (encourages filling the route outward), normalized by current distance.
    radial = depot_d / (cur_d + 1e-9)

    # Load term: prefer filling larger demand when slack allows (packing efficiency).
    load_term = dem / (rest_capacity + 1e-9)

    # Combined priority score (minimize): proximity dominates,
    # radial bias and load packing adjust the ordering.
    score = cur_d * (1.0 + 0.25 * radial) - 0.35 * load_term * cur_d + 0.15 * (max_slack - slack)

    idx = int(np.argmin(score))
    node = int(unvisited_nodes[idx])
    return node