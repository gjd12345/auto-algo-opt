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

    max_cur = float(np.max(cur_d)) if cur_d.size > 0 else 0.0
    max_depot = float(np.max(depot_d)) if depot_d.size > 0 else 0.0
    denom_cur = max_cur if max_cur > 1e-9 else 1.0
    denom_depot = max_depot if max_depot > 1e-9 else 1.0
    denom_cap = rest_capacity if rest_capacity > 1e-9 else 1.0

    # Normalized proximity term (smaller = closer).
    prox = cur_d / denom_cur
    # Radial term: prefer far-from-depot nodes early to fill routes outward.
    radial = depot_d / denom_depot
    # Load term: prefer larger demand to improve packing.
    load_term = dem / denom_cap
    # Slack term: prefer leaving small slack (tight packing) - penalize large leftover.
    slack = np.maximum(rest_capacity - dem, 0.0) / denom_cap

    score = 0.45 * prox + 0.30 * radial + 0.15 * slack - 0.25 * load_term

    idx = int(np.argmin(score))
    return int(unvisited_nodes[idx])