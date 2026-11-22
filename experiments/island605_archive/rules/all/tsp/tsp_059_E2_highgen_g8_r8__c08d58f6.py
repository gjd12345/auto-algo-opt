def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    alpha = 1.5   # penalty weight for crossing-prone edges
    beta = 0.5    # weight for distance to destination (reduced emphasis)

    dist_current = distance_matrix[current_node][unvisited_nodes]
    dist_to_dest = distance_matrix[destination_node][unvisited_nodes]

    avg_neighbor_dist = np.array([
        np.mean(np.delete(distance_matrix[node][unvisited_nodes],
                          np.where(unvisited_nodes == node)[0]))
        if len(unvisited_nodes) > 1 else 0
        for node in unvisited_nodes
    ])

    crossing_penalty = np.where(avg_neighbor_dist > 0, dist_current / avg_neighbor_dist, 0)

    scores = dist_current + alpha * crossing_penalty - beta * dist_to_dest
    best_idx = np.argmin(scores)
    return unvisited_nodes[best_idx]
