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
    unvisited = np.asarray(unvisited_nodes, dtype=np.int64)
    if unvisited.size == 0:
        return 0

    d_cur = distance_matrix[current_node][unvisited]
    d_dep = distance_matrix[depot][unvisited]

    # Radial progress: how much closer to the depot the candidate is
    # relative to the current node's own depot distance. Positive means
    # the candidate pulls the route back toward the depot (usually a bad
    # idea mid-route), negative means it pushes outward.
    d_cur_dep = float(distance_matrix[current_node][depot])
    radial = d_dep - d_cur_dep  # negative => outward, positive => inward

    # Primary term: distance to current node scaled by how much the
    # candidate pulls the route back toward the depot. Inward moves are
    # penalised; outward moves are only mildly favoured so we do not
    # chase far-away outliers.
    inward = np.maximum(radial, 0.0)
    outward = np.maximum(-radial, 0.0)
    scale = 1.0 + 0.35 * inward - 0.15 * outward
    scale = np.maximum(scale, 0.1)
    primary = d_cur * scale

    order = np.argsort(primary)
    best = order[0]

    # Second stage: within a tight band, prefer smaller depot distance so
    # the vehicle builds routes from the depot outward compactly, then
    # tie-break by nearest.
    band = primary[best] + 0.02 * (primary[best] + 1.0)
    close_mask = primary <= band
    close = unvisited[close_mask]
    if close.size > 1:
        close_dep = distance_matrix[depot][close]
        min_dep = close_dep.min()
        near = close[close_dep <= min_dep + 1e-9]
        if near.size == 1:
            return int(near[0])
        near_d = distance_matrix[current_node][near]
        return int(near[np.argmin(near_d)])
    return int(unvisited[best])