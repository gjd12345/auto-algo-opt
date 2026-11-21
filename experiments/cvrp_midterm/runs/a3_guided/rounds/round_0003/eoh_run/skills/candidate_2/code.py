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
        return depot

    cur = distance_matrix[current_node][unvisited_nodes]
    to_depot = distance_matrix[unvisited_nodes, depot]
    if current_node == depot:
        # Start with nearest-to-depot sweep: smallest radial distance wins
        return int(unvisited_nodes[np.argmin(to_depot)])

    # Angular detour: use law of cosines with distances only
    stem = distance_matrix[current_node, depot]
    a = stem
    b = to_depot
    c = cur
    denom = 2.0 * np.sqrt(np.maximum(a * b, 1e-12))
    cos_theta = np.clip((a * a + b * b - c * c) / denom, -1.0, 1.0)
    # Detour grows with (1 - cos_theta); prefer continuing the sweep
    detour = 1.0 - cos_theta
    # Reward filling the vehicle: prefer high demand relative to remaining capacity
    dem = demands[unvisited_nodes]
    fill = dem / (rest_capacity + dem + 1e-12)
    # Normalize radial distance by max in candidate set to keep scale-free
    rmax = np.max(b) + 1e-12
    radial = b / rmax

    score = 0.7 * detour + 0.6 * radial - 0.4 * fill
    return int(unvisited_nodes[np.argmin(score)])