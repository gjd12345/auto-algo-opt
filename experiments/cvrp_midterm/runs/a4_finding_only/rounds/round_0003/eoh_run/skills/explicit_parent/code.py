def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if len(unvisited_nodes) == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]

    # Scale normalization: use a representative length scale of the instance.
    dm = distance_matrix
    n = dm.shape[0]
    # max distance among customer-depot distances as scale reference (invariant to uniform scaling)
    scale = np.max(d_dep) if np.max(d_dep) > 0 else 1.0
    # also consider max pairwise to be safe; but keep cheap and scale-consistent
    # use max over depot distance is fine since it scales linearly.

    d_cur_n = d_cur / scale
    d_dep_n = d_dep / scale

    # savings: how much going via current node saves vs depot roundtrip
    savings_n = d_dep_n - d_cur_n  # positive means current->node is closer than depot->node

    # load utilization contribution
    dem = demands[unvisited_nodes].astype(float)
    cap = float(rest_capacity) if rest_capacity > 0 else 1.0
    # remaining capacity after visiting (utilization is how much this fills)
    util = dem / cap  # between 0 and 1 per feasible node

    # Priority: prefer near, prefer high savings, prefer filling capacity
    # Weights chosen to be modest; all components scale-invariant.
    score = 1.0 * d_cur_n - 0.5 * savings_n - 0.3 * util

    idx = np.argmin(score)
    return int(unvisited_nodes[idx])