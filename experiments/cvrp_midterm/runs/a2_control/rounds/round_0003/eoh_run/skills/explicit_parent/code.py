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

    # Score: favor close nodes, but prefer those that fill the vehicle
    # (high demand relative to remaining capacity) and are not too far from depot.
    score = d_cur - 0.20 * d_dep + 0.50 * (1.0 - dem / cap) * d_cur
    return int(idx[np.argmin(score)])