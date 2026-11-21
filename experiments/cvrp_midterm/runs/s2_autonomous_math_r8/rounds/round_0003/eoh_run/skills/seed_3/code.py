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
        return int(depot)

    nodes = np.asarray(unvisited_nodes)
    n = nodes.size

    # Dimensionless scale from depot distances (strict scale invariance)
    d0_all = distance_matrix[depot].astype(float)
    scale = float(np.max(d0_all))
    if scale < 1e-12:
        scale = 1.0

    d_cur = distance_matrix[current_node][nodes].astype(float)
    d_dep = distance_matrix[depot][nodes].astype(float)
    dem = demands[nodes].astype(float)

    # Scale-invariant normalized quantities
    d_cur_n = d_cur / scale
    d_dep_n = d_dep / scale
    dem_n = dem / scale

    # ---------- Depot-start branch: seed with heavy-far / radial-load mix ----------
    if current_node == depot:
        # Larger is better: prefer far, heavy nodes
        seed_score = d_dep_n + 0.5 * dem_n
        best_idx = int(np.argmax(seed_score))
        return int(nodes[best_idx])

    # ---------- Mid-route branch ----------
    # Best candidate by closeness to current node, with moderate depot pull
    alpha_mid = 0.85  # depot pull weight (0.70-0.95)
    beta_fill = 0.12  # capacity-fill weight (0.05-0.18), calibrated

    denom = rest_capacity if rest_capacity > 1e-12 else 1e-12
    fill = dem / denom  # dimensionless fraction of remaining capacity

    # Smaller is better
    mid_score = d_cur_n - alpha_mid * d_dep_n + beta_fill * fill
    best_idx = int(np.argmin(mid_score))
    j = int(nodes[best_idx])

    # ---------- Voluntary early-return gate via normalized Clarke-Wright saving ----------
    tau = 0.25
    d0i = float(distance_matrix[depot][current_node])
    d0j = float(distance_matrix[depot][j])
    dij = float(distance_matrix[current_node][j])
    denom_cw = d0i + d0j
    if denom_cw < 1e-12:
        denom_cw = 1e-12
    sigma = (d0i + d0j - dij) / denom_cw
    if sigma < tau:
        return int(depot)

    return j