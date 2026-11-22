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
    dist_from_current = distance_matrix[current_node][unvisited_nodes]

    # Compute average distance from each candidate to all other unvisited nodes
    avg_dist_to_others = np.array([
        distance_matrix[candidate][unvisited_nodes].mean()
        for candidate in unvisited_nodes
    ])

    # Score: prefer candidates far from others on average, but close to current
    score = avg_dist_to_others - dist_from_current
    best_idx = np.argmax(score)
    return int(unvisited_nodes[best_idx])
