def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) <= 2:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    dist_from_current = distance_matrix[current_node][unvisited_nodes]
    dist_to_dest = distance_matrix[destination_node][unvisited_nodes]

    # Compute angle-based penalty for each candidate
    penalty = np.zeros(len(unvisited_nodes))
    for i, u in enumerate(unvisited_nodes):
        # Find neighbor distances from candidate u (excluding self)
        neighbors = np.delete(distance_matrix[u], u)
        # Use a small set of nearest neighbors for local smoothness
        k = min(5, len(neighbors))
        nearest_neighbors = np.partition(neighbors, k)[:k]
        avg_near = np.mean(nearest_neighbors) if k > 0 else 0
        if avg_near > 0 and dist_from_current[i] > 0:
            # Penalize if current->u edge is much longer than local average
            penalty[i] = dist_from_current[i] / avg_near

    # Farthest-insertion component: prefer nodes far from destination
    # Combined with penalty to avoid locally long edges
    epsilon = 1e-10
    scores = dist_to_dest / (dist_from_current + epsilon) * (1.0 / (1.0 + penalty))

    best_idx = np.argmax(scores)
    return unvisited_nodes[best_idx]
