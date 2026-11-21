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
    idx = np.asarray(unvisited_nodes, dtype=int)
    d_cur = distance_matrix[current_node][idx]
    d_dep = distance_matrix[depot][idx]
    dem = demands[idx].astype(float)
    cap = float(rest_capacity) if rest_capacity > 0 else 1.0

    fill = dem / cap               # 0..1 how much this node fills the vehicle
    savings = d_dep - d_cur        # positive if node is farther from depot than current

    # Rebalanced score: stronger depot preference, stronger fill preference,
    # and a mild savings term to avoid backtracking toward the depot too early.
    score = 1.00 * d_cur - 0.35 * d_dep + 0.80 * (1.0 - fill) * d_cur - 0.10 * savings
    return int(idx[np.argmin(score)])