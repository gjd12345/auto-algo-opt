def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    candidates = unvisited_nodes.copy()
    n = len(candidates)
    if n == 1:
        return int(candidates[0])

    # Compute nearest neighbor distances from current node to all candidates
    dists = distance_matrix[current_node][candidates]
    min_dist = np.min(dists)
    max_dist = np.max(dists)
    range_dist = max_dist - min_dist if max_dist > min_dist else 1.0

    # Normalize distances: smaller is better
    normalized_dists = (dists - min_dist) / range_dist

    # Compute diversity term: count how many times each candidate has been the nearest
    # to previously visited nodes (we approximate using a static "attractiveness" based on
    # average distance to all other candidates)
    diversity_scores = np.zeros(n)
    for i, u in enumerate(candidates):
        other_dists = distance_matrix[u][[v for v in candidates if v != u]]
        avg_other_dist = np.mean(other_dists) if len(other_dists) > 0 else 1.0
        # Nodes that are far from others get higher diversity score (to avoid clustering)
        diversity_scores[i] = avg_other_dist / (np.max(distance_matrix) + 1e-10)

    # Composite score: prefer short distance, but also prefer nodes that are isolated from others
    alpha = 0.6  # weight for distance term
    scores = -(alpha * normalized_dists) + ((1 - alpha) * diversity_scores)

    best_idx = np.argmax(scores)
    best_score = scores[best_idx]
    tie_mask = (scores == best_score)
    if np.sum(tie_mask) > 1:
        tied_nodes = candidates[tie_mask]
        nearest = np.argmin(distance_matrix[current_node][tied_nodes])
        return int(tied_nodes[nearest])
    return int(candidates[best_idx])
