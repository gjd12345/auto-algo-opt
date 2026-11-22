def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    dist_current = distance_matrix[current_node][unvisited_nodes]
    dist_dest = distance_matrix[destination_node][unvisited_nodes]

    # Compute vector directions (approximate using coordinate differences if available, else use distances)
    # Use distances to compute cosine similarity: cos(theta) = (a^2 + b^2 - c^2) / (2ab)
    # where a = dist_current, b = dist_dest, c = distance between current and dest
    direct_dist = distance_matrix[current_node][destination_node]

    # Avoid division by zero
    denom = 2 * dist_current * dist_dest + 1e-10
    cos_theta = (dist_current**2 + dist_dest**2 - direct_dist**2) / denom
    # Penalize large deviations: cos_theta close to 1 means straight line, -1 means opposite direction
    angle_penalty = np.where(cos_theta < 0.5, 0.3 * (0.5 - cos_theta) * dist_current, 0.0)

    # Score: balance current proximity (weight 0.7) and destination proximity (weight 0.3), minus angle penalty
    scores = 0.3 * dist_dest - 0.7 * dist_current - angle_penalty

    return unvisited_nodes[np.argmax(scores)]
