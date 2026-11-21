def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes].astype(float)

    # span-proportional normalisation (scale invariant)
    span = max(float(distance_matrix[depot].max()), 1e-12)
    span_cur = max(float(d_cur.max()), 1e-12)
    span_dep = max(float(d_dep.max()), 1e-12)
    span_dem = max(float(dem.max()), 1e-12)

    nc = d_cur / span_cur
    nd = d_dep / span_dep
    nq = dem / span_dem

    # scale-free load level: 1 = empty, 0 = full
    load = 0.0
    if rest_capacity > 0:
        load = min(1.0, max(0.0, rest_capacity / (rest_capacity + dem.sum())))
    # use a demand-based proxy for vehicle fill that is scale invariant
    fill = 0.0
    if rest_capacity > 0:
        fill = max(0.0, min(1.0, 1.0 - (dem.max() / rest_capacity)))
    # savings-like term: prefer far-from-depot customers when light, near when heavy
    savings = (nd - nc)

    # priority: small score is better
    score = (
        1.00 * nc
        + 0.35 * nd
        + 0.25 * nq
        + (0.20 * savings) * (0.5 + 0.5 * fill)
    )

    score = np.asarray(score, dtype=float)
    score[~np.isfinite(score)] = np.inf
    idx = int(np.argmin(score))
    return int(unvisited_nodes[idx])