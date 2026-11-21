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
    unvisited = np.asarray(unvisited_nodes, dtype=np.int64)
    if unvisited.size == 0:
        return 0

    d_cur = distance_matrix[current_node][unvisited]
    d_dep = distance_matrix[depot][unvisited]
    dem = demands[unvisited]

    cap = max(rest_capacity, 1e-9)
    total_cap = cap
    fill = cap / (total_cap + 1e-9)
    urgency = fill * fill

    reward = (d_dep * (1.0 + dem / (cap + 1e-9))) / (d_cur + 1e-9)
    scores = -reward * urgency * (1.0 + dem / (cap + 1e-9))

    order = np.argsort(scores)
    best = order[0]
    cutoff = scores[best] + 0.01 * (np.abs(scores[best]) + 1.0)
    close = unvisited[scores <= cutoff]
    if close.size > 1:
        close_d = distance_matrix[current_node][close]
        return int(close[np.argmin(close_d)])
    return int(unvisited[best])