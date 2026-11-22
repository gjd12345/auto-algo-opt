def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 1:
        return unvisited_nodes[0]

    # Compute distance from current to each unvisited
    cur_distances = distance_matrix[current_node][unvisited_nodes]
    # Compute distance from destination to each unvisited (for farthest seeding)
    dest_distances = distance_matrix[destination_node][unvisited_nodes]

    # Average distance from each candidate to all other unvisited nodes (including current?)
    # Use to other unvisited, exclude self
    avg_other_dist = np.array([
        np.mean([distance_matrix[u][v] for v in unvisited_nodes if v != u])
        for u in unvisited_nodes
    ])

    # Normalize to avoid scale issues
    epsilon = 1e-9
    # Score = (distance from current) * (1 / (distance from destination + epsilon)) * (distance from current / (avg_other_dist + epsilon))
    # Actually we want: prefer higher dest distance (farthest), lower current distance (smooth), and lower ratio current/avg_other (smooth)
    # Score = dest_distances / (cur_distances * (cur_distances / (avg_other_dist + epsilon)) + epsilon)
    # Simplified: combine farthest (high dest_dist) with smooth (low cur_dist / avg_other)
    ratio = cur_distances / (avg_other_dist + epsilon)
    score = dest_distances / (cur_distances * ratio + epsilon)

    # Fallback to nearest neighbor if something is NaN
    if np.any(np.isnan(score)):
        return unvisited_nodes[np.argmin(cur_distances)]

    best_idx = np.argmax(score)
    return unvisited_nodes[best_idx]
