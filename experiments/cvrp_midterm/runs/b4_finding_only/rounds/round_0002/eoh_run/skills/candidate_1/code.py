def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    d_cur_dep = distance_matrix[current_node][depot]
    dem = demands[unvisited_nodes].astype(float)

    scale = float(np.max(distance_matrix[depot])) if distance_matrix.size else 1.0
    if scale <= 0.0:
        scale = 1.0

    low = np.minimum(d_cur, d_dep)
    high = np.maximum(d_cur, d_dep)
    safe_low = np.where(low > 0.0, low, 1.0)
    cos_angle = (d_cur_dep * d_cur_dep + safe_low * safe_low - high * high) / (2.0 * d_cur_dep * safe_low + 1e-12)
    cos_angle = np.clip(cos_angle, -1.0, 1.0)
    angle = np.arccos(cos_angle)

    detour = (d_cur + d_dep - d_cur_dep) / scale + 0.05 * angle

    cap = float(rest_capacity) if rest_capacity > 0.0 else 1.0
    tightness = 1.0 - cap / max(cap + float(np.sum(dem)), 1e-9)
    load_term = dem / cap

    score = detour / (load_term + 0.1) - 0.1 * tightness * load_term

    return int(unvisited_nodes[np.argmin(score)])