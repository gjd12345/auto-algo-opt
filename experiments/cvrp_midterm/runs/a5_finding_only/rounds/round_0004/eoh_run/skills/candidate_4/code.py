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
    if len(unvisited_nodes) == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes].astype(float)
    d_dep = distance_matrix[depot][unvisited_nodes].astype(float)
    dem = demands[unvisited_nodes].astype(float)

    cap = float(rest_capacity) + 1e-9
    load_frac = np.clip(dem / cap, 0.0, 1.0)

    # Detour cost of inserting candidate before returning to depot:
    # extra distance versus going straight back to the depot.
    # Always >= 0 by triangle inequality; scale-invariant when normalised
    # by the candidate's own depot distance.
    detour = d_cur + d_dep - float(distance_matrix[current_node][depot])
    detour = np.maximum(detour, 0.0)
    denom = d_dep + 1e-12
    detour_rel = detour / denom

    # Saving proxy: candidates far from depot are cheap to fold in now
    # (they will be expensive later), but expensive if the detour is large.
    # Reward filling remaining capacity: multiplicative capacity pressure.
    pressure = 1.0 + load_frac * load_frac  # in [1, 2]

    # Multiplicative score: (relative detour) / (capacity pressure).
    # Then subtract a radial reward so far-from-depot customers are
    # prioritised while capacity remains plentiful.
    mean_ddep = float(np.mean(d_dep)) if len(d_dep) > 0 else 1.0
    if mean_ddep <= 0:
        mean_ddep = 1.0
    rad = d_dep / mean_ddep  # larger for customers far from depot

    score = detour_rel / pressure - 0.5 * rad * (1.0 - 0.5 * load_frac)
    idx = int(np.argmin(score))
    return int(unvisited_nodes[idx])