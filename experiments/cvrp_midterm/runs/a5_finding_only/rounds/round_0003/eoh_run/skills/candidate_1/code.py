def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if len(unvisited_nodes) == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes].astype(float)
    d_dep = distance_matrix[depot][unvisited_nodes].astype(float)

    cur_to_dep = float(distance_matrix[current_node][depot])
    a = d_cur
    b = cur_to_dep
    c = d_dep
    denom = 2.0 * a * b + 1e-12
    cos_angle = (a * a + b * b - c * c) / denom
    cos_angle = np.clip(cos_angle, -1.0, 1.0)
    continuation = -cos_angle

    dem = demands[unvisited_nodes].astype(float)
    cap = float(rest_capacity) + 1e-9
    load_frac = dem / cap

    mean_dcur = float(np.mean(d_cur)) if len(d_cur) > 0 else 1.0
    if mean_dcur <= 0:
        mean_dcur = 1.0
    near = d_cur / mean_dcur

    pack = load_frac * (1.0 + 0.25 * load_frac)

    score = 1.35 * near - 0.25 * continuation - 0.60 * pack
    idx = int(np.argmin(score))
    return int(unvisited_nodes[idx])