def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) <= 3:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    curr_dists = distance_matrix[current_node][unvisited_nodes]
    dest_dists = distance_matrix[destination_node][unvisited_nodes]

    # Regret: cost savings of best over next best insertion
    sorted_indices = np.argsort(curr_dists)
    best_idx = sorted_indices[0]
    second_best_idx = sorted_indices[1]
    regret = curr_dists[second_best_idx] - curr_dists[best_idx]

    # Farthest incentive: normalized distance from destination
    farthest = dest_dists / (np.max(dest_dists) + 1e-9)

    # Smoothness penalty: ratio of current->u distance to direct current->destination distance plus local average
    direct_dist = distance_matrix[current_node][destination_node]
    avg_local = np.mean(curr_dists)
    smoothness_penalty = (curr_dists / (direct_dist + avg_local + 1e-9))

    # Weighted score: regret + farthest - smoothness
    scores = regret * np.ones_like(curr_dists) + 0.7 * farthest - 1.3 * smoothness_penalty

    best_idx = np.argmax(scores)
    return int(unvisited_nodes[best_idx])
