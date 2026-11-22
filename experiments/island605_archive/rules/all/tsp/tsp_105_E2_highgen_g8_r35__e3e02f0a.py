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
    distances_to_current = distance_matrix[current_node][unvisited_nodes]
    distances_to_dest = distance_matrix[destination_node][unvisited_nodes]

    # Compute how many unvisited neighbors are within 1.5x the distance from current_node to each candidate
    neighbor_counts = np.zeros(len(unvisited_nodes))
    for i, candidate in enumerate(unvisited_nodes):
        dists_other = distance_matrix[candidate][unvisited_nodes]
        dists_other[i] = np.inf
        neighbor_counts[i] = np.sum(dists_other <= 1.5 * distances_to_current[i])

    # Score: favor high (distance_to_dest / distance_to_current) * (1 + 1/(neighbor_count+1))
    # This prefers nodes far from destination but close to current, with few local alternatives.
    epsilon = 1e-10
    ratio = distances_to_dest / (distances_to_current + epsilon)
    compactness_penalty = 1.0 / (neighbor_counts + 1.0)
    score = ratio * compactness_penalty

    if len(unvisited_nodes) <= 3:
        return unvisited_nodes[np.argmin(distances_to_current)]

    return unvisited_nodes[np.argmax(score)]
