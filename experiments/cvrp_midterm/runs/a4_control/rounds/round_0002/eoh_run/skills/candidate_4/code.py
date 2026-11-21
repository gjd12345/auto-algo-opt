def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes].astype(float)
    d_dep = distance_matrix[depot][unvisited_nodes].astype(float)
    d_cur_dep = float(distance_matrix[current_node][depot])

    dem = demands[unvisited_nodes].astype(float)
    fill = dem / max(rest_capacity, 1e-9)
    fill = np.clip(fill, 0.0, 1.0)

    eps = 1e-9
    detour = (d_cur + d_dep) / max(d_cur_dep, eps)
    spread = d_dep / max(float(np.mean(d_dep)), eps)

    alpha = 1.5
    beta = 0.85
    gamma = 2.0
    delta = 0.3

    scores = (np.power(1.0 + detour, alpha) *
              np.power(np.maximum(1.0 - beta * fill, eps), gamma) /
              (1.0 + delta * spread))

    return int(unvisited_nodes[np.argmin(scores)])