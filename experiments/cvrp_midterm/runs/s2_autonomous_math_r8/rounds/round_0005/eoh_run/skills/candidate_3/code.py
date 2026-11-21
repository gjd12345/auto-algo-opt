def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return 0

    nodes = np.asarray(unvisited_nodes)
    d_cur = distance_matrix[current_node][nodes].astype(float)
    d_dep = distance_matrix[depot][nodes].astype(float)
    dem = demands[nodes].astype(float)

    scale = float(np.mean(d_dep) + np.mean(d_cur) + 1e-12)

    d0c = float(distance_matrix[depot][current_node]) if current_node != depot else 0.0
    pair = np.maximum(d_dep + d0c, 1e-12)
    rho = d_cur / pair

    # State-only capacity pressure (depends ONLY on vehicle state, not candidates)
    mean_dem = float(np.mean(dem))
    pressure = min(1.0, mean_dem / max(rest_capacity, 1e-12))
    alpha_0 = 1.05
    alpha_1 = 0.95
    alpha_eff = alpha_0 - alpha_1 * pressure

    radial = (d_cur - alpha_eff * d_dep) / scale

    fill = dem / (rest_capacity + 1e-12)
    beta = 0.11

    if current_node != depot:
        denom_cos = np.maximum(2.0 * d_dep * d0c, 1e-12)
        cos_t = np.clip((d_dep * d_dep + d0c * d0c - d_cur * d_cur) / denom_cos, -1.0, 1.0)
        w_cos = 0.20
    else:
        cos_t = np.zeros_like(d_cur)
        w_cos = 0.0

    score = radial + 0.35 * rho - beta * fill - w_cos * cos_t

    if current_node == depot:
        total_dem = float(np.sum(dem))
        rem_routes = total_dem / (rest_capacity + 1e-12)
        if rem_routes > 7.0:
            score = -d_dep / scale - 0.25 * fill
        else:
            score = d_dep / scale - 0.30 * fill
        return int(nodes[int(np.argmin(score))])

    best_dem = float(np.max(dem))
    tau = 0.25 + 0.50 * min(1.0, mean_dem / (rest_capacity + 1e-12))

    if best_dem > 0.55 * rest_capacity:
        best_idx_local = int(np.argmin(score))
        rho_best = float(rho[best_idx_local])
        if (1.0 - rho_best) < tau:
            return 0

    return int(nodes[int(np.argmin(score))])