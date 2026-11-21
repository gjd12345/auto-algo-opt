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

    # Elongation ratio
    denom = np.maximum(d0i + d_dep, 1e-12)
    rho = d_cur / denom

    # Isolation urgency via masked nearest neighbor
    if n >= 2:
        sub = distance_matrix[nodes][:, nodes].astype(float)
        eye_mask = np.eye(n) > 0.5
        masked = np.where(eye_mask, np.inf, sub)
        d_nn = np.min(masked, axis=1) / scale
    else:
        d_nn = np.zeros(n)

    # Fill reward
    if rest_capacity > 0.0:
        fill = dem / rest_capacity
    else:
        fill = dem

    # Angular coherence
    if current_node != depot and d0i > 0.0:
        dij = d_cur
        d0j = d_dep
        cos_theta = (d0i * d0i + d0j * d0j - dij * dij) / np.maximum(2.0 * d0i * d0j, 1e-12)
        cos_theta = np.clip(cos_theta, -1.0, 1.0)
    else:
        cos_theta = np.zeros(n)

    # Single clean pressure variable
    if rest_capacity > 0.0:
        pressure = min(1.0, float(np.mean(dem)) / max(float(rest_capacity), 1e-12))
    else:
        pressure = 1.0

    # Two-phase depot-start policy
    if current_node == depot:
        total_dem = float(np.sum(dem))
        rem_routes = total_dem / rest_capacity if rest_capacity > 0.0 else 1.0
        if rem_routes > 7.0:
            # Outside-in clearing: far + isolated
            score = (-0.60 * d_dep / scale) - 0.18 * rho - 0.22 * fill \
                    - 0.05 * cos_theta - 0.28 * d_nn
        else:
            # Compact radial-load seed
            score = (0.85 * d_dep / scale) + 0.28 * rho - 0.42 * fill + 0.10 * d_nn
        return int(nodes[int(np.argmin(score))])

    # Multiplicative harmonic radial pull (replaces linear d_cur - alpha*d_dep)
    # Spiral inward as pressure rises; blend weight drives depot pull strength
    alpha_0 = 1.10
    alpha_1 = 0.75
    w_cur = 1.0
    w_dep = max(0.05, 1.0 - (alpha_0 - alpha_1 * pressure) * pressure)
    # Harmonic blend: lower -> closer in combined sense
    inner = w_cur * d_cur + w_dep * d_dep
    harm = (1.0 / np.maximum(inner / scale, 1e-12))
    # Convert to decreasing-distance form: use inner as additive potential
    radial = inner / scale

    beta = 0.105
    gamma = 0.36
    w_cos = 0.22
    w_iso = 0.24

    score = radial + gamma * rho - beta * fill - w_cos * cos_theta - w_iso * d_nn

    best_idx = int(np.argmin(score))

    # Continuous capacity-aware early-return gate
    tau_0 = 0.27
    tau_1 = 0.42
    tau = tau_0 + tau_1 * pressure
    best_rho = float(rho[best_idx])
    best_sigma = 1.0 - best_rho
    if best_sigma < tau:
        if d_cur[best_idx] >= d_dep[best_idx] * (1.0 - tau) * 1.05:
            return int(depot)

    return int(nodes[best_idx])