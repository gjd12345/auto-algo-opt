def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return 0

    nodes = np.asarray(unvisited_nodes)
    dem = demands[nodes].astype(float)

    d_cur = distance_matrix[current_node][nodes].astype(float)
    d_dep = distance_matrix[depot][nodes].astype(float)
    d_cur_dep = float(distance_matrix[current_node][depot])

    d_all = distance_matrix[nodes][:, nodes].astype(float)
    scale = float(np.max(d_all)) if d_all.size > 0 else 1.0
    if scale <= 0.0:
        scale = 1.0

    rest = float(rest_capacity)
    if rest <= 0.0:
        rest = 1.0

    if current_node == depot:
        rel_dem = dem / rest
        rel_dist = d_dep / scale
        score = rel_dist - 0.40 * rel_dem
        return int(nodes[int(np.argmin(score))])

    axis = d_cur_dep + d_dep
    rho = d_cur / np.maximum(axis, 1e-12)

    alpha = 0.78
    linear_pull = (d_cur - alpha * d_dep) / scale

    resid = rest - dem
    resid_frac = np.abs(resid) / rest
    fill_bonus = -0.12 * (1.0 - np.minimum(resid_frac, 1.0))

    score = linear_pull + 0.55 * rho + fill_bonus
    best_k = int(np.argmin(score))

    # Capacity-adaptive early-return threshold.
    mean_dem = float(np.mean(dem)) if dem.size > 0 else 0.0
    load_frac = mean_dem / rest if rest > 0.0 else 0.0
    if load_frac > 1.0:
        load_frac = 1.0
    tau = 0.52 + 0.20 * load_frac

    if float(rho[best_k]) > tau:
        return 0

    return int(nodes[best_k])