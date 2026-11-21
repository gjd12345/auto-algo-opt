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
    # Primary: insertion-saving style term, normalised so it is scale-free.
    saving = d_cur + d_dep - 0.5 * (d_cur + d_dep)
    denom = d_cur + d_dep
    denom = np.where(denom <= 0, 1.0, denom)
    score = saving / denom
    # Secondary: among near-ties (relative to local spread), prefer larger demand.
    order = np.argsort(score)
    best = order[0]
    best_score = score[best]
    spread = score[order[-1]] - best_score
    if spread <= 0:
        spread = 1.0
    window = 0.20 * spread
    chosen = best
    best_demand = demands[unvisited_nodes[best]]
    for idx in order[1:]:
        if score[idx] - best_score > window:
            break
        dem = demands[unvisited_nodes[idx]]
        if dem > best_demand:
            best_demand = dem
            chosen = idx
    return unvisited_nodes[chosen]