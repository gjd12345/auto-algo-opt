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

    # Scale-free distance scale for normalization (never divide demands by distance).
    scale = float(np.mean(d_dep) + np.mean(d_cur) + 1e-12)

    # Elongation ratio rho = d_cur / (d0i + d0j), scale-free
    denom = np.maximum(d_dep + d_dep, 1e-12)  # d(0,j) + d(0,j) guards zero
    # Use depot-to-node plus depot-to-current as a proxy for the depot detour pair
    d0c = distance_matrix[depot][current_node] if current_node != depot else 0.0
    pair = np.maximum(d_dep + d0c, 1e-12)
    rho = d_cur / pair

    # Normalized linear radial pull
    alpha = 0.75
    radial = (d_cur - alpha * d_dep) / scale

    # Capacity-fill reward (dimensionless)
    fill = dem / (rest_capacity + 1e-12)
    beta = 0.10

    score = radial + 0.5 * rho - beta * fill

    # Capacity-adaptive early-return threshold
    if current_node != depot:
        best_dem = float(np.max(dem))
        mean_dem = float(np.mean(dem))
        fill_ratio = max(best_dem, mean_dem) / (rest_capacity + 1e-12)
        tau = 0.30 + 0.15 * min(fill_ratio, 1.0)

        # If the current node is close to depot and vehicle is near-full, return early
        if best_dem > 0.55 * rest_capacity:
            best_idx_local = int(np.argmin(score))
            rho_best = float(rho[best_idx_local])
            if rho_best > (0.72 - 0.10 * min(fill_ratio, 1.0)):
                return 0

    return int(nodes[int(np.argmin(score))])