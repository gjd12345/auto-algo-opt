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
    dm = distance_matrix
    idx = unvisited_nodes

    span = float(np.max(dm))
    if not np.isfinite(span) or span <= 0.0:
        span = 1.0

    d_cur = dm[current_node][idx]
    d_dep = dm[depot][idx]
    dem = demands[idx]

    travel = d_cur / span            # local move cost
    depot_term = d_dep / span        # defer near-depot customers

    cap = float(rest_capacity)
    if cap > 0.0:
        load_fill = dem / cap
        cap_pressure = (dem / cap) ** 2
    else:
        load_fill = np.zeros_like(dem, dtype=np.float64)
        cap_pressure = np.zeros_like(dem, dtype=np.float64)

    # Stronger demand packing and depot deferral than the parent rule,
    # plus a quadratic capacity-pressure term to avoid leaving usable
    # capacity stranded late in a route.
    score = travel + 0.45 * depot_term - 0.35 * load_fill - 0.20 * cap_pressure

    return int(idx[np.argmin(score)])