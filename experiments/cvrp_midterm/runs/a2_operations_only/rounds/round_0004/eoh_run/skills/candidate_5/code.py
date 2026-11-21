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
    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes]
    alpha = 1.2
    cap_weight = rest_capacity / (rest_capacity + dem + 1e-9)
    score = d_cur - alpha * d_dep * cap_weight
    order = np.argsort(score)
    best = order[0]
    # secondary ordering among near-ties of the primary score
    tie_band = score[best] + 0.05 * d_cur[best]
    ties = order[score[order] <= tie_band]
    if ties.size > 1:
        best = ties[np.argmin(d_cur[ties])]
    return int(unvisited_nodes[best])