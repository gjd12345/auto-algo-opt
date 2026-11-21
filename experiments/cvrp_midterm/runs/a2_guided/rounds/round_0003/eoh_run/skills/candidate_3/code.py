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

    d_cur = distance_matrix[current_node][unvisited_nodes].astype(np.float64)
    d_dep = distance_matrix[depot][unvisited_nodes].astype(np.float64)
    dem = demands[unvisited_nodes].astype(np.float64)

    # Span-proportional normaliser -> scale invariant.
    span = float(np.max(d_dep))
    if not np.isfinite(span) or span <= 0.0:
        span = 1.0

    cap = float(rest_capacity)
    if cap <= 0.0:
        cap = 1.0

    # Dimensionless normalized terms.
    ncur = d_cur / span
    ndep = d_dep / span
    fill = np.clip(dem / cap, 0.0, 1.0)

    # Multiplicative urgency: nearer-to-current and fuller-capacity customers
    # get smaller scores. Depot proximity acts as a mild tie-breaker.
    denom = 1.0 + 2.0 * fill
    score = (ncur + 0.20 * ndep) / denom

    return int(unvisited_nodes[int(np.argmin(score))])