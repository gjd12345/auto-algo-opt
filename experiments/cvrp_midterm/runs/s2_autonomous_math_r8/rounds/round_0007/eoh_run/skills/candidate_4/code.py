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

    # Scale-free isolation distance via AST-safe eye mask (no fill_diagonal)
    if n >= 2:
        sub = distance_matrix[nodes][:, nodes].astype(float)
        mask = np.eye(n) * (scale * 1e6 + 1e12)
        d_nn = np.min(sub + mask, axis=1) / scale
    else:
        d_nn = np.zeros(n)

    # Capacity pressure in [0,1]
    pressure = 1.0 - float(rest_capacity) / (
        float(rest_capacity) + float(np.sum(dem)) + 1e-12
    )
    pressure = 0.0 if pressure < 0.0 else (1.0 if pressure > 1.0 else pressure)

    # Two-phase depot start
    if current_node == depot:
        total_dem = float(np.sum(dem))
        rem_routes = total_dem / (rest_capacity + 1e-12)
        if rem_routes > 7.0:
            # outside-in: prefer far seeds, mild isolation preference
            return int(nodes[int(np.argmin(-d_dep / scale - 0.25 * d_nn - 0.20 * dem / (rest_capacity + 1e-12)))])
        else:
            return int(nodes[int(np.argmin(d_dep / scale - 0.30 * dem / (rest_capacity + 1e-12)))])

    # Inward-spiral reward: nearer-to-current prologue, depot-pull grows with pressure
    alpha_eff = 1.00 - 0.80 * pressure
    spiral = (d_cur / scale) - alpha_eff * (d_dep / scale)

    # Law-of-Cosines depot-ray angular coherence
    d0c = float(distance_matrix[depot][current_node])
    if d0c > 1e-12:
        denom_cos = np.maximum(2.0 * d_dep * d0c, 1e-12)
        cos_t = np.clip((d_dep * d_dep + d0c * d0c - d_cur * d_cur) / denom_cos, -1.0, 1.0)
    else:
        cos_t = np.zeros(n)

    fill = dem / (rest_capacity + 1e-12)
    w_iso = 0.25
    w_cos = 0.18
    beta = 0.11

    score = spiral - w_iso * d_nn - w_cos * cos_t - beta * fill

    # Continuous capacity-adaptive early return (unblocked)
    best = int(np.argmin(score))
    rho_best = float(d_cur[best] / max(d_dep[best] + d0c, 1e-12))
    tau = 0.26 + 0.45 * pressure
    if (1.0 - rho_best) < tau and float(np.max(dem)) > 0.40 * rest_capacity:
        return 0

    return int(nodes[best])