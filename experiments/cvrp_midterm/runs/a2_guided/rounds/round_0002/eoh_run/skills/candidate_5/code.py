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

    scale = float(np.mean(d_dep))
    if not np.isfinite(scale) or scale <= 0.0:
        scale = 1.0

    cap = float(rest_capacity)
    if cap <= 0.0:
        cap = 1.0

    s_cur = d_cur / scale
    s_dep = d_dep / scale
    fill = np.clip(dem / cap, 0.0, 1.0)
    s_cap = 1.0 - fill

    # Load ratio: how full the vehicle currently is (0 empty, 1 full).
    total_dem = float(np.sum(dem)) + cap  # rough original load proxy
    if total_dem <= 0.0:
        load_ratio = 1.0
    else:
        load_ratio = 1.0 - cap / total_dem
    load_ratio = min(max(load_ratio, 0.0), 1.0)

    # Adaptive depot weight: high when nearly empty, low when nearly full.
    w_dep = 0.55 - 0.45 * load_ratio

    score = 1.0 * s_cur + w_dep * s_dep + 0.20 * s_cap

    return int(unvisited_nodes[int(np.argmin(score))])