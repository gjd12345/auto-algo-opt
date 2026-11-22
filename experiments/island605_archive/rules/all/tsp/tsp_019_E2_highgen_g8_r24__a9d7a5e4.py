def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    n_unvisited = len(unvisited_nodes)
    if n_unvisited == 1:
        return unvisited_nodes[0]

    current_distances = distance_matrix[current_node][unvisited_nodes]

    # Compute regret: second best minus best (current distance)
    regrets = np.zeros(n_unvisited)
    for i, candidate in enumerate(unvisited_nodes):
        dists_from_candidate = distance_matrix[candidate][unvisited_nodes]
        sorted_dists = np.sort(dists_from_candidate)
        # Best is 0 (self), so second best is the first positive value
        second_best = sorted_dists[1]
        best = current_distances[i]
        regrets[i] = second_best - best

    # Compute smoothness penalty: ratio of current edge to average neighbor distance
    local_avg = np.zeros(n_unvisited)
    for i, candidate in enumerate(unvisited_nodes):
        neighbors = distance_matrix[candidate][unvisited_nodes]
        local_avg[i] = np.mean(neighbors[neighbors > 0])
    smoothness_penalty = current_distances / (local_avg + 1e-10)

    # Combined score: higher weight on smoothness penalty, add distance weighting to regret
    score = regrets - 0.8 * smoothness_penalty - 0.2 * current_distances

    # Fallback to nearest neighbor if low variation
    if np.std(score) < 0.05:
        return unvisited_nodes[np.argmin(current_distances)]

    best_idx = np.argmax(score)
    return unvisited_nodes[best_idx]
