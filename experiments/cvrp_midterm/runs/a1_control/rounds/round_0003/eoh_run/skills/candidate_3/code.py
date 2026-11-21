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

    depot_d = distance_matrix[depot]

    # Pick a stable anchor: farthest node from depot (all nodes, not only unvisited)
    anchor_candidates = np.where(depot_d > 0)[0]
    if anchor_candidates.size == 0:
        return int(unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])])
    anchor = int(anchor_candidates[np.argmax(depot_d[anchor_candidates])])
    da = float(depot_d[anchor])
    if da <= 0.0:
        return int(unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])])

    def polar(node_d0, node_d1):
        x = (node_d0 * node_d0 + da * da - node_d1 * node_d1) / (2.0 * da)
        y2 = np.maximum(node_d0 * node_d0 - x * x, 0.0)
        return x, np.sqrt(y2)

    d0 = depot_d[unvisited_nodes]
    d1 = distance_matrix[anchor][unvisited_nodes]
    x, y = polar(d0, d1)
    angle = np.arctan2(y, x)

    # Heading angle of current node
    if current_node == depot:
        cur_angle = None
    else:
        cd0 = float(depot_d[current_node])
        cd1 = float(distance_matrix[anchor][current_node])
        if cd0 > 0.0:
            cx, cy = polar(cd0, cd1)
            cur_angle = float(np.arctan2(cy, cx))
        else:
            cur_angle = None

    # Candidate distances to current node
    dc = distance_matrix[current_node][unvisited_nodes]

    # Demand fill ratio
    dem = demands[unvisited_nodes]
    fill = dem / (rest_capacity + 1.0)

    if cur_angle is None:
        # Start of a new route: prefer small |angle| relative to anchor axis,
        # moderate depot distance and short hops from depot
        score = 0.45 * np.abs(angle) + 0.30 * d0 + 0.25 * dc - 0.20 * fill
    else:
        delta = angle - cur_angle
        delta = (delta + np.pi) % (2.0 * np.pi) - np.pi
        forward = np.where(delta >= 0.0, delta, 2.0 * np.pi + delta)
        # Blend forward sweep with immediate hop cost, radial pull, and fill
        score = 0.50 * forward + 0.55 * dc + 0.20 * d0 - 0.30 * fill

    idx = int(np.argmin(score))
    return int(unvisited_nodes[idx])