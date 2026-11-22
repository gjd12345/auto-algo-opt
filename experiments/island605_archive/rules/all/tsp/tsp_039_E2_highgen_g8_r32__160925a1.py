def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    dist_current = distance_matrix[current_node][unvisited_nodes]
    dist_dest = distance_matrix[destination_node][unvisited_nodes]
    n_remaining = len(unvisited_nodes)

    # Nearest neighbor distance among unvisited nodes from current node
    nn_dist = np.min(dist_current[dist_current > 0]) if np.any(dist_current > 0) else 1.0

    # Penalty: ratio of current edge to nearest neighbor distance
    penalty = dist_current / nn_dist

    # Dynamic weight: penalty weight decreases as fewer nodes remain (inverted from original)
    weight = 0.5 + (0.5 / n_remaining)

    # Score: favor nodes far from destination, penalize long current edges with dynamic weight
    score = dist_dest - weight * dist_current * penalty

    best_idx = np.argmax(score)
    return int(unvisited_nodes[best_idx])
