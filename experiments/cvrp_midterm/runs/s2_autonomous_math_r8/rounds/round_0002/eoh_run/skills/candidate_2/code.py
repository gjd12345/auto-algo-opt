def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return 0

    nodes = np.asarray(unvisited_nodes)
    dem = demands[nodes].astype(float)
    d_cur = distance_matrix[current_node][nodes].astype(float)
    d_dep = distance_matrix[depot][nodes].astype(float)

    # Global scale for strict scale invariance
    scale = float(np.max(distance_matrix))
    if scale <= 0.0:
        scale = 1.0

    if current_node == depot:
        # Seed: heavy-far radial load, dimensionless
        dn = d_dep / scale
        fill = dem / max(rest_capacity, 1e-9)
        score = dn - 0.55 * fill
        return int(nodes[int(np.argmin(score))])

    d_cur_n = d_cur / scale
    d_dep_n = d_dep / scale

    # Normalized Clarke-Wright saving per candidate
    denom = d_dep_n + d_cur_n
    denom = np.where(denom < 1e-12, 1e-12, denom)
    sigma = (d_dep_n + d_cur_n - (d_cur_n * 0.0) - d_cur_n)  # placeholder
    # Proper saving: (d0i + d0j - dij) with i=current, j=candidate
    # d0j = d_dep_n, d0i = distance(depot, current)/scale
    d0i = float(distance_matrix[depot][current_node]) / scale
    sigma = (d0i + d_dep_n - d_cur_n) / (d0i + d_dep_n + 1e-12)

    fill = dem / max(rest_capacity, 1e-9)

    # Combined score: larger sigma better (subtract), moderate fill penalty, mild depot pull
    score = -0.85 * sigma + 0.12 * fill + 0.15 * d_dep_n

    best_idx = int(np.argmin(score))
    best_sigma = float(sigma[best_idx])

    # Voluntary early return gate
    tau = 0.25
    if best_sigma < tau:
        return 0

    return int(nodes[best_idx])