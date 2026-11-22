def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    candidates = unvisited_nodes
    n_candidates = len(candidates)

    if n_candidates == 1:
        return candidates[0]

    dists_current = distance_matrix[current_node][candidates]
    dists_to_dest = distance_matrix[destination_node][candidates]

    scores = np.zeros(n_candidates)
    for i, u in enumerate(candidates):
        distances_u = distance_matrix[u][candidates]
        other_dists = distances_u[candidates != u]
        local_avg = np.mean(other_dists) if len(other_dists) > 0 else dists_current[i]

        edge_penalty = dists_current[i] / (local_avg + 1e-8)
        distance_penalty = 0.6 * dists_current[i]
        dest_bonus = 0.3 * dists_to_dest[i]

        scores[i] = edge_penalty + distance_penalty - dest_bonus

    return candidates[np.argmin(scores)]
