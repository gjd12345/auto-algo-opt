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

    nodes = np.asarray(unvisited_nodes, dtype=int)
    d_cur = distance_matrix[current_node][nodes].astype(float)
    d_dep = distance_matrix[depot][nodes].astype(float)
    dem = demands[nodes].astype(float)

    cap = float(max(rest_capacity, 0.0))
    total_dem = float(np.sum(dem)) if dem.size > 0 else 0.0

    # Quadratic scoring: penalize squared local distance and squared depot distance,
    # and prefer demands that fit tightly with the remaining capacity.
    # Larger remaining capacity after serving => better packing; normalized term.
    cap_after = cap - dem
    cap_after_norm = cap_after / (cap + 1e-9)

    # Demand fit: reward serving demand close to a target fraction of capacity,
    # but also allow the largest possible demand to keep routes short.
    # Use a convex term: (cap - dem)^2 scaled down by depot distance.
    depot_scale = 1.0 + d_dep
    gap = (cap - dem) / depot_scale

    # Weighted convex combination.
    score = 1.0 * d_cur * d_cur - 0.35 * d_dep * d_dep \
            + 0.02 * (gap * gap) - 0.5 * cap_after_norm * d_dep / depot_scale

    # Soft early-return: if depot is very close and current route has loaded a
    # substantial share of demand, consider going back instead of detouring.
    if current_node != depot:
        d_home = float(distance_matrix[current_node][depot])
        min_local = float(np.min(d_cur))
        served = total_dem - float(np.sum(dem))
        if d_home <= 1.05 * min_local and served > 0.0 and rest_capacity < 0.25 * (served + cap):
            return 0

    best_idx = int(np.argmin(score))
    return int(nodes[best_idx])