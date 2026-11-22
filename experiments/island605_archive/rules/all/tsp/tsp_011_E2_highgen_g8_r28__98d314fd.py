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
    if len(unvisited_nodes) == 1:
        return unvisited_nodes[0]

    # Compute distances from current_node to each unvisited node
    dists_current = distance_matrix[current_node][unvisited_nodes]
    # Compute distances from destination_node to each unvisited node
    dists_dest = distance_matrix[destination_node][unvisited_nodes]

    # Farthest from destination (to seed distant regions early)
    dest_score = dists_dest

    # Penalize sharp angles: approximate by preferring nodes where
    # dist_current + dist_dest is close to the direct current->destination distance
    direct_dist = distance_matrix[current_node][destination_node]
    angle_penalty = np.abs(dists_current + dists_dest - direct_dist)

    # Combined score: prioritize far from destination but penalize poor angles
    alpha = 0.6  # weight for farthest from destination
    beta = 0.4   # weight for angle penalty
    scores = alpha * dists_dest - beta * angle_penalty

    # Choose node with highest score (farthest from dest, least angle penalty)
    best_idx = np.argmax(scores)
    return unvisited_nodes[best_idx]
