def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    # Compute distance from current node to each unvisited node
    dist_current = distance_matrix[current_node][unvisited_nodes]

    # Compute average distance from each unvisited node to all other unvisited nodes
    avg_dist_to_others = np.array([
        np.mean(distance_matrix[u][unvisited_nodes[unvisited_nodes != u]]) if len(unvisited_nodes) > 1 else 0
        for u in unvisited_nodes
    ])
    avg_dist_to_others = np.where(avg_dist_to_others == 0, np.inf, avg_dist_to_others)

    # Score: ratio of current distance to average proximity to others (lower is better)
    scores = dist_current / avg_dist_to_others

    # Pick deterministically the node with smallest score
    return unvisited_nodes[np.argmin(scores)]
