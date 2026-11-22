def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    n_unvisited = len(unvisited_nodes)
    if n_unvisited == 1:
        return unvisited_nodes[0]

    # Compute distances from current node to all unvisited
    dists = distance_matrix[current_node][unvisited_nodes]

    # Compute regret scores
    regrets = np.zeros(n_unvisited)
    for i, u in enumerate(unvisited_nodes):
        # Best insertion cost: directly from current_node to u
        best = dists[i]
        # Second-best: find the smallest distance from u to any other unvisited node (excluding itself)
        other_dists = distance_matrix[u][unvisited_nodes]
        other_dists = np.delete(other_dists, i)  # remove distance to itself
        second_best = np.min(other_dists) if len(other_dists) > 0 else best
        regrets[i] = second_best - best

    # Smoothness penalty: penalize edges that are much longer than local alternatives
    smooth_penalty = np.zeros(n_unvisited)
    for i, u in enumerate(unvisited_nodes):
        # For each candidate u, consider the average distance from u to all other unvisited nodes
        other_dists = distance_matrix[u][unvisited_nodes]
        avg_dist = np.mean(other_dists)
        # Penalty: ratio of current edge length to average local distance (higher ratio = worse)
        ratio = dists[i] / (avg_dist + 1e-10)
        smooth_penalty[i] = ratio

    # Normalize scores (min-max scaling between 0 and 1)
    def normalize(arr):
        min_val = np.min(arr)
        max_val = np.max(arr)
        if max_val - min_val == 0:
            return np.zeros_like(arr)
        return (arr - min_val) / (max_val - min_val)

    regret_norm = normalize(regrets)
    penalty_norm = normalize(-smooth_penalty)  # negative because lower penalty is better

    # Combined score: 60% regret, 40% smoothness
    weights = np.array([0.6, 0.4])
    combined = weights[0] * regret_norm + weights[1] * penalty_norm

    # Return the node with highest combined score
    return unvisited_nodes[np.argmax(combined)]
