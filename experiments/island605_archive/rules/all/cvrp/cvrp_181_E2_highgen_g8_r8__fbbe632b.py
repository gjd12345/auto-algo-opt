def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    dists = distance_matrix[current_node][unvisited_nodes]

    # For each unvisited node, compute the average distance to all other unvisited nodes
    avg_dists = np.array([
        np.mean(distance_matrix[node][unvisited_nodes][distance_matrix[node][unvisited_nodes] > 0])
        if np.any(distance_matrix[node][unvisited_nodes] > 0) else np.inf
        for node in unvisited_nodes
    ])

    # Compute a score: higher distance from current node is penalized, higher average connectivity is rewarded
    # Normalize to avoid scale issues
    max_dists = np.max(dists) if np.max(dists) > 0 else 1
    max_avg = np.max(avg_dists) if np.max(avg_dists) > 0 else 1
    score = (dists / max_dists) - 0.5 * (avg_dists / max_avg)

    # Select the node with the smallest score
    return unvisited_nodes[np.argmin(score)]
