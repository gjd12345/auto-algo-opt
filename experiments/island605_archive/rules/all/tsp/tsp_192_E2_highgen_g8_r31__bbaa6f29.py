def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    # Compute distances from current node to all unvisited nodes
    distances = distance_matrix[current_node][unvisited_nodes]
    # For each candidate, compute the average distance to other unvisited nodes (excluding itself)
    scores = np.zeros(len(unvisited_nodes))
    for i, node in enumerate(unvisited_nodes):
        other_distances = distance_matrix[node][unvisited_nodes]
        # Exclude self-distance (zero) from average
        avg_other_dist = np.mean(np.delete(other_distances, i))
        # Score: distance + penalty if neighbors are close (i.e., small avg_other_dist)
        scores[i] = distances[i] + 0.3 * (1.0 / (avg_other_dist + 1e-6))
    return unvisited_nodes[np.argmin(scores)]
