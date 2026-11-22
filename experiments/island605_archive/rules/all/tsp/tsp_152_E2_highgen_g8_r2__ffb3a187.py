def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    n_remaining = len(unvisited_nodes)
    if n_remaining <= 3:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    dist_from_current = distance_matrix[current_node][unvisited_nodes]
    dist_to_dest = distance_matrix[destination_node][unvisited_nodes]
    # Penalize nodes that are close to destination (to avoid leaving distant clusters)
    # but also penalize very long edges from current node (to avoid crossings)
    # Use product: high score for nodes far from destination and moderately far from current
    # Add small epsilon to avoid division by zero
    scores = dist_from_current / (dist_to_dest + 1e-10)
    # Additionally, penalize candidates where dist_from_current is very large relative to local neighborhood
    # Compute mean distance from current to all unvisited nodes
    mean_dist = np.mean(dist_from_current)
    penalty = np.where(dist_from_current > 2.0 * mean_dist, dist_from_current * 0.5, 0.0)
    scores += penalty
    # Select the node with lowest score (lowest weighted combination)
    return unvisited_nodes[np.argmin(scores)]
