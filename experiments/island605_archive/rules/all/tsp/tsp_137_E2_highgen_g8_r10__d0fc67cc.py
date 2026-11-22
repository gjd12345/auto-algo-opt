def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    d_current = distance_matrix[current_node][unvisited_nodes]
    d_dest = distance_matrix[destination_node][unvisited_nodes]

    # Weighted score: small current distance, large destination distance
    score = d_current / (d_dest + 1e-10)

    # Deterministic tournament among top candidates
    n_candidates = min(5, len(unvisited_nodes))
    if n_candidates < 2:
        return unvisited_nodes[np.argmin(score)]

    candidate_indices = np.argpartition(score, n_candidates-1)[:n_candidates]
    np.random.seed(42)  # deterministic tie-breaking
    shuffled = np.random.permutation(candidate_indices)
    best_idx = shuffled[0]
    best_score = score[shuffled[0]]
    for idx in shuffled[1:]:
        if score[idx] < best_score:
            best_score = score[idx]
            best_idx = idx

    return unvisited_nodes[best_idx]
