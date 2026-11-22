def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    # Compute distances from current node to all unvisited nodes
    dists = distance_matrix[current_node][unvisited_nodes]

    # If only one left, return it
    if len(unvisited_nodes) == 1:
        return unvisited_nodes[0]

    # Farthest-first component: distance from destination (to seed far regions early)
    dest_dists = distance_matrix[destination_node][unvisited_nodes]
    # Normalize distances to avoid scale issues
    max_cur_dist = np.max(dists) if np.max(dists) > 0 else 1
    max_dest_dist = np.max(dest_dists) if np.max(dest_dists) > 0 else 1
    norm_cur = dists / max_cur_dist
    norm_dest = dest_dists / max_dest_dist

    # 2-opt awareness: penalize if edge is much longer than average local distance
    avg_local = np.mean(dists)
    penalty = np.zeros_like(dists, dtype=float)
    long_edges = dists > 1.5 * avg_local
    penalty[long_edges] = dists[long_edges] / (2 * avg_local)  # penalty proportional to excess

    # Combined score: penalize short cur_dists (to push farther), reward far from dest, add penalty for long edges
    # Use opposite sign: we want to maximize this score to pick "far but not too far disruptively"
    scores = -norm_cur + 0.5 * norm_dest - penalty

    # Fallback: if all scores are equal or degenerate, use nearest neighbor
    if np.std(scores) < 1e-9:
        return unvisited_nodes[np.argmin(dists)]

    # Select node with highest score (farther from current, farther from destination, less penalty)
    best_idx = np.argmax(scores)
    return unvisited_nodes[best_idx]
