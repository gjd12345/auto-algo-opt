def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    distances_from_current = distance_matrix[current_node][unvisited_nodes]
    distances_to_destination = distance_matrix[destination_node][unvisited_nodes]

    # Normalize distances from current to [0,1]
    max_curr = distances_from_current.max()
    min_curr = distances_from_current.min()
    if max_curr == min_curr:
        norm_current = np.zeros_like(distances_from_current)
    else:
        norm_current = (distances_from_current - min_curr) / (max_curr - min_curr)

    # Normalize distances to destination to [0,1]
    max_dest = distances_to_destination.max()
    min_dest = distances_to_destination.min()
    if max_dest == min_dest:
        norm_dest = np.zeros_like(distances_to_destination)
    else:
        norm_dest = (distances_to_destination - min_dest) / (max_dest - min_dest)

    # Smoothness penalty: ratio of current edge to average of two smallest distances from candidate
    penalty = np.zeros(len(unvisited_nodes))
    for i, u in enumerate(unvisited_nodes):
        other_distances = distance_matrix[u][unvisited_nodes]
        sorted_dists = np.sort(other_distances)
        if len(sorted_dists) > 1:
            nearest_two = sorted_dists[1] if sorted_dists[0] == 0 else sorted_dists[0]
            nearest_two += sorted_dists[2] if len(sorted_dists) > 2 and sorted_dists[0] == 0 else sorted_dists[1]
            nearest_avg = nearest_two / 2.0
        else:
            nearest_avg = distances_from_current[i]
        penalty[i] = distances_from_current[i] / (distances_from_current[i] + nearest_avg + 1e-8)

    # Adjusted weights: emphasize closeness to current and smoothness more
    alpha = 0.4
    beta = 0.2
    gamma = 0.4
    scores = alpha * norm_current + beta * (1.0 - norm_dest) + gamma * penalty
    next_node = unvisited_nodes[np.argmin(scores)]
    return next_node
