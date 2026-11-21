def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return 0

    cur_d = distance_matrix[current_node][unvisited_nodes]
    depot_d = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes]

    max_cur = float(np.max(cur_d)) if cur_d.size > 0 else 0.0
    max_depot = float(np.max(depot_d)) if depot_d.size > 0 else 0.0
    denom_cur = max_cur if max_cur > 1e-9 else 1.0
    denom_depot = max_depot if max_depot > 1e-9 else 1.0
    denom_cap = rest_capacity if rest_capacity > 1e-9 else 1.0

    prox = cur_d / denom_cur
    radial = depot_d / denom_depot
    load_term = dem / denom_cap
    slack = np.maximum(rest_capacity - dem, 0.0) / denom_cap

    score = 0.70 * prox + 0.20 * radial + 0.05 * slack - 0.35 * load_term

    idx = int(np.argmin(score))
    return int(unvisited_nodes[idx])