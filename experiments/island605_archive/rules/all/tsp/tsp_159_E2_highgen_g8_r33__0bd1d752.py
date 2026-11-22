def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    # Compute distances from current node and destination
    current_dists = distance_matrix[current_node][unvisited_nodes]
    return_dists = distance_matrix[destination_node][unvisited_nodes]

    # Compute dispersion penalty: for each unvisited node, mean distance to all other unvisited nodes
    penalty = np.array([np.mean(distance_matrix[node][unvisited_nodes]) for node in unvisited_nodes])

    # Weighted score: favor nodes far from current (exploration), but close to destination and with low dispersion
    alpha = 1.2   # weight for current distance (exploration)
    beta = 0.8    # weight for return distance
    gamma = 0.4   # weight for dispersion penalty
    scores = -alpha * current_dists + beta * return_dists + gamma * penalty

    # Fallback: if best score is extreme (lowest 10th percentile), use farthest insertion
    best_idx = np.argmax(scores)
    if scores[best_idx] < np.percentile(scores, 10):
        best_idx = np.argmax(current_dists)

    return unvisited_nodes[best_idx]
