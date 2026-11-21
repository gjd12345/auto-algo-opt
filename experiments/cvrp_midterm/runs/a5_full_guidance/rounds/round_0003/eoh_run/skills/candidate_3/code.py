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
    # Clarke-Wright style savings: going depot->cur->cand saves vs. two trips.
    saving = d_dep + d_dep - d_cur
    # Normalise by a per-step scale so the score is dimensionless.
    scale = np.maximum(d_cur + d_dep, 1e-12)
    score = saving / scale
    # Lower saving = more attractive next hop; pick smallest first.
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