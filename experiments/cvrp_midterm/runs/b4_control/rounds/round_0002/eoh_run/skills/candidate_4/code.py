def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return depot

    cap = float(rest_capacity)
    if cap <= 0.0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes].astype(float)
    d_dep = distance_matrix[depot][unvisited_nodes].astype(float)
    dem = demands[unvisited_nodes].astype(float)

    r_cur = float(distance_matrix[depot][current_node])
    max_d = float(np.max(distance_matrix))
    if max_d <= 0.0:
        max_d = 1.0

    # Normalised proximity to current node (higher = closer)
    prox = 1.0 - d_cur / max_d

    # Angular consistency via law of cosines
    d_cd = float(distance_matrix[current_node][depot])
    denom = 2.0 * max(d_cd, 1e-9) * np.maximum(d_dep, 1e-9)
    cos_theta = (d_cd * d_cd + d_dep * d_dep - d_cur * d_cur) / denom
    cos_theta = np.clip(cos_theta, -1.0, 1.0)

    # Radial continuity: prefer staying near current depot radius
    radial_gap = np.abs(d_dep - r_cur) / (r_cur + 1e-9)

    # Load fill preference
    load_frac = (cap - dem) / cap

    score = 0.50 * prox + 0.25 * cos_theta - 0.20 * radial_gap + 0.15 * load_frac
    return int(unvisited_nodes[np.argmax(score)])