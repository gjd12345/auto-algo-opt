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

    cap = float(rest_capacity)
    dem = demands[idx].astype(np.float64)

    d_cur = dm[current_node][idx]
    d_dep = dm[depot][idx]

    span = float(np.max(dm))
    if not np.isfinite(span) or span <= 0.0:
        span = 1.0

    # normalize distances by span so terms are scale-invariant
    d_cur_n = d_cur / span
    d_dep_n = d_dep / span

    # fill incentive: prefer candidates using up remaining capacity
    fill = np.clip(dem / (cap + 1e-12), 0.0, 1.0)

    # linear combination: nearest-neighbour cost + depot pull - fill reward
    score = d_cur_n + 0.6 * d_dep_n - 0.5 * fill

    return int(idx[np.argmin(score)])