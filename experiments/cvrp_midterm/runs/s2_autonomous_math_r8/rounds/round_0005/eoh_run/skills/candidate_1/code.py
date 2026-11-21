def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return 0

    nodes = np.asarray(unvisited_nodes)
    d_cur = distance_matrix[current_node][nodes].astype(float)
    d_dep = distance_matrix[depot][nodes].astype(float)
    dem = demands[nodes].astype(float)

    # Scale-free normalizer
    scale = float(np.mean(d_cur) + np.mean(d_dep) + 1e-12)

    # State-only capacity pressure (dimensionless)
    mean_dem = float(np.mean(dem))
    pressure = min(1.0, mean_dem / max(rest_capacity, 1e-12))

    # Decaying depot pull: high early (sweep outward), low/negative late (spiral inward)
    alpha_eff = 1.05 - 0.90 * pressure

    # Radial pull term
    radial = (d_cur - alpha_eff * d_dep) / scale

    # Elongation ratio rho = d_cur / (d0i + d0j)
    d0c = float(distance_matrix[depot][current_node]) if current_node != depot else 0.0
    pair = d_dep + d0c
    pair = np.maximum(pair, 1e-12)
    rho = d_cur / pair

    # Angular coherence via Law of Cosines: cos(theta_0) between
    # (current -> candidate) and (candidate -> depot)
    # cos(theta) = (d_cur^2 + d_dep^2 - d0c^2) / (2 * d_cur * d_dep)
    denom_cos = 2.0 * d_cur * d_dep
    denom_cos = np.where(denom_cos > 1e-12, denom_cos, 1e-12)
    cos_theta = (d_cur * d_cur + d_dep * d_dep - d0c * d0c) / denom_cos
    cos_theta = np.clip(cos_theta, -1.0, 1.0)

    # Fill reward (dimensionless)
    fill = dem / max(rest_capacity, 1e-12)
    beta = 0.11

    w_cos = 0.18
    gamma_rho = 0.45

    score = radial + gamma_rho * rho - w_cos * cos_theta - beta * fill

    # Capacity-adaptive early return: near-full truck with small improvement heads home
    if current_node != depot:
        tau = 0.30 + 0.15 * pressure
        best_idx_local = int(np.argmin(score))
        best_rho = float(rho[best_idx_local])
        fill_ratio = float(dem[best_idx_local]) / max(rest_capacity, 1e-12)
        if fill_ratio > 0.55:
            if best_rho > (0.72 - 0.10 * min(fill_ratio, 1.0)):
                return int(depot)
        if (1.0 - best_rho) < tau and d_cur[best_idx_local] >= d_dep[best_idx_local] * (1.0 - tau):
            return int(depot)

    return int(nodes[int(np.argmin(score))])