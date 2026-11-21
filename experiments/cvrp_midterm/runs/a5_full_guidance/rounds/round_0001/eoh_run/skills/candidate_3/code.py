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
    c = distance_matrix[current_node][unvisited_nodes]
    d = distance_matrix[depot][unvisited_nodes]
    # Scale-invariant score: relative saving of serving near-current vs depot
    denom = c + d
    denom = np.where(denom <= 0.0, 1.0, denom)
    score = c / denom

    order = np.argsort(score)
    best = order[0]
    best_score = score[best]

    # Cheap relative near-tie gate: spread-normalized, hence scale-invariant
    spread = score[order[-1]] - best_score
    if spread > 0.0:
        thr = best_score + 0.25 * spread
    else:
        thr = best_score

    cand = order[score[order] <= thr]
    if cand.size > 1:
        # Secondary criterion: prefer larger remaining capacity after service
        # (i.e. smaller demand) then nearer current node, both mild tie-breaks.
        best = cand[np.argmin(demands[unvisited_nodes[cand]] * 1.0 + 1e-9 * c[cand])]

    return int(unvisited_nodes[best])