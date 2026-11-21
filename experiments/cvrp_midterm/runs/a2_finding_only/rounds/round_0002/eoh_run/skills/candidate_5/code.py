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
    dem = demands[idx]
    if cap > 0.0:
        load_fill = dem / cap
    else:
        load_fill = np.zeros_like(dem, dtype=np.float64)

    eps = 1e-12
    savings = d_dep - d_cur
    savings_term = savings / (d_cur + d_dep + eps)

    new_rest = cap - dem
    frag = np.maximum(new_rest, 0.0) / (cap + eps)

    # Rebalanced weights: stronger savings pull, weaker fragmentation,
    # moderate demand preference, slightly lighter nearest-neighbour weight.
    score = (0.85 * d_cur
             - 0.55 * savings_term
             - 0.20 * load_fill
             + 0.04 * frag)

    return int(idx[np.argmin(score)])