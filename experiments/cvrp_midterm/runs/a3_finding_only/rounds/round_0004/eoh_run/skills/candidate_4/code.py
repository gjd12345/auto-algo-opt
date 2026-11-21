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
    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    d_cur_dep = distance_matrix[current_node][depot]
    dem = demands[unvisited_nodes]

    cap = max(rest_capacity, 1e-9)

    # Scale-invariant shape of the d(cur,.) triangle relative to d(dep,.) and d(cur,dep):
    # use the law-of-cosines-like alignment proxy without needing coordinates.
    # cos_angle ~ (d_cur^2 + d_cur_dep^2 - d_dep^2) / (2 * d_cur * d_cur_dep)
    denom = 2.0 * d_cur * max(d_cur_dep, 1e-9)
    cos_ang = np.where(denom > 0, (d_cur * d_cur + d_cur_dep * d_cur_dep - d_dep * d_dep) / denom, 1.0)
    cos_ang = np.clip(cos_ang, -1.0, 1.0)

    # Angular pull: strongly prefer candidates aligned with the depot-outward direction
    # (cos_ang near +1) so the route sweeps outward rather than zig-zagging.
    angular = 0.5 * (1.0 - cos_ang)

    # Normalized demand pressure in [0,1): prefer larger demands when capacity is scarce.
    util = dem / (cap + dem)

    # Single normalized blend: angular shape plus capacity pressure.
    score = angular - 0.55 * util

    return int(unvisited_nodes[np.argmin(score)])