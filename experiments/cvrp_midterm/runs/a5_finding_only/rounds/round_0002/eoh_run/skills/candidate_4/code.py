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
    d_cur_dep = float(distance_matrix[current_node][depot])

    # Relative insertion cost normalised by the direct return chord.
    # Keeps only the relative part -> scale-invariant.
    denom = d_cur_dep if d_cur_dep > 1e-12 else 1.0
    elong = (d_cur + d_dep) / denom - 1.0

    # Depot pull: normalise by row scale so it stays relative.
    scale = float(np.mean(d_dep)) if len(d_dep) > 0 else 1.0
    if scale <= 1e-12:
        scale = 1.0
    far_pull = d_dep / scale

    # Capacity packing reward: relative demand fraction of remaining capacity.
    dem = demands[unvisited_nodes].astype(float)
    cap = float(rest_capacity) + 1e-9
    load_frac = dem / cap

    score = elong - 0.55 * far_pull - 0.85 * load_frac
    return int(unvisited_nodes[np.argmin(score)])