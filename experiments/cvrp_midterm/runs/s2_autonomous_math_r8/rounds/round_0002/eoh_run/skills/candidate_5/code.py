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

    w = 0.75
    beta_fill = 0.12
    tau = 0.25

    nodes = np.asarray(unvisited_nodes)
    n = nodes.size

    d_cur = distance_matrix[current_node][nodes].astype(float)
    d_dep = distance_matrix[depot][nodes].astype(float)
    dem = demands[nodes].astype(float)

    # Dimensionless local scale (avoid div-by-zero)
    scale = max(float(np.max(d_dep)), 1e-9)
    inv_rest = 1.0 / max(float(rest_capacity), 1e-9)

    # Base score: smaller is better. Depot pull (larger radial = better) subtracts.
    base = d_cur / scale - w * (d_dep / scale)

    # Capacity-fill bonus: prefer demand that fills remaining capacity.
    fill = dem * inv_rest  # in [0, ~1]
    base = base - beta_fill * fill

    # Small deterministic tie-breaker toward larger demand
    base = base - 1e-6 * fill

    best_idx = int(np.argmin(base))
    best_node = int(nodes[best_idx])

    # Voluntary early return to depot based on normalized Clarke-Wright saving.
    if current_node != depot:
        i = current_node
        j = best_node
        d0i = float(distance_matrix[depot][i])
        d0j = float(distance_matrix[depot][j])
        dij = float(distance_matrix[i][j])
        denom = d0i + d0j
        if denom > 1e-12:
            sigma = (d0i + d0j - dij) / denom
            if sigma < tau:
                return depot

    return best_node