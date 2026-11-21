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
    dem = demands[unvisited_nodes]

    # Base ordering (preserved): depot-biased radial score.
    base = d_cur - 0.6 * d_dep

    # Scale-free near-tie gate: relative band on the base score span.
    span = float(np.max(base) - np.min(base))
    if span <= 0.0:
        return int(unvisited_nodes[np.argmin(base)])

    band = 1e-3 * span
    best_val = float(np.min(base))
    near = np.nonzero(base <= best_val + band)[0]

    if near.size <= 1:
        return int(unvisited_nodes[int(np.argmin(base))])

    # Capacity-aware refinement: prefer candidates that leave the smallest
    # residual that is still usable, balancing fit and remaining range.
    cand = near
    slack = rest_capacity - dem[cand]
    # Normalise slack by remaining capacity to stay scale-free.
    slack_frac = slack / max(rest_capacity, 1e-12)
    # Prefer close-to-full loads (small slack_frac) but also short return.
    refine = slack_frac * d_dep[cand] + d_cur[cand]

    return int(unvisited_nodes[cand[int(np.argmin(refine))]])