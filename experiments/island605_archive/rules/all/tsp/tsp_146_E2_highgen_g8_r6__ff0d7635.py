def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) <= 3:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    dist_to_current = distance_matrix[current_node][unvisited_nodes]
    dist_to_dest = distance_matrix[destination_node][unvisited_nodes]

    n = len(unvisited_nodes)
    far_sum = np.zeros(n)
    for i, u in enumerate(unvisited_nodes):
        other_dists = distance_matrix[u][unvisited_nodes]
        sorted_dists = np.sort(other_dists)
        if len(sorted_dists) >= 3:
            far_sum[i] = sorted_dists[-1] + sorted_dists[-2]
        elif len(sorted_dists) == 2:
            far_sum[i] = sorted_dists[-1]
        else:
            far_sum[i] = 0

    # Normalize each factor to [0,1] to combine meaningfully
    max_cur = np.max(dist_to_current) if np.max(dist_to_current) > 0 else 1
    max_dest = np.max(dist_to_dest) if np.max(dist_to_dest) > 0 else 1
    max_far = np.max(far_sum) if np.max(far_sum) > 0 else 1

    norm_cur = dist_to_current / max_cur
    norm_dest = dist_to_dest / max_dest
    norm_far = far_sum / max_far

    # Weighted sum: prefer close to current, far from destination, far from others
    alpha, beta, gamma = 0.6, 0.2, 0.2
    scores = -alpha * norm_cur + beta * norm_dest + gamma * norm_far
    return unvisited_nodes[np.argmax(scores)]
