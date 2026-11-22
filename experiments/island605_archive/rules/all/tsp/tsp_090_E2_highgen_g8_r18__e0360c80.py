def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    dists = distance_matrix[current_node][unvisited_nodes]
    best_score = np.inf
    best_node = unvisited_nodes[0]
    best_dist = np.inf

    for i, candidate in enumerate(unvisited_nodes):
        dist = dists[i]
        remaining = np.concatenate([unvisited_nodes[unvisited_nodes != candidate], [destination_node]])
        distances_from_candidate = distance_matrix[candidate][remaining]

        mean_dist = distances_from_candidate.mean() if len(distances_from_candidate) > 0 else 1.0
        std_dist = distances_from_candidate.std() if len(distances_from_candidate) > 1 else 0.0

        if mean_dist == 0:
            return candidate
        gap = dist - mean_dist
        score = gap * (1.0 + 0.2 * std_dist)

        if score < best_score or (score == best_score and dist < best_dist):
            best_score = score
            best_node = candidate
            best_dist = dist

    return best_node
