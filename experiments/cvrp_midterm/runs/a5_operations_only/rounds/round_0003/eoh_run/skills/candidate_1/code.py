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

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    cap = rest_capacity if rest_capacity > 0 else 1.0

    savings = distance_matrix[current_node][depot] + d_dep - d_cur
    dem = demands[unvisited_nodes]
    new_rest = np.maximum(cap - dem, 0.0)
    fill_sq = 1.0 - (new_rest / cap) ** 2

    primary = 1.0 * d_cur - 0.5 * savings - 0.6 * fill_sq

    best_val = primary.min()
    tol = 1e-9
    close = np.where(primary <= best_val + tol)[0]

    if close.size > 1:
        candidates = unvisited_nodes[close]
        secondary = distance_matrix[depot][candidates] + 1e-6 * distance_matrix[current_node][candidates]
        return int(candidates[np.argmin(secondary)])

    return int(unvisited_nodes[int(np.argmin(primary))])