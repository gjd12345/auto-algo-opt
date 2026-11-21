def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return 0

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    d_cd = distance_matrix[current_node][depot]

    dem = demands[unvisited_nodes]
    dem0 = float(np.sum(demands)) if demands.size else 1.0
    if rest_capacity > 0:
        load_frac = rest_capacity / (rest_capacity + 1e-12 + float(np.sum(dem)))
    else:
        load_frac = 0.0

    # Load-aware weight: more detour penalty when capacity is tight.
    lam = 0.5 + 0.3 * (1.0 - load_frac)

    # Detour relative to going straight back to depot (span-normalised by d_cd).
    detour = (d_cur + d_dep - d_cd)
    span = d_cd + 1e-9

    priority = d_cur + 0.5 * d_dep - lam * detour

    # Prefer larger demands when distances tie (helps pack routes).
    priority = priority - 1e-6 * dem

    return int(unvisited_nodes[np.argmin(priority)])