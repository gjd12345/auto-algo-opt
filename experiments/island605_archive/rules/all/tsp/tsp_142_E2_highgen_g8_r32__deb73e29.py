def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    dist_from_current = distance_matrix[current_node][unvisited_nodes]
    dist_to_dest = distance_matrix[destination_node][unvisited_nodes]
    # Score: ratio of current distance to total distance (current + destination)
    denominator = dist_from_current + dist_to_dest
    # Avoid division by zero
    denominator = np.where(denominator == 0, 1e-8, denominator)
    scores = dist_from_current / denominator
    # Tie-breaking: prefer node closer to destination
    min_score = np.min(scores)
    tie_mask = scores == min_score
    if np.sum(tie_mask) > 1:
        tied_nodes = unvisited_nodes[tie_mask]
        tied_dists = distance_matrix[destination_node][tied_nodes]
        next_node = tied_nodes[np.argmin(tied_dists)]
    else:
        next_node = unvisited_nodes[np.argmin(scores)]
    return int(next_node)
