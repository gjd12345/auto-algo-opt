def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if len(unvisited_nodes) == 0:
        return depot

    dm = distance_matrix
    d_cur = dm[current_node][unvisited_nodes]
    d_dep = dm[depot][unvisited_nodes]
    d_ret = dm[unvisited_nodes][depot] if False else d_dep  # symmetric assumption

    scale = float(np.max(d_dep)) if np.max(d_dep) > 0 else 1.0
    d_cur_n = d_cur / scale
    d_dep_n = d_dep / scale

    dem = demands[unvisited_nodes].astype(float)
    cap = float(rest_capacity) if rest_capacity > 0 else 1.0

    total_load = float(np.sum(dem))
    load_frac = total_load / cap if cap > 0 else 1.0
    if load_frac > 1.0:
        load_frac = 1.0
    if load_frac < 0.0:
        load_frac = 0.0

    util = dem / cap

    # Savings-style term: benefit of serving a node now relative to returning to depot.
    saving = d_dep_n - d_cur_n

    # Score: prefer close nodes, high savings weighted by load fraction, high utilization.
    score = d_cur_n - 0.75 * load_frac * saving - 0.2 * util

    idx = np.argmin(score)
    return int(unvisited_nodes[idx])