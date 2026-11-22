def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 1:
        return unvisited_nodes[0]

    dist_curr = distance_matrix[current_node][unvisited_nodes]
    dist_dest = distance_matrix[destination_node][unvisited_nodes]

    # Normalize distances to [0, 1]
    min_curr, max_curr = dist_curr.min(), dist_curr.max()
    norm_curr = (dist_curr - min_curr) / (max_curr - min_curr) if max_curr > min_curr else np.zeros_like(dist_curr)

    min_dest, max_dest = dist_dest.min(), dist_dest.max()
    norm_dest = (dist_dest - min_dest) / (max_dest - min_dest) if max_dest > min_dest else np.zeros_like(dist_dest)

    # Hubness penalty: how many other unvisited nodes are close to this candidate (within 20th percentile distance)
    hubness_penalty = np.zeros(len(unvisited_nodes))
    threshold = np.percentile(distance_matrix[unvisited_nodes][:, unvisited_nodes], 20, axis=1)
    for i, u in enumerate(unvisited_nodes):
        other_dists = distance_matrix[u][unvisited_nodes]
        hubness_penalty[i] = np.sum(other_dists < threshold[i]) / len(unvisited_nodes)

    # Normalize hubness penalty
    min_hub, max_hub = hubness_penalty.min(), hubness_penalty.max()
    norm_hub = (hubness_penalty - min_hub) / (max_hub - min_hub) if max_hub > min_hub else np.zeros_like(hubness_penalty)

    # Composite score: favor short current distance, long distance to destination, low hubness (avoid clusters)
    score = -0.5 * norm_curr + 0.3 * norm_dest - 0.2 * norm_hub

    best_idx = np.argmax(score)
    return unvisited_nodes[best_idx]
