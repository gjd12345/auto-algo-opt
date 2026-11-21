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

    d_cur = distance_matrix[current_node][unvisited_nodes].astype(float)
    d_dep = distance_matrix[depot][unvisited_nodes].astype(float)

    span = float(np.max(d_cur) - np.min(d_cur)) if d_cur.size > 1 else 0.0
    norm = span + 1e-12

    # Multiplicative "value per unit detour" form instead of an additive score.
    # Detour: extra distance paid relative to the closest remaining customer.
    detour = d_cur - float(np.min(d_cur))
    detour_frac = detour / norm

    # Depot-proximity benefit, guarded against zero distance.
    dep_benefit = 1.0 / (d_dep / (span + 1.0) + 1e-9)

    # Demand density gating: prefer customers that consume a good chunk of
    # the remaining capacity while still being nearby.
    dem = demands[unvisited_nodes].astype(float)
    cap = rest_capacity + 1e-12
    fill = dem / cap
    density = fill / (1.0 + detour_frac)

    # Regret-ratio: larger benefit per unit detour, scaled by demand density.
    score = (dep_benefit * density) / (1.0 + detour_frac)

    idx = int(np.argmax(score))
    return int(unvisited_nodes[idx])