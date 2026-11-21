def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction.

    Args:
        current_node:    index of the current node (0 = depot)
        depot:           index of the depot (always 0)
        unvisited_nodes: array of feasible unvisited customer indices
                         (already filtered to satisfy remaining capacity)
        rest_capacity:   remaining vehicle capacity
        demands:         demand of every node (index 0 = depot demand = 0)
        distance_matrix: pairwise Euclidean distance matrix
    Returns:
        Index of the next node to visit, or 0 to return to the depot early.
    """
    if unvisited_nodes.size == 0:
        return 0

    nodes = np.asarray(unvisited_nodes)
    d_cur = distance_matrix[current_node][nodes].astype(float)
    d_dep = distance_matrix[depot][nodes].astype(float)
    dem = demands[nodes].astype(float)

    # Scale-free distance scale for normalization.
    scale = float(np.mean(d_dep) + np.mean(d_cur) + 1e-12)

    # Elongation ratio rho = d_cur / (d0i + d0j), scale-free.
    d0c = float(distance_matrix[depot][current_node]) if current_node != depot else 0.0
    pair = np.maximum(d_dep + d0c, 1e-12)
    rho = d_cur / pair

    # State-only capacity pressure drives the depot-pull phase transition.
    mean_dem = float(np.mean(dem)) if dem.size > 0 else 0.0
    pressure = min(1.0, mean_dem / (rest_capacity + 1e-12))

    # Decaying depot pull: sweep outward early, spiral inward near-full.
    alpha_0 = 1.02
    alpha_1 = 0.85
    alpha_eff = alpha_0 - alpha_1 * pressure

    radial = (d_cur - alpha_eff * d_dep) / scale

    # Calibrated fill bonus (dimensionless).
    fill = dem / (rest_capacity + 1e-12)
    beta = 0.11

    # Law-of-Cosines angular coherence at non-depot node.
    if current_node != depot:
        denom_cos = np.maximum(2.0 * d_dep * d0c, 1e-12)
        cos_t = np.clip((d_dep * d_dep + d0c * d0c - d_cur * d_cur) / denom_cos, -1.0, 1.0)
        w_cos = 0.18
    else:
        cos_t = np.zeros_like(d_cur)
        w_cos = 0.0

    score = radial + 0.35 * rho - beta * fill - w_cos * cos_t

    # Two-phase depot-start policy.
    if current_node == depot:
        total_dem = float(np.sum(dem))
        rem_routes = total_dem / (rest_capacity + 1e-12)
        if rem_routes > 7.0:
            # Outside-in: prefer far heavy nodes.
            score = -d_dep / scale - 0.25 * fill
        else:
            # Compact radial-load seed.
            score = d_dep / scale - 0.30 * fill
        return int(nodes[int(np.argmin(score))])

    # Capacity-adaptive early return.
    best_dem = float(np.max(dem))
    tau = 0.25 + 0.50 * pressure

    if best_dem > 0.55 * rest_capacity:
        best_idx_local = int(np.argmin(score))
        rho_best = float(rho[best_idx_local])
        if (1.0 - rho_best) < tau:
            return 0

    return int(nodes[int(np.argmin(score))])