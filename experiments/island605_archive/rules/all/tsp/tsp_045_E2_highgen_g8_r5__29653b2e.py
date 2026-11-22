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
    current_distances = distance_matrix[current_node][unvisited_nodes]
    scores = np.zeros(len(unvisited_nodes))
    for i, u in enumerate(unvisited_nodes):
        other_mask = np.ones(len(unvisited_nodes), dtype=bool)
        other_mask[i] = False
        other_nodes = unvisited_nodes[other_mask]
        if len(other_nodes) > 0:
            avg_other_dist = np.mean(distance_matrix[u][other_nodes])
        else:
            avg_other_dist = 0.0
        scores[i] = -current_distances[i] + 0.7 * avg_other_dist
    best_idx = np.argmax(scores)
    return int(unvisited_nodes[best_idx])
