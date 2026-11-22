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
    num_unvisited = len(unvisited_nodes)
    if num_unvisited <= 2:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    dists_from_current = distance_matrix[current_node][unvisited_nodes]
    dists_from_dest = distance_matrix[destination_node][unvisited_nodes]

    # Calculate a penalty based on the ratio of the edge to average local distances
    alphas = np.zeros(num_unvisited)
    for i, u in enumerate(unvisited_nodes):
        dist_to_u = dists_from_current[i]
        # Get distances from u to all other unvisited nodes and destination
        other_dists = np.concatenate([distance_matrix[u][unvisited_nodes], [distance_matrix[u][destination_node]]])
        avg_other = np.mean(other_dists)
        if avg_other > 0:
            alphas[i] = dist_to_u / avg_other
        else:
            alphas[i] = 0.0

    # Combine farthest selection (distance from current + destination) with smoothness penalty
    # Farthest component: larger distance is better to visit early
    far_score = dists_from_current + dists_from_dest
    # Penalty: high alpha means long edge relative to local neighborhood, penalize to avoid crossings
    penalty = alphas * 2.0
    score = far_score - penalty
    # Ensure positive with small constant to avoid negative impact on argmax
    score = score + 1e-9

    next_idx = np.argmax(score)
    return int(unvisited_nodes[next_idx])
