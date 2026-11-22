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

    dist_current = distance_matrix[current_node][unvisited_nodes]
    dist_dest = distance_matrix[destination_node][unvisited_nodes]

    # Vector from current to destination (approximate direction)
    dx_dest = distance_matrix[destination_node][current_node]  # direct distance as proxy for direction
    # For each candidate, compute the relative angle penalty using law of cosines
    # We use: d_current^2 + d_dest^2 - d_cd^2 where d_cd is distance between candidate and destination
    # This correlates with being "off direction" (negative means closer to line)
    dist_candidate_dest = distance_matrix[unvisited_nodes][:, destination_node]
    direction_penalty = (dist_current**2 + dist_dest**2 - dist_candidate_dest**2) / (2 * dist_current + 1e-10)
    # Normalize direction penalty
    max_pen = np.abs(direction_penalty).max()
    if max_pen > 0:
        direction_penalty = direction_penalty / max_pen

    # Farthest-insertion component: reward nodes far from destination
    norm_dest = dist_dest / dist_dest.max() if dist_dest.max() > 0 else dist_dest

    # Composite score: lower is better; penalize bad direction, reward far destinations
    alpha = 0.7
    beta = 0.3
    scores = alpha * direction_penalty - beta * norm_dest

    # Add a small penalty for very long edges from current
    avg_neighbor = np.mean(dist_current)
    long_edge_penalty = np.where(dist_current > 2 * avg_neighbor, 0.15, 0.0)
    scores += long_edge_penalty

    best_idx = np.argmin(scores)
    return unvisited_nodes[best_idx]
