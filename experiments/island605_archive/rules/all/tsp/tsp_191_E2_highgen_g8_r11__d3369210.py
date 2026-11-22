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
    distances = distance_matrix[current_node][unvisited_nodes]
    dest_distances = distance_matrix[destination_node][unvisited_nodes]
    # Score: lower is better; combine nearest-neighbor (distances) with farthest-insertion penalty (-0.3 * dest_distances)
    scores = distances - 0.3 * dest_distances
    return unvisited_nodes[np.argmin(scores)]
