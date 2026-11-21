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

    eps = 1e-9
    # Detour ratio: how much extra travel relative to direct depot return.
    detour = (d_cur + d_dep) / max(d_cur_dep, eps)
    # Urgency: prefer nodes far from depot (they benefit from being served now).
    spread = d_dep / max(float(np.mean(d_dep)), eps)
    # Capacity pressure: prefer filling vehicle near end of route.
    used_frac = 1.0 - rest_capacity / max(rest_capacity + dem.max(), eps)

    # Multiplicative score: lower is better.
    # Balanced product: compact detour, high spread, high fill (esp. when nearly full).
    scores = (1.0 + detour) * (1.0 - 0.5 * fill) / (1.0 + spread * (0.5 + used_frac))

    return int(unvisited_nodes[np.argmin(scores)])