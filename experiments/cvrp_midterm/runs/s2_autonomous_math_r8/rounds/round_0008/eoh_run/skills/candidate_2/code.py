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

    total_dem = float(np.sum(demands))
    if not np.isfinite(total_dem) or total_dem <= 0.0:
        total_dem = 1.0

    mean_dem = float(np.mean(dem)) if n > 0 else 0.0

    # ---- single clean pressure state variable (never 0, never saturating) ----
    if current_node != depot and rest_capacity > 0.0:
        pressure = min(1.0, float(np.mean(dem)) / max(float(rest_capacity), 1e-12))
    else:
        pressure = 0.0

    # ---- phase decision: two-phase rem_routes depot start ----
    rem_routes = total_dem / max(float(rest_capacity), 1e-12)

    # scale-free normalizer
    scale = float(np.max(d_cur))
    if not np.isfinite(scale) or scale <= 0.0:
        scale = 1.0

    d0i = float(distance_matrix[depot][current_node])
    if not np.isfinite(d0i) or d0i < 0.0:
        d0i = 0.0

    # ---- AST-safe isolation urgency: min off-diagonal distance per node ----
    sub_all = distance_matrix[np.asarray(nodes)]
    sub = sub_all[:, nodes].astype(float)
    mask = np.eye(n) > 0.5
    d_nn = np.min(np.where(mask, np.inf, sub), axis=1) / scale
    if not np.all(np.isfinite(d_nn)):
        d_nn = np.where(np.isfinite(d_nn), d_nn, 0.0)

    # ---- elongation ratio rho in (0,1] ----
    denom = np.maximum(d0i + d_dep, 1e-12)
    rho = d_cur / denom

    # ---- angular coherence via Law-of-Cosines ----
    # cos(theta_0) at candidate between (candidate->current) and (candidate->depot)
    a = d_cur            # candidate <-> current
    b = d_dep            # candidate <-> depot
    c = d0i              # current  <-> depot
    num = b * b + a * a - c * c
    den = 2.0 * a * b
    den = np.maximum(den, 1e-12)
    cos_t = num / den
    cos_t = np.clip(cos_t, -1.0, 1.0)

    # ---- calibrated fill bonus ----
    if rest_capacity > 0.0:
        fill = np.clip(dem / rest_capacity, 0.0, 1.0)
    else:
        fill = np.zeros_like(dem)

    # ---- composite score weights ----
    alpha_0 = 1.00
    alpha_1 = 0.80
    alpha_eff = alpha_0 - alpha_1 * pressure

    w_iso = 0.24
    gamma = 0.36
    w_cos = 0.21
    beta = 0.105

    lin = (d_cur - alpha_eff * d_dep) / scale
    score = lin + gamma * rho - w_iso * d_nn - w_cos * cos_t - beta * fill

    # two-phase flavor: outside-in emphasizes far+isolated early on
    if rem_routes > 7.0:
        # boost isolation and radial distance slightly for outside-in spiral
        score = score - 0.05 * d_nn - 0.05 * (d_dep / scale)
    else:
        # compact radial-load: favor closer, angularly coherent nodes
        score = score + 0.05 * (d_cur / scale)

    best_idx = 0
    best_val = score[0]
    for idx in range(1, n):
        if score[idx] < best_val:
            best_val = score[idx]
            best_idx = idx

    # ---- adaptive early return driven by the same pressure ----
    if current_node != depot and rest_capacity > 0.0:
        tau_0 = 0.27
        tau_1 = 0.42
        tau = tau_0 + tau_1 * pressure
        best_rho = float(rho[best_idx])
        if (1.0 - best_rho) < tau:
            if d_cur[best_idx] >= d_dep[best_idx] * (1.0 - tau) * 1.10:
                return int(depot)

    return int(nodes[best_idx])