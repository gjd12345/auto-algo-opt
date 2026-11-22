def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 1:
        return unvisited_nodes[0]

    # Compute centroid distances: average distance from each unvisited node to all other unvisited nodes
    centroid_dists = np.array([
        np.mean(distance_matrix[u][unvisited_nodes]) for u in unvisited_nodes
    ])

    # Normalize centroid distances
    c_min, c_max = np.min(centroid_dists), np.max(centroid_dists)
    if c_max - c_min > 0:
        norm_centroid = (centroid_dists - c_min) / (c_max - c_min)
    else:
        norm_centroid = np.zeros_like(centroid_dists)

    # Current distances from current_node
    current_dists = distance_matrix[current_node][unvisited_nodes]
    d_min, d_max = np.min(current_dists), np.max(current_dists)
    if d_max - d_min > 0:
        norm_current = (current_dists - d_min) / (d_max - d_min)
    else:
        norm_current = np.zeros_like(current_dists)

    # Score: weight current distance 0.7, centroid proximity (1 - norm_centroid) 0.3
    scores = 0.7 * norm_current + 0.3 * (1 - norm_centroid)

    return unvisited_nodes[np.argmin(scores)]
