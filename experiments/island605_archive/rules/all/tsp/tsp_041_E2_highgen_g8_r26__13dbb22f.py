def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    # Precompute distances from current node to all unvisited nodes
    dists = distance_matrix[current_node][unvisited_nodes]

    # Compute regret and smoothness penalty for each candidate
    best_score = -1e9
    best_node = int(unvisited_nodes[0])

    for i, candidate in enumerate(unvisited_nodes):
        # Regret: difference between second-best and best insertion cost
        # (simplified: use distance to current_node as best; second-best is min distance from candidate to another unvisited node)
        distances_from_candidate = distance_matrix[candidate][unvisited_nodes]
        # exclude the candidate itself from min search
        candidate_dists = np.delete(distances_from_candidate, i)
        best_alt = np.min(candidate_dists) if len(candidate_dists) > 0 else float('inf')
        regret = best_alt - dists[i]

        # Smoothness penalty: penalize long edges relative to local average
        local_avg = np.mean(distances_from_candidate) if len(distances_from_candidate) > 0 else 1.0
        smoothness_penalty = dists[i] / (local_avg + 1e-8)

        # Composite score: regret weighted high, smoothness penalized (lower is better)
        score = regret - 2.0 * smoothness_penalty

        if score > best_score:
            best_score = score
            best_node = int(candidate)

    return best_node
