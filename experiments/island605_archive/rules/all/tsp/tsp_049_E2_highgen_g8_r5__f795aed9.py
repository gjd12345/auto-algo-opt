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
    if len(unvisited_nodes) <= 2:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    dist_from_current = distance_matrix[current_node][unvisited_nodes]

    # Average distance from each candidate to all other unvisited nodes
    avg_dist_to_others = np.array([
        np.mean(distance_matrix[node][unvisited_nodes])
        for node in unvisited_nodes
    ])

    # Score = average distance to others - distance from current
    scores = avg_dist_to_others - dist_from_current

    next_node = unvisited_nodes[np.argmax(scores)]
    return int(next_node)
