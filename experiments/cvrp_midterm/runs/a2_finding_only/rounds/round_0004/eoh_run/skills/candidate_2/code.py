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

    dm = distance_matrix
    idx = unvisited_nodes

    span = float(np.max(dm))
    if not np.isfinite(span) or span <= 0.0:
        span = 1.0

    d_cur = dm[current_node][idx] / span
    d_dep = dm[depot][idx] / span

    cap = float(rest_capacity)
    if cap <= 0.0:
        return depot

    dem = demands[idx].astype(np.float64)
    util = np.clip(dem / cap, 0.0, 1.0)

    # Remoteness: prefer customers that are far from the depot, since
    # they are cheapest to fold into the current tour now rather than
    # serving them on a dedicated trip later.
    remoteness = np.clip(d_dep, 0.0, 1.0)

    # Multiplicative composite: cost-like gap term divided by a
    # reward-like product. Small score = good candidate.
    # - proximity:   closeness to current node (dominant, squared)
    # - reward:      product of remoteness and utilisation, both in [0,1]
    # A small floor keeps the denominator strictly positive and
    # scale-free (all inputs are already normalised to [0, 1]).
    reward = remoteness * util
    score = (d_cur * d_cur + 1e-3) / (1e-3 + reward)

    return int(idx[np.argmin(score)])