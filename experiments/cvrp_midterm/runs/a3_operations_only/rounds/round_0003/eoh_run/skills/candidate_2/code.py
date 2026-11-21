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

    # Angular alignment: cosine between the "outward" depot->candidate
    # direction and the "forward" current->candidate direction. Reuses only
    # the distance matrix (no extra coordinates needed) via the law of
    # cosines: cos(theta) = (d_dep^2 + d_cur_dep^2 - d_cur^2) / (2*d_dep*d_cur_dep)
    d_cur_dep = float(distance_matrix[current_node][depot])
    denom = 2.0 * np.maximum(d_dep, 1e-9) * max(d_cur_dep, 1e-9)
    cos_out = (d_dep * d_dep + d_cur_dep * d_cur_dep - d_cur * d_cur) / denom
    cos_out = np.clip(cos_out, -1.0, 1.0)

    # Primary term: nearest-neighbour cost penalised for pointing back
    # toward the depot (negative alignment). No savings, no capacity ratio.
    align_bonus = 1.0 + 0.5 * cos_out
    primary = d_cur / np.maximum(align_bonus, 1e-9)

    order = np.argsort(primary)
    best = order[0]

    # Second stage: within a tight band, prefer larger demand to fill the
    # vehicle quickly and keep the route compact; tie-break nearest.
    band = primary[best] + 0.02 * (primary[best] + 1.0)
    close_mask = primary <= band
    close = unvisited[close_mask]
    if close.size > 1:
        close_dem = demands[close]
        max_dem = close_dem.max()
        heavy = close[close_dem >= max_dem - 1e-9]
        if heavy.size == 1:
            return int(heavy[0])
        heavy_d = distance_matrix[current_node][heavy]
        return int(heavy[np.argmin(heavy_d)])
    return int(unvisited[best])