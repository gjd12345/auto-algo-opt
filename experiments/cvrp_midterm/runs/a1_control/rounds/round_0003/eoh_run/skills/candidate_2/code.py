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

    # Recover approximate coordinates from the distance matrix via classic
    # trilateration against the depot and first customer (depot at origin).
    n = distance_matrix.shape[0]
    depot_d = distance_matrix[depot]
    # Choose an anchor customer distinct from depot with max depot distance
    anchor_candidates = np.where(depot_d > 0)[0]
    if anchor_candidates.size == 0:
        return int(unvisited_nodes[0])
    anchor = int(anchor_candidates[np.argmax(depot_d[anchor_candidates])])
    da = float(depot_d[anchor])

    if da <= 0.0:
        return int(unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])])

    # For each unvisited node compute distance from depot and from anchor
    d0 = depot_d[unvisited_nodes]
    d1 = distance_matrix[anchor][unvisited_nodes]

    # x coordinate along anchor axis
    x = (d0 * d0 + da * da - d1 * d1) / (2.0 * da)
    # y coordinate magnitude
    y2 = d0 * d0 - x * x
    y2 = np.maximum(y2, 0.0)
    y = np.sqrt(y2)

    # Angle in polar coordinates around depot (anchor defines zero angle)
    angle = np.arctan2(y, x)  # in [-pi, pi]

    # Current node angle (if not depot)
    if current_node == depot:
        cur_angle = None
    else:
        cd0 = float(depot_d[current_node])
        cd1 = float(distance_matrix[anchor][current_node])
        if cd0 > 0.0:
            cx = (cd0 * cd0 + da * da - cd1 * cd1) / (2.0 * da)
            cy2 = max(cd0 * cd0 - cx * cx, 0.0)
            cy = np.sqrt(cy2)
            cur_angle = float(np.arctan2(cy, cx))
        else:
            cur_angle = None

    # Sweep priority: forward angular progression from current node's direction
    if cur_angle is None:
        # Starting fresh from depot: go to nearest angularly consistent far node
        # radial-first sweep, prefer small angle magnitude then shorter radial
        sweep = np.abs(angle) * 0.5 + d0 * 0.5
    else:
        delta = angle - cur_angle
        # Wrap to (-pi, pi]
        delta = (delta + np.pi) % (2.0 * np.pi) - np.pi
        # Prefer small forward steps; penalize backward sweeps
        forward = np.where(delta >= 0.0, delta, 2.0 * np.pi + delta)
        sweep = forward + 0.10 * d0 + 0.05 * np.diff(
            np.concatenate(([0.0], np.zeros(1)))
        ).sum() if False else forward + 0.10 * d0

    # Capacity fill preference: mild bonus for larger demand relative to rest capacity
    dem = demands[unvisited_nodes]
    fill = dem / (rest_capacity + 1.0)

    # Blend sweep angular progression with radial and load cues
    score = sweep + 0.35 * d0 + 0.20 * distance_matrix[current_node][unvisited_nodes] - 0.15 * fill

    idx = int(np.argmin(score))
    return int(unvisited_nodes[idx])