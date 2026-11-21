def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return int(depot)

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    d_cd = distance_matrix[current_node][depot]

    dem = demands[unvisited_nodes]

    cap = rest_capacity if rest_capacity > 0 else 1.0
    fill = dem / cap
    fill = np.clip(fill, 0.0, 1.0)

    span = float(np.max(d_cur) - np.min(d_cur))
    if span <= 0.0:
        span = 1.0
    d_norm = (d_cur - float(np.min(d_cur))) / span

    savings = d_cd + d_dep - d_cur
    s_span = float(np.max(savings) - np.min(savings))
    if s_span <= 0.0:
        s_span = 1.0
    s_norm = (savings - float(np.min(savings))) / s_span

    score = 0.55 * d_norm - 0.35 * s_norm - 0.20 * fill

    return int(unvisited_nodes[int(np.argmin(score))])