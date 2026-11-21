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

    scale = float(np.mean(d_dep) + np.mean(d_cur) + 1e-12)

    d0c = distance_matrix[depot][current_node] if current_node != depot else 0.0
    pair = np.maximum(d_dep + d0c, 1e-12)
    rho = d_cur / pair

    alpha = 0.75
    radial = (d_cur - alpha * d_dep) / scale

    fill = dem / (rest_capacity + 1e-12)
    beta = 0.10

    score = radial + 0.35 * rho - beta * fill

    d0i = d_dep
    d0j = d_dep
    dij = distance_matrix[nodes][:, nodes].astype(float) if nodes.size > 1 else np.zeros((1, 1))
    num = d0i[:, None] ** 2 + d0j[None, :] ** 2 - dij ** 2
    den = np.maximum(2.0 * d0i[:, None] * d0j[None, :], 1e-12)
    cos_theta = np.clip(num / den, -1.0, 1.0)

    w_cos = 0.20
    if nodes.size > 1:
        angular = np.mean(cos_theta, axis=1)
    else:
        angular = cos_theta[0, 0:1]
    score = score - w_cos * angular

    if current_node == depot:
        total_dem = float(np.sum(demands[np.asarray(unvisited_nodes)]))
        rem_routes = total_dem / (rest_capacity + 1e-12)
        if rem_routes > 7.0:
            outside_in = -(d_dep / scale) + 0.5 * (dem / (rest_capacity + 1e-12))
            score = score + 0.5 * outside_in
        else:
            compact = (d_dep / scale) - 0.5 * (dem / (rest_capacity + 1e-12))
            score = score + 0.5 * compact

    if current_node != depot:
        best_dem = float(np.max(dem))
        mean_dem = float(np.mean(dem))
        mean_dem_all = float(np.mean(demands[np.asarray(unvisited_nodes)])) if unvisited_nodes.size > 0 else 0.0
        fill_ratio = max(best_dem, mean_dem) / (rest_capacity + 1e-12)
        tau = 0.25 + 0.50 * min(1.0, mean_dem_all / (rest_capacity + 1e-12))

        best_idx_local = int(np.argmin(score))
        rho_best = float(rho[best_idx_local])
        if 1.0 - rho_best < tau:
            return 0

    return int(nodes[int(np.argmin(score))])