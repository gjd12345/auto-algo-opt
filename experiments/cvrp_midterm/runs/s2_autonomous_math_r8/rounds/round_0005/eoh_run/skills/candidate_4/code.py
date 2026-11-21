def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return 0

    nodes = np.asarray(unvisited_nodes)
    n = nodes.size

    d_cur = distance_matrix[current_node][nodes].astype(float)
    d_dep = distance_matrix[depot][nodes].astype(float)
    dem = demands[nodes].astype(float)

    scale = float(np.max(d_cur))
    if not np.isfinite(scale) or scale <= 0.0:
        scale = 1.0

    d0i = distance_matrix[depot][current_node]
    if not np.isfinite(d0i) or d0i < 0.0:
        d0i = 0.0

    denom = d0i + d_dep
    denom = np.maximum(denom, 1e-12)
    rho = d_cur / denom

    if rest_capacity > 0.0:
        fill = dem / rest_capacity
    else:
        fill = dem

    if current_node != depot:
        dij = d_cur
        d0j = d_dep
        cos_theta = (d0i * d0i + d0j * d0j - dij * dij) / np.maximum(2.0 * d0i * d0j, 1e-12)
        cos_theta = np.clip(cos_theta, -1.0, 1.0)
    else:
        cos_theta = np.zeros(n)

    if current_node == depot:
        total_dem = float(np.sum(dem))
        rem_routes = total_dem / rest_capacity if rest_capacity > 0.0 else 1.0
        if rem_routes > 7.0:
            lin = (-0.60 * d_dep / scale)
            score = lin - 0.20 * rho - 0.25 * fill - 0.05 * cos_theta
        else:
            lin = (0.85 * d_dep / scale)
            score = lin + 0.30 * rho - 0.40 * fill
        best_idx = int(np.argmin(score))
        return int(nodes[best_idx])

    mean_dem = float(np.mean(dem))
    if rest_capacity > 0.0:
        pressure = min(1.0, mean_dem / rest_capacity)
    else:
        pressure = 1.0

    alpha_0 = 1.02
    alpha_1 = 0.85
    alpha = alpha_0 - alpha_1 * pressure

    beta = 0.12
    gamma = 0.35
    w_cos = 0.20

    lin = (d_cur - alpha * d_dep) / scale
    score = lin + gamma * rho - beta * fill - w_cos * cos_theta

    best_idx = int(np.argmin(score))

    if rest_capacity > 0.0:
        mean_ratio = mean_dem / rest_capacity
    else:
        mean_ratio = 1.0
    tau = 0.27 + 0.40 * min(1.0, mean_ratio)
    best_rho = float(rho[best_idx])
    best_sigma = 1.0 - best_rho
    if best_sigma < tau:
        if d_cur[best_idx] >= d_dep[best_idx] * (1.0 - tau) * 1.10:
            return int(depot)

    return int(nodes[best_idx])