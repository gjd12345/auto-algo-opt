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

    d0i = float(distance_matrix[depot][current_node])
    if not np.isfinite(d0i) or d0i < 0.0:
        d0i = 0.0

    denom = np.maximum(d0i + d_dep, 1e-12)
    rho = d_cur / denom

    if n >= 2:
        sub = distance_matrix[nodes][:, nodes].astype(float)
        eye_mask = np.eye(n) > 0.5
        masked = np.where(eye_mask, np.inf, sub)
        d_nn = np.min(masked, axis=1) / scale
    else:
        d_nn = np.zeros(n)

    # Exponential capacity-fill reward
    if rest_capacity > 0.0:
        frac = np.clip(dem / rest_capacity, 0.0, 1.0)
    else:
        frac = np.ones(n)
    fill_exp = 1.0 - np.exp(-3.0 * frac)

    if current_node != depot:
        dij = d_cur
        d0j = d_dep
        cos_theta = (d0i * d0i + d0j * d0j - dij * dij) / np.maximum(2.0 * d0i * d0j, 1e-12)
        cos_theta = np.clip(cos_theta, -1.0, 1.0)
    else:
        cos_theta = np.zeros(n)

    if current_node == depot:
        total_dem = float(np.sum(dem))
        if rest_capacity > 0.0:
            rem_routes = total_dem / rest_capacity
        else:
            rem_routes = 1.0
        pressure = 1.0 - min(1.0, max(0.0, rem_routes / 14.0))
    else:
        rem_routes = 1.0
        pressure = 0.0

    # Two-phase depot-start policy
    if current_node == depot:
        total_dem = float(np.sum(dem))
        rem_routes = total_dem / rest_capacity if rest_capacity > 0.0 else 1.0
        if rem_routes > 7.0:
            lin = (-0.60 * d_dep / scale)
            score = lin - 0.16 * rho - 0.24 * fill_exp - 0.06 * cos_theta - 0.30 * d_nn
        else:
            lin = (0.88 * d_dep / scale)
            score = lin + 0.26 * rho - 0.45 * fill_exp + 0.08 * d_nn
        best_idx = int(np.argmin(score))
        return int(nodes[best_idx])

    # Mid-route scoring
    alpha_0 = 1.02
    alpha_1 = 0.88
    alpha = alpha_0 - alpha_1 * pressure
    beta = 0.115
    gamma = 0.32
    w_cos = 0.24
    w_iso = 0.26

    lin = (d_cur - alpha * d_dep) / scale
    score = lin + gamma * rho - beta * fill_exp - w_cos * cos_theta - w_iso * d_nn

    best_idx = int(np.argmin(score))

    # Sigmoid-shaped adaptive early return
    if current_node != depot:
        if rest_capacity > 0.0:
            mean_dem = float(np.mean(dem)) if n > 0 else 0.0
            mean_ratio = mean_dem / rest_capacity
        else:
            mean_ratio = 1.0
        mu = 0.34 + 0.42 * min(1.0, max(0.0, mean_ratio))
        best_rho = float(rho[best_idx])
        best_sigma = 1.0 - best_rho
        # Sigmoid gate: strong return pressure when sigma far below mu
        gate = 1.0 / (1.0 + np.exp((best_sigma - mu) * 18.0))
        if gate > 0.5:
            if d_cur[best_idx] >= d_dep[best_idx] * (1.0 - mu) * 1.02:
                return int(depot)

    return int(nodes[best_idx])