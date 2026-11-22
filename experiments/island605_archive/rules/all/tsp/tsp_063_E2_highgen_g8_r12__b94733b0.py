def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    dist_cur = distance_matrix[current_node][unvisited_nodes]
    dist_dest = distance_matrix[destination_node][unvisited_nodes]

    # Compute average minimum distance from each candidate to all other unvisited nodes (excluding itself)
    avg_min_dists = np.array([
        np.mean(np.sort(np.delete(distance_matrix[u][unvisited_nodes], i))[:max(1, len(unvisited_nodes)//2)])
        if len(unvisited_nodes) > 1 else 0.0
        for i, u in enumerate(unvisited_nodes)
    ])

    # Penalty: if current->u is more than 1.5 times the average min distance
    penalties = np.maximum(0, dist_cur - 1.5 * avg_min_dists)

    # Normalize components
    max_cur = np.max(dist_cur) if np.max(dist_cur) > 0 else 1
    max_dest = np.max(dist_dest) if np.max(dist_dest) > 0 else 1
    max_pen = np.max(penalties) if np.max(penalties) > 0 else 1

    # Score: prefer short current distance (negative), long destination distance (positive), low penalty (negative)
    scores = -0.5 * (dist_cur / max_cur) + 0.3 * (dist_dest / max_dest) - 0.2 * (penalties / max_pen)

    return unvisited_nodes[np.argmax(scores)]
