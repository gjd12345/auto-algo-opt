def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a TSP greedy construction.

    Args:
        current_node: ID of the current node
        destination_node: ID of the destination (return) node
        unvisited_nodes: array of unvisited node IDs
        distance_matrix: pairwise distance matrix between all nodes
    Returns:
        next_node: ID of the next node to visit
    """
    if len(unvisited_nodes) <= 3:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    distances_current = distance_matrix[current_node][unvisited_nodes]
    dest_distances = distance_matrix[destination_node][unvisited_nodes]

    best_score = -np.inf
    best_idx = 0

    for i, candidate in enumerate(unvisited_nodes):
        candidate_dists = distance_matrix[candidate][unvisited_nodes]
        # Variance of distances from candidate to all unvisited nodes (spread measure)
        variance = np.var(candidate_dists) + 1e-10
        # Current edge cost
        current_cost = distances_current[i] + 1e-10
        # Distance to destination (penalize being close to destination too early)
        dest_cost = dest_distances[i] + 1e-10

        # Score: reward high variance (exploration), penalize current cost and early destination proximity
        score = (variance * dest_cost) / (current_cost ** 2)

        if score > best_score:
            best_score = score
            best_idx = i

    return int(unvisited_nodes[best_idx])
