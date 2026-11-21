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
    denom = d_cur + d_dep
    denom = np.where(denom <= 0, 1.0, denom)
    rel = d_cur / denom  # in [0, 1], scale-free proximity to current node

    # Capacity pressure in [0, 1]: 1 means vehicle is nearly empty of room.
    cap = rest_capacity if rest_capacity > 0 else 1.0
    dem_ratio = demands[unvisited_nodes] / cap
    dem_ratio = np.clip(dem_ratio, 0.0, 1.0)

    # Radial term: normalized distance to depot (per-candidate scale-free).
    radial = d_dep / denom  # = 1 - rel, share of detour to depot

    # Multiplicative urgency: as capacity fills, larger-demand customers
    # further from the depot become relatively more attractive to grab now.
    urgency = np.power(1.0 + radial, 1.0 + dem_ratio)
    score = rel * urgency
    return unvisited_nodes[np.argmin(score)]