def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 1:
        return unvisited_nodes[0]

    curr_dists = distance_matrix[current_node][unvisited_nodes]
    dest_dists = distance_matrix[destination_node][unvisited_nodes]

    # Normalize distances
    max_curr = curr_dists.max() if curr_dists.max() > 0 else 1
    max_dest = dest_dists.max() if dest_dists.max() > 0 else 1
    norm_curr = curr_dists / max_curr
    norm_dest = dest_dists / max_dest

    # Compute farthest distance from each unvisited node to any other unvisited node
    farthest_dists = np.zeros(len(unvisited_nodes))
    for i, u in enumerate(unvisited_nodes):
        farthest_dists[i] = np.max(distance_matrix[u][unvisited_nodes])

    norm_farthest = farthest_dists / (farthest_dists.max() if farthest_dists.max() > 0 else 1)

    # Combined score: encourage staying close to current (low norm_curr) but far from destination (high norm_dest)
    # Add small perturbation from farthest distance for variety
    alpha = 0.6
    beta = 0.3
    gamma = 0.1
    scores = -alpha * norm_curr + beta * norm_dest + gamma * norm_farthest

    best_idx = np.argmax(scores)
    return int(unvisited_nodes[best_idx])
