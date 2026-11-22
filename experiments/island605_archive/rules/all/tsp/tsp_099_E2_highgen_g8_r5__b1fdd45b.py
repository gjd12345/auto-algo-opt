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

    # Compute distances from current node and from destination
    dist_current = distance_matrix[current_node][unvisited_nodes]
    dist_to_dest = distance_matrix[destination_node][unvisited_nodes]

    # Normalize distances to [0,1] range for fair combination
    max_current = np.max(dist_current)
    max_dest = np.max(dist_to_dest)
    norm_current = dist_current / max_current if max_current > 0 else dist_current
    norm_dest = dist_to_dest / max_dest if max_dest > 0 else dist_to_dest

    # Combined score: prefer short current edge but also prefer staying away from destination (to handle distant clusters)
    scores = 0.7 * norm_current - 0.3 * norm_dest

    return unvisited_nodes[np.argmin(scores)]
