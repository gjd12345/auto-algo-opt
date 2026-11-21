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

    # Elongation ratio rho
    denom = np.maximum(d0i + d_dep, 1e-12)
    rho = d_cur / denom

    # AST-safe nearest-unvisited isolation distance (scale-free)
    if n >= 2:
        sub = distance_matrix[nodes][:, nodes].astype(float)
        eye_mask = np.eye(n) > 0.5
        masked = np.where(eye_mask, np.inf, sub)
        d_nn = np.min(masked, axis=1) / scale
    else:
        d_nn = np.zeros(n)

    # Capacity fill reward
    if rest_capacity > 0.0:
        fill = dem / rest_capacity
    else:
        fill = dem

    # Law-of-Cosines depot-ray angular coherence (scale-free)
    if current_node != depot:
        dij = d_cur
        d0j = d_dep
        cos_theta = (d0i * d0i + d0j * d0j - dij * dij) / np.maximum(2.0 * d0i * d0j, 1e-12)
        cos_theta = np.clip(cos_theta, -1.0, 1.0)
    else:
        cos_theta = np.zeros(n)

    # Pressure in [0,1]
    if current_node == depot:
        total_dem = float(np.sum(dem))
        if rest_capacity > 0.0:
            rem_routes = total_dem / rest_capacity
            pressure = 1.0 - min(1.0, max(0.0, rem_routes / 14.0))
        else:
            rem_routes = 1.0
            pressure = 0.0
    else:
        pressure = 0.0

    # Two-phase depot-start policy
    if current_node == depot:
        total_dem = float(np.sum(dem))
        rem_routes = total_dem / rest_capacity if rest_capacity > 0.0 else 1.0
        if rem_routes > 7.0:
            # Outside-in heavy-far clearing with mild isolation preference
            lin = (-0.58 * d_dep / scale)
            score = lin - 0.18 * rho - 0.22 * fill - 0.05 * cos_theta - 0.28 * d_nn
        else:
            # Compact radial-load seed
            lin = (0.85 * d_dep / scale)
            score = lin + 0.28 * rho - 0.42 * fill + 0.10 * d_nn
        best_idx = int(np.argmin(score))
        return int(nodes[best_idx])

    # Mid-route scoring with isolation urgency
    alpha_0 = 1.00
    alpha_1 = 0.85
    alpha = alpha_0 - alpha_1 * pressure
    beta = 0.105
    gamma = 0.35
    w_cos = 0.22
    w_iso = 0.24

    lin = (d_cur - alpha * d_dep) / scale
    score = lin + gamma * rho - beta * fill - w_cos * cos_theta - w_iso * d_nn

    best_idx = int(np.argmin(score))

    # Unblocked continuous capacity-adaptive early return
    if current_node != depot:
        if rest_capacity > 0.0:
            mean_dem = float(np.mean(dem)) if n > 0 else 0.0
            mean_ratio = mean_dem / rest_capacity
        else:
            mean_ratio = 1.0
        tau_0 = 0.26
        tau_1 = 0.45
        tau = tau_0 + tau_1 * min(1.0, max(0.0, mean_ratio))
        best_rho = float(rho[best_idx])
        best_sigma = 1.0 - best_rho
        if best_sigma < tau:
            if d_cur[best_idx] >= d_dep[best_idx] * (1.0 - tau) * 1.05:
                return int(depot)

    return int(nodes[best_idx])