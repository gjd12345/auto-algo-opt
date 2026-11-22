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
    eps = 1e-10
    d_current = distance_matrix[current_node][unvisited_nodes]
    d_dest = distance_matrix[destination_node][unvisited_nodes]

    # Compute regret: for each candidate, find its nearest and second-nearest distances among unvisited nodes
    best_scores = []
    for i, node in enumerate(unvisited_nodes):
        dists = distance_matrix[node][unvisited_nodes]
        sorted_dists = np.sort(dists)
        if len(sorted_dists) >= 2:
            regret = sorted_dists[1] - sorted_dists[0]
        else:
            regret = 0
        best_scores.append(regret)

    regret_scores = np.array(best_scores)
    # Combine: favor high regret (critical nodes) and far from destination, but close to current
    scores = (d_current + eps) / (regret_scores + d_dest + eps)
    best_idx = np.argmin(scores)
    return int(unvisited_nodes[best_idx])
