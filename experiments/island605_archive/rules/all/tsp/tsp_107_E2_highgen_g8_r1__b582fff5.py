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
    current_dists = distance_matrix[current_node][unvisited_nodes]
    dest_dists = distance_matrix[destination_node][unvisited_nodes]

    # Avoid division by zero by adding a small epsilon
    ratio = current_dists / (dest_dists + 1e-10)
    diff = np.abs(current_dists - dest_dists)

    # Score: prefer lower ratio (close to current, far from destination) and larger difference
    scores = 0.5 * (1 - ratio) + 0.5 * diff

    return unvisited_nodes[np.argmax(scores)]
