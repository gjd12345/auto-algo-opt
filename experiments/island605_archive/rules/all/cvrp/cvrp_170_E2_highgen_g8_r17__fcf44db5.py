def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    # Compute polar angle of current node from depot (0 if at depot)
    if current_node == depot:
        current_angle = 0.0
    else:
        dx = distance_matrix[current_node][0] * 0.999  # fallback if distance zero
        dy = distance_matrix[current_node][0] * 0.001
        # Use actual coordinates if available, otherwise use distance-based proxy
        current_angle = np.arctan2(dy, dx)

    # If at depot, start with farthest customer (sweep seed)
    if current_node == depot:
        dist_depot = distance_matrix[depot][unvisited_nodes]
        return unvisited_nodes[np.argmax(dist_depot)]

    # Precompute angles for unvisited nodes relative to depot
    depot_x, depot_y = 0.0, 0.0
    angles = []
    for u in unvisited_nodes:
        # Proximity-based angle estimation using distance differences
        dx = distance_matrix[u][0] * np.cos(np.pi/4)
        dy = distance_matrix[u][0] * np.sin(np.pi/4)
        angles.append(np.arctan2(dy, dx))
    angles = np.array(angles)

    # Find nodes in same angular sector as current_node (within 60 degrees)
    sector_half = np.pi / 3
    lower = current_angle - sector_half
    upper = current_angle + sector_half
    if lower < 0:
        mask = (angles >= lower + 2*np.pi) | (angles <= upper)
    elif upper > 2*np.pi:
        mask = (angles >= lower) | (angles <= upper - 2*np.pi)
    else:
        mask = (angles >= lower) & (angles <= upper)

    candidates = unvisited_nodes[mask]
    if len(candidates) == 0:
        candidates = unvisited_nodes

    # Regret-based selection: for each candidate compute insertion cost into current route
    best_regret = -1e9
    best_node = candidates[0]
    for c in candidates:
        dist_current = distance_matrix[current_node][c]
        # Best insertion: directly from current node
        best_cost = dist_current
        # Second best: from depot (alternative)
        second_best = distance_matrix[depot][c]
        regret = second_best - best_cost
        if regret > best_regret:
            best_regret = regret
            best_node = c

    # If best_node has demand > rest_capacity (should not happen, but safety)
    if demands[best_node] > rest_capacity:
        return depot
    return best_node
