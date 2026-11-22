def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    n_remaining = len(unvisited_nodes)

    if n_remaining <= 4:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    dist_cur = distance_matrix[current_node][unvisited_nodes]
    dist_dest = distance_matrix[destination_node][unvisited_nodes]

    # Cluster seeding: favor nodes far from destination relative to current (squared ratio)
    cluster_weight = (dist_dest ** 2) / (dist_cur ** 2 + 1e-10)

    # 2-opt awareness: penalty based on coefficient of variation
    mean_cur = np.mean(dist_cur)
    std_cur = np.std(dist_cur)
    if mean_cur < 1e-10:
        local_penalty = np.ones_like(dist_cur)
    else:
        cv = std_cur / mean_cur
        local_penalty = dist_cur / (mean_cur + cv * std_cur + 1e-10)

    # Adaptive weighting with threshold at 6 remaining nodes
    alpha = 0.7 if n_remaining > 6 else 0.3
    scores = alpha * cluster_weight - (1 - alpha) * local_penalty

    return unvisited_nodes[np.argmax(scores)]
