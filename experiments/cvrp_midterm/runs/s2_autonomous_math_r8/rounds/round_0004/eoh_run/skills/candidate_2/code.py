def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return 0

    nodes = np.asarray(unvisited_nodes)
    n = nodes.size
    dem = demands[nodes].astype(float)

    d_cur = distance_matrix[current_node][nodes].astype(float)
    d_dep = distance_matrix[depot][nodes].astype(float)

    # Scale-free normalizer
    scale = float(np.max(d_cur))
    if not np.isfinite(scale) or scale <= 0.0:
        scale = 1.0

    d0_cur = float(distance_matrix[depot][current_node])
    if not np.isfinite(d0_cur) or d0_cur < 0.0:
        d0_cur = 0.0

    rest = float(rest_capacity)
    if not np.isfinite(rest) or rest <= 0.0:
        rest = 1.0

    eps = 1e-12

    # ---------- Depot-start phase: two-phase remaining-fleet policy ----------
    if current_node == depot:
        total_rem_dem = float(np.sum(demands[nodes].astype(float)))
        rem_routes = total_rem_dem / rest if rest > 0.0 else 1.0

        rel_dem = dem / rest
        rel_dist = d_dep / scale

        if rem_routes > 7.0:
            # many routes remain: outside-in heavy-far clearing
            score = rel_dist - 0.55 * rel_dem
        else:
            # few routes remain: compact radial-load seed
            score = rel_dist + 0.35 * rel_dem
        return int(nodes[int(np.argmin(score))])

    # ---------- Mid-route: radial-efficiency + angular coherence scoring ----------
    # Outward radial projection reference: distance from depot to current node
    # (Law-of-Cosines cos(theta_0) between depot->current and depot->candidate)
    cos_theta = (d0_cur * d0_cur + d_dep * d_dep - d_cur * d_cur) / np.maximum(
        2.0 * d0_cur * d_dep, eps)
    cos_theta = np.clip(cos_theta, -1.0, 1.0)

    # Radial advance along depot ray: candidate sitting "beyond" current node on
    # the same petal gains positively.
    radial_advance = (d_dep - d0_cur) / scale  # negative => moves outward

    # Detour cost in dimensionless form
    detour = d_cur / scale

    # Radial efficiency: outward progress per unit of detour
    efficiency = (-radial_advance) / (detour + eps)

    # Angular coherence bonus: reward candidates aligned on the same petal
    coherence = cos_theta

    # Fill reward (dimensionless)
    fill = dem / rest

    w_eff = 0.60
    w_cos = 0.18
    w_fill = 0.30

    score = (-w_eff * efficiency) - w_cos * coherence - w_fill * fill

    # tiny tie-break: nearest distance (dimensionless)
    score = score + 1e-6 * detour

    best_idx = int(np.argmin(score))

    # ---------- Capacity-adaptive voluntary early return ----------
    mean_dem = float(np.mean(dem)) if n > 0 else 0.0
    mean_ratio = mean_dem / rest
    if mean_ratio > 1.0:
        mean_ratio = 1.0

    tau_0 = 0.27
    tau_1 = 0.40
    tau = tau_0 + tau_1 * mean_ratio

    # rho = d_cur / (d0_cur + d_dep), dimensionless elongation
    denom = d0_cur + d_dep
    denom = np.maximum(denom, eps)
    rho = d_cur / denom

    best_rho = float(rho[best_idx])
    if (1.0 - best_rho) < tau:
        if d_cur[best_idx] >= d_dep[best_idx] * (1.0 - tau) * 1.10:
            return int(depot)

    return int(nodes[best_idx])