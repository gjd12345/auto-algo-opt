def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) <= 2:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    current_dists = distance_matrix[current_node][unvisited_nodes]
    dest_dists = distance_matrix[destination_node][unvisited_nodes]
    mean_dist = np.mean(current_dists)
    std_dist = np.std(current_dists) + 1e-10

    scores = []
    for i, candidate in enumerate(unvisited_nodes):
        # Distance savings relative to mean
        savings = (mean_dist - current_dists[i]) / std_dist

        # Angular penalty: compare candidate->dest vs current->dest direction
        direct_return = dest_dists[i]
        detour_ratio = (current_dists[i] + dest_dists[i]) / direct_return if direct_return > 0 else 1.0
        angular_penalty = 1.0 / (1.0 + np.exp(2.0 * (detour_ratio - 1.5)))

        # Probabilistic score: sigmoid-weighted combination
        score = 1.0 / (1.0 + np.exp(-savings)) * angular_penalty
        scores.append(score)

    scores = np.array(scores)
    if np.max(scores) - np.min(scores) < 0.05:
        return unvisited_nodes[np.argmin(current_dists)]

    return unvisited_nodes[np.argmax(scores)]
