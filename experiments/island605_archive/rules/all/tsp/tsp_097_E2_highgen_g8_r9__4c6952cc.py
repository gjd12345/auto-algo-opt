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

    distances = distance_matrix[current_node][unvisited_nodes]
    dest_distances = distance_matrix[destination_node][unvisited_nodes]

    # Penalize nodes that are far from destination (to avoid leaving isolated clusters)
    max_dist = np.max(distances)
    max_dest = np.max(dest_distances)

    # Score: low distance from current is good, but also prefer nodes closer to destination
    normalized_cur = distances / max_dist if max_dist > 0 else distances
    normalized_dest = dest_distances / max_dest if max_dest > 0 else dest_distances

    # Hybrid score: 0.7 weight on current distance, 0.3 on destination proximity
    scores = 0.7 * normalized_cur + 0.3 * (1 - normalized_dest)

    return unvisited_nodes[np.argmin(scores)]
