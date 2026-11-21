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
    if idx.size == 0:
        return 0

    d_cur = distance_matrix[current_node][idx].astype(float)
    d_dep = distance_matrix[depot][idx].astype(float)
    d_cur_dep = float(distance_matrix[current_node][depot])
    dem = demands[idx].astype(float)

    cap = float(rest_capacity) if rest_capacity > 0 else 1.0

    # Clarke-Wright style saving: extending current route to this node vs returning to depot
    savings = d_cur_dep + d_dep - d_cur

    # Urgency from fill ratio: prefer nodes whose demand uses a large fraction of remaining capacity
    fill = dem / cap

    # Primary score: larger saving is better, so minimize the negative
    score = -savings + 0.5 * d_dep * (1.0 - fill)

    # Penalize very small fills to avoid stranding capacity
    score = score + 0.3 * (1.0 - fill) * np.max(d_cur + 1e-9)

    return int(idx[np.argmin(score)])