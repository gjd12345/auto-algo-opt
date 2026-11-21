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

    nodes = np.asarray(unvisited_nodes)
    n = nodes.size

    d_cur = distance_matrix[current_node][nodes].astype(float)
    d_dep = distance_matrix[depot][nodes].astype(float)
    dem = demands[nodes].astype(float)

    cap = float(rest_capacity)
    if cap <= 0.0:
        cap = 1.0
    fill = dem / cap  # dimensionless demand fraction

    if current_node == depot:
        # Outside-in seed: farthest customer, modulated by how much it fills the vehicle.
        # Use dimensionless radial distance normalized by max radial distance.
        dmax = float(np.max(d_dep)) if n > 0 else 0.0
        if dmax <= 0.0:
            dmax = 1.0
        radial = d_dep / dmax
        score = -(radial + 0.35 * fill)
    else:
        # Scale-free scale: use local distance reference
        scale = float(np.max(d_cur))
        if scale <= 0.0:
            scale = float(np.max(d_dep))
        if scale <= 0.0:
            scale = 1.0
        alpha_mid = 0.6
        beta_fill = 0.4
        score = (d_cur / scale) - alpha_mid * (d_dep / scale) - beta_fill * fill

    best = int(np.argmin(score))
    return int(nodes[best])