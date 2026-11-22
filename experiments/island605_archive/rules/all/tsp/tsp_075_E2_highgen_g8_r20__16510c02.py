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
    dists = distance_matrix[current_node][unvisited_nodes]
    best_score = np.inf
    best_node = unvisited_nodes[0]
    for i, candidate in enumerate(unvisited_nodes):
        other_dists = []
        for j, other in enumerate(unvisited_nodes):
            if other != candidate:
                other_dists.append(distance_matrix[candidate][other])
        avg_other = np.mean(other_dists) if other_dists else 0.0
        score = dists[i] - avg_other
        if score < best_score:
            best_score = score
            best_node = candidate
    return int(best_node)
