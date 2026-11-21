def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return 0

    nodes = np.asarray(unvisited_nodes)
    n = int(nodes.size)

    d_cur = distance_matrix[current_node][nodes].astype(float)
    d_dep = distance_matrix[depot][nodes].astype(float)
    dem = demands[nodes].astype(float)

    scale = float(np.mean(d_dep) + np.mean(d_cur) + 1e-12)

    # Isolation urgency: distance to nearest other unvisited node (AST-safe diagonal masking)
    if n >= 2:
        sub = distance_matrix[nodes][:, nodes].astype(float)
        mask = np.eye(n) > 0.5
        d_nn = np.min(np.where(mask, np.inf, sub), axis=1) / scale
    else:
        d_nn = np.zeros(n)

    # Elongation ratio rho = d_cur / (d_dep + d0c)
    d0c = float(distance_matrix[depot][current_node]) if current_node != depot else 0.0
    pair = np.maximum(d_dep + d0c, 1e-12)
    rho = d_cur / pair

    # Pressure = fraction of remaining capacity consumed per remaining node
    total_dem = float(np.sum(dem))
    pressure = total_dem / (rest_capacity + 1e-12)

    # Capacity-adaptive inward spiral
    alpha_eff = 1.00 - 0.85 * min(1.0, pressure)
    radial = (d_cur - alpha_eff * d_dep) / scale

    fill = dem / (rest_capacity + 1e-12)
    beta = 0.10

    # Law-of-Cosines angular coherence at non-depot node
    if current_node != depot:
        denom_cos = np.maximum(2.0 * d_dep * d0c, 1e-12)
        cos_t = np.clip((d_dep * d_dep + d0c * d0c - d_cur * d_cur) / denom_cos, -1.0, 1.0)
        w_cos = 0.20
    else:
        cos_t = np.zeros_like(d_cur)
        w_cos = 0.0

    score = radial + 0.35 * rho - beta * fill - w_cos * cos_t - 0.25 * d_nn

    # Two-phase depot-start policy
    if current_node == depot:
        rem_routes = total_dem / (rest_capacity + 1e-12)
        if rem_routes > 7.0:
            # outside-in: prefer far isolated nodes; add mild isolation preference
            score = -d_dep / scale - 0.25 * fill - 0.30 * d_nn
        else:
            # compact radial-load seed
            score = d_dep / scale - 0.30 * fill - 0.15 * d_nn
        return int(nodes[int(np.argmin(score))])

    # Unblocked continuous capacity-adaptive early return
    best_idx_local = int(np.argmin(score))
    rho_best = float(rho[best_idx_local])
    tau = 0.26 + 0.45 * min(1.0, pressure)
    if (1.0 - rho_best) < tau:
        return 0

    return int(nodes[best_idx_local])