def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    dists_current = distance_matrix[current_node][unvisited_nodes]
    dists_dest = distance_matrix[destination_node][unvisited_nodes]

    max_current = np.max(dists_current) if np.max(dists_current) > 0 else 1
    max_dest = np.max(dists_dest) if np.max(dists_dest) > 0 else 1

    norm_current = dists_current / max_current
    norm_dest = dists_dest / max_dest

    # Compute approximate angle penalty: prefer nodes where current->node is not much larger than node->destination
    # Use ratio to penalize sharp turns (high current-to-node relative to node-to-destination)
    with np.errstate(divide='ignore', invalid='ignore'):
        ratio = np.where(dists_dest > 0, dists_current / dists_dest, np.inf)
    norm_ratio = np.clip(ratio / (np.max(ratio[ratio != np.inf]) if np.any(ratio != np.inf) else 1), 0, 1)

    # Score: penalize large current edges (smoothness) + reward far from destination (seeding) - penalize high ratio (angles)
    score = norm_current - 0.6 * norm_dest + 0.4 * norm_ratio

    best_idx = np.argmin(score)
    return int(unvisited_nodes[best_idx])
