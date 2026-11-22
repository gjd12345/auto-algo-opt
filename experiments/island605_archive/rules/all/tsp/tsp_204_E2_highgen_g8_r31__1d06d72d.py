def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 1:
        return unvisited_nodes[0]

    best_node = None
    best_score = float('inf')

    for node in unvisited_nodes:
        dist_to_current = distance_matrix[current_node][node]

        # Distances from this candidate to all other unvisited nodes
        dist_to_others = distance_matrix[node][unvisited_nodes]

        # Future-cost variability: use coefficient of variation (std/mean)
        mean_future = np.mean(dist_to_others)
        std_future = np.std(dist_to_others)
        variability_penalty = std_future / (mean_future + 1e-10)

        # Normalized distance (relative to max possible distance)
        norm_distance = dist_to_current / (np.max(distance_matrix) + 1e-10)

        # Combined score: smaller is better
        score = norm_distance * (1 + variability_penalty)

        if score < best_score:
            best_score = score
            best_node = node

    if best_node is None:
        best_node = unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    return best_node
