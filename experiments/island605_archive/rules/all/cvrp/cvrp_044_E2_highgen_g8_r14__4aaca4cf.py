def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    # If no unvisited nodes remain, return to depot
    if len(unvisited_nodes) == 0:
        return depot

    # Get distances from current node and from depot
    dist_current = distance_matrix[current_node][unvisited_nodes]
    dist_depot = distance_matrix[depot][unvisited_nodes]

    # Parameter: weight for far-from-depot preference when starting a route
    FAR_WEIGHT = 1.5  # higher = more aggressive toward distant clusters
    # Parameter: balance between current-distance and depot-distance during route
    ALPHA = 0.7  # weight for current-distance; 1 = pure nearest, 0 = pure furthest from depot

    # If starting a new route, prefer customers far from depot, amplified by FAR_WEIGHT
    if current_node == depot:
        scores = dist_depot ** FAR_WEIGHT
        next_idx = np.argmax(scores)
        return unvisited_nodes[next_idx]

    # During the route: use a weighted combination
    # Normalize distances to avoid scale dominance
    if np.max(dist_current) > 0:
        norm_current = dist_current / np.max(dist_current)
    else:
        norm_current = dist_current
    if np.max(dist_depot) > 0:
        norm_depot = dist_depot / np.max(dist_depot)
    else:
        norm_depot = dist_depot

    # Score: lower is better; prefer small current distance and large depot distance
    scores = ALPHA * norm_current - (1 - ALPHA) * norm_depot
    # To avoid negative bias, shift to positive minimum
    scores = scores - np.min(scores)
    next_idx = np.argmin(scores)
    return unvisited_nodes[next_idx]
