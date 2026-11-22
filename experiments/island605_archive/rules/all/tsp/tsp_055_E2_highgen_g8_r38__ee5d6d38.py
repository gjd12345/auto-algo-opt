def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    # Compute distance from current node to each unvisited node
    dists_from_current = distance_matrix[current_node][unvisited_nodes]
    # Compute distance from each unvisited node to destination
    dists_to_dest = distance_matrix[destination_node][unvisited_nodes]
    # Normalize to avoid scale issues
    max_curr = dists_from_current.max() if len(dists_from_current) > 0 else 1
    max_dest = dists_to_dest.max() if len(dists_to_dest) > 0 else 1
    if max_curr == 0:
        max_curr = 1
    if max_dest == 0:
        max_dest = 1
    # Score: prefer nodes close to current (small dist) and far from destination (large dist)
    # Also penalize edges that are very long relative to local average to avoid crossings
    scores = []
    for i, node in enumerate(unvisited_nodes):
        curr_dist = dists_from_current[i]
        dest_dist = dists_to_dest[i]
        # Local average: average distance from current to all unvisited (rough proxy)
        local_avg = dists_from_current.mean()
        crossing_penalty = max(0, curr_dist - local_avg) / (local_avg + 1e-8)
        # Score: lower is better — close to current, far from destination, small crossing penalty
        score = (curr_dist / max_curr) - 0.5 * (dest_dist / max_dest) + 0.3 * crossing_penalty
        scores.append(score)
    best_idx = int(np.argmin(scores))
    return int(unvisited_nodes[best_idx])
