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

    # ---- Scale-free normalizers ----
    scale = float(np.max(d_cur))
    if not np.isfinite(scale) or scale <= 0.0:
        scale = 1.0

    d0i = float(distance_matrix[depot][current_node])
    if not np.isfinite(d0i) or d0i < 0.0:
        d0i = 0.0

    # ---- Capacity pressure ----
    total_dem = float(np.sum(dem))
    if rest_capacity > 0.0:
        pressure = 0.0
        if total_dem + rest_capacity > 0.0:
            pressure = float(np.clip(total_dem / (total_dem + rest_capacity), 0.0, 1.0))
        fill = dem / rest_capacity
    else:
        pressure = 1.0
        fill = dem

    # ---- Elongation ratio rho = d_cur / (d0i + d0j) in (0,1] ----
    denom = d0i + d_dep
    denom = np.maximum(denom, 1e-12)
    rho = d_cur / denom
    rho = np.clip(rho, 0.0, 1.0)

    # ---- Inward spiral angular term via Law of Cosines ----
    # cos(theta_0) where theta_0 is angle at current node between depot-direction and candidate
    # Using: cos(theta) = (d0i^2 + d_cur^2 - d_dep^2) / (2 * d0i * d_cur)
    numer = d0i * d0i + d_cur * d_cur - d_dep * d_dep
    cden = 2.0 * d0i * d_cur
    cden = np.maximum(cden, 1e-12)
    cos_t = numer / cden
    cos_t = np.clip(cos_t, -1.0, 1.0)

    # ---- Adaptive spiral weight: strong inward early, relaxes with pressure ----
    alpha_0 = 1.00
    alpha_1 = 0.85
    alpha_eff = alpha_0 - alpha_1 * pressure
    if alpha_eff < 0.0:
        alpha_eff = 0.0
    w_cos = 0.30

    # ---- Nearest-unvisited isolation urgency (AST-safe diagonal mask) ----
    w_iso = 0.25
    if n >= 2:
        sub = distance_matrix[nodes][:, nodes].astype(float)
        # neutralize diagonal without np.fill_diagonal / np.ix_
        mask = np.eye(n) * (scale * 1e6 + 1e12)
        sub_m = sub + mask
        d_nn = np.min(sub_m, axis=1) / scale
    else:
        d_nn = np.zeros(n)

    # ---- Capacity-fill reward ----
    beta = 0.10

    # ---- Composite score (all terms scale-free) ----
    lin = (d_cur - alpha_eff * d_dep) / scale
    score = lin - w_cos * cos_t + 0.35 * rho - beta * fill - w_iso * d_nn

    # ---- Two-phase depot-start isolation bias for far outer seeds ----
    if current_node == depot and n >= 2:
        # positive isolation preference when just starting a route
        outer = d_dep / np.maximum(float(np.max(d_dep)), 1e-12)
        score = score + 0.25 * outer * d_nn

    best_idx = 0
    best_val = score[0]
    for idx in range(1, n):
        if score[idx] < best_val:
            best_val = score[idx]
            best_idx = idx

    # ---- Unblocked continuous capacity-adaptive voluntary early return ----
    if current_node != depot and n > 0:
        tau_0 = 0.26
        tau_1 = 0.45
        tau = tau_0 + tau_1 * pressure
        best_rho = float(rho[best_idx])
        if (1.0 - best_rho) < tau:
            if d_cur[best_idx] >= d_dep[best_idx] * (1.0 - tau):
                return int(depot)

    return int(nodes[best_idx])