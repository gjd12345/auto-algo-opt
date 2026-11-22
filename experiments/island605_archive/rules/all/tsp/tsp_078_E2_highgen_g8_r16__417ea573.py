def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) <= 3:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    distances_from_current = distance_matrix[current_node][unvisited_nodes]

    # Compute centrality: sum of distances from each candidate to all other unvisited nodes
    centrality_scores = np.array([
        np.sum(distance_matrix[u][unvisited_nodes]) for u in unvisited_nodes
    ])

    # Normalize both measures to avoid scale dominance
    norm_dist = distances_from_current / (np.max(distances_from_current) + 1e-10)
    norm_cent = centrality_scores / (np.max(centrality_scores) + 1e-10)

    # Score: prefer close nodes (low norm_dist) and high centrality (high norm_cent)
    scores = norm_dist - 0.4 * norm_cent

    return unvisited_nodes[np.argmin(scores)]
