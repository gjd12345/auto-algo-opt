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
    # If only one unvisited node remains, return it directly
    if len(unvisited_nodes) == 1:
        return unvisited_nodes[0]

    # Get distances from current node and from destination for all unvisited nodes
    dist_from_current = distance_matrix[current_node][unvisited_nodes]
    dist_from_destination = distance_matrix[destination_node][unvisited_nodes]

    # Compute a combined score: weighted sum
    # Alpha weights nearest-neighbor smoothness, beta weights farthest-insertion priority
    alpha = 0.6
    beta = 0.4
    # Normalize distances to avoid scale bias
    max_current = np.max(dist_from_current) if np.max(dist_from_current) > 0 else 1
    max_dest = np.max(dist_from_destination) if np.max(dist_from_destination) > 0 else 1
    score = alpha * (dist_from_current / max_current) + beta * (1 - dist_from_destination / max_dest)

    # Select the node with the smallest combined score
    best_idx = np.argmin(score)
    return unvisited_nodes[best_idx]
