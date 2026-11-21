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

    # Scale-free normalizers
    scale = float(np.max(d_cur))
    if not np.isfinite(scale) or scale <= 0.0:
        scale = 1.0

    d0i = distance_matrix[depot][current_node]
    if not np.isfinite(d0i) or d0i < 0.0:
        d0i = 0.0

    # Elongation ratio rho(i,j) = d_cur / (d0i + d0j), always in (0,1]
    denom = d0i + d_dep
    denom = np.maximum(denom, 1e-12)
    rho = d_cur / denom

    # Capacity-fill reward (demand normalized ONLY by rest_capacity)
    if rest_capacity > 0.0:
        fill = dem / rest_capacity
    else:
        fill = dem

    # Composite score: normalized linear radial pull + elongation + fill reward
    alpha = 0.75
    beta = 0.10
    gamma = 0.35

    lin = (d_cur - alpha * d_dep) / scale
    score = lin + gamma * rho - beta * fill

    best_idx = 0
    best_val = score[0]
    for idx in range(1, n):
        if score[idx] < best_val:
            best_val = score[idx]
            best_idx = idx

    # Capacity-adaptive voluntary early return (only when not at depot)
    if current_node != depot and n > 0:
        mean_dem = float(np.mean(dem)) if n > 0 else 0.0
        if rest_capacity > 0.0:
            load_frac = 1.0 - (rest_capacity / (rest_capacity + mean_dem))
            # adaptive tau rises as vehicle gets fuller relative to mean demand
            mean_ratio = mean_dem / rest_capacity if rest_capacity > 0.0 else 1.0
            tau = 0.30 + 0.15 * min(1.0, mean_ratio)
        else:
            tau = 0.45
        # sigma = 1 - rho ; return early if best candidate is not enough better than depot
        best_sigma = 1.0 - float(rho[best_idx])
        # Also consider the minimum rho among candidates
        min_rho = float(np.max(rho))  # farthest from depot direction
        best_rho = float(rho[best_idx])
        if (1.0 - best_rho) < tau:
            # Only return if heading back is competitive; require that even the
            # best candidate is close in radial terms
            if d_cur[best_idx] >= d_dep[best_idx] * (1.0 - tau) * 1.15:
                return int(depot)

    return int(nodes[best_idx])