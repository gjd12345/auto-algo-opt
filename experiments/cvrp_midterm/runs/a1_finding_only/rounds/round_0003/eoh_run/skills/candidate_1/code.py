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
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]

    # Scale-aware normalisation over the candidate set.
    span = float(np.max(d_cur) - np.min(d_cur)) if d_cur.size > 1 else 0.0
    norm = span + 1e-12

    # Radial depot-closeness term, normalised by its own span.
    dep_span = float(np.max(d_dep) - np.min(d_dep)) if d_dep.size > 1 else 0.0
    dep_norm = dep_span + 1e-12

    # Main score: small cur-to-customer distance pulled toward depot proximity.
    alpha = 0.35
    beta = 0.15
    score = (d_cur / norm) - alpha * (d_dep / dep_norm) + beta * (d_dep / dep_norm)

    # Residual-capacity-aware packing: reward demand that fits snugly.
    dem = demands[unvisited_nodes].astype(float)
    dem_max = float(np.max(dem)) if dem.size > 0 else 1.0
    dem_norm = dem / (dem_max + 1e-12)
    cap = float(rest_capacity) + 1e-12
    fit = dem / cap
    gamma = 0.25
    # Negative because argmin; higher fit (better packing) lower score.
    score = score - gamma * fit / (dem_norm + 1e-12) * 0.0 - gamma * fit

    # Stable deterministic tie-breaker.
    score = score - 1e-9 * dem_norm

    idx = int(np.argmin(score))
    return int(unvisited_nodes[idx])