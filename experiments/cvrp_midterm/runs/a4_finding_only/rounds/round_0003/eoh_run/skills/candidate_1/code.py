def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if len(unvisited_nodes) == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]

    dm = distance_matrix
    scale = float(np.max(d_dep)) if np.max(d_dep) > 0 else 1.0

    d_cur_n = d_cur / scale
    d_dep_n = d_dep / scale

    # savings relative to depot roundtrip
    savings_n = d_dep_n - d_cur_n

    dem = demands[unvisited_nodes].astype(float)
    cap = float(rest_capacity) if rest_capacity > 0 else 1.0
    util = dem / cap  # fraction of remaining capacity this node fills

    # Stronger weight on savings and capacity fill than the incumbent
    score = 1.0 * d_cur_n - 0.9 * savings_n - 0.6 * util

    idx = np.argmin(score)
    return int(unvisited_nodes[idx])