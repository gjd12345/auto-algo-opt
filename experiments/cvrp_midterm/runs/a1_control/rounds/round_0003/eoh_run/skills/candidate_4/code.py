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

    # Current direction vector: from depot to current node (or depot->itself if at depot)
    cur_vec = distance_matrix[depot][current_node]
    # Use distances to derive a scalar directional alignment proxy.
    # cos angle between (depot->current) and (current->node) via law of cosines on triangle.
    d_dc = distance_matrix[depot][current_node]
    d_dn = distance_matrix[depot][unvisited_nodes]
    d_cn = distance_matrix[current_node][unvisited_nodes]

    # Alignment: prefer nodes that continue outward from current heading.
    # Larger forward_alignment means node is "ahead" of current direction.
    # Using dot-product-style proxy from triangle distances.
    eps = 1e-9
    if d_dc < eps:
        forward = d_dn  # at depot, prefer farther nodes to build a route
    else:
        forward = (d_dc * d_dc + d_cn * d_cn - d_dn * d_dn) / (2.0 * d_dc + eps)

    # Capacity utilization: prefer nodes that tightly fill remaining capacity.
    dem = demands[unvisited_nodes]
    slack = rest_capacity - dem
    # Reward small slack (tight fit) and penalize overshoot waste.
    util = 1.0 - slack / (rest_capacity + 1.0)

    # Radial penalty: mildly discourage returning very close to depot too early.
    radial_penalty = d_dn / (rest_capacity + 1.0)

    score = -forward + 0.7 * util - 0.3 * radial_penalty - 0.15 * d_cn

    idx = int(np.argmax(score))
    return int(unvisited_nodes[idx])