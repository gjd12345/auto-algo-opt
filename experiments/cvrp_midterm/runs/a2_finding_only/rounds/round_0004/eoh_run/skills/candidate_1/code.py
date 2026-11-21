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
    dem = demands[idx].astype(np.float64)

    util = np.clip(dem / (cap + 1e-12), 0.0, 1.0)
    new_rest = np.maximum(cap - dem, 0.0)
    tightness = 1.0 - new_rest / (cap + 1e-12)

    saving = (d_dep - d_cur) / (d_cur + d_dep + 1e-12)

    score = (1.00 * d_cur
             - 0.20 * saving
             - 0.45 * util
             - 0.15 * tightness)

    return int(idx[np.argmin(score)])