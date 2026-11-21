def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
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

    # Depot-start: radial-load seed (dimensionless, scale-free).
    if current_node == depot:
        rel_dem = dem / rest
        rel_dist = d_dep / scale
        score = -(rel_dist + 0.5 * rel_dem)
        return int(nodes[int(np.argmin(score))])

    # Mid-route: Clarke-Wright normalized saving combined with capacity-fill.
    denom = d_dep + d_cur  # current_node is the last visited, so use d(i,j)=d_cur
    # Normalized saving relative to depot: sigma(i,j) = (d0i + d0j - dij)/(d0i + d0j)
    # Here d0i = d_cur_dep (fixed), d0j = d_dep, dij = d_cur.
    sigma = (d_cur_dep + d_dep - d_cur) / np.maximum(d_cur_dep + d_dep, 1e-12)

    # Capacity-fill term: reward candidates that match remaining capacity well.
    fill = dem / rest
    fill_term = -0.12 * np.minimum(fill, 1.0)  # calibrated low weight

    # Local normalized distance tie-break.
    local = d_cur / (d_cur_dep + scale)

    # score: smaller is better. Reward larger saving (so use -sigma) plus fill.
    score = -sigma + fill_term + 1e-3 * local

    best_k = int(np.argmin(score))

    # Voluntary early-return gate: if the best candidate's normalized saving
    # is too small, cross the depot (return 0) rather than bridge across it.
    tau = 0.25
    if float(sigma[best_k]) < tau:
        return 0

    return int(nodes[best_k])