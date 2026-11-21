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

    # Normalized load usage: how much of remaining capacity this customer consumes.
    load_ratio = dem / (rest_capacity + 1e-9)
    # Penalize customers that are far from depot relative to current node distance,
    # and mildly discourage high-demand picks to preserve capacity for clustering.
    score = cur_d + 0.35 * depot_d + 0.5 * load_ratio * depot_d - 0.2 * load_ratio

    idx = int(np.argmin(score))
    return int(unvisited_nodes[idx])