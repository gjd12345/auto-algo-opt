def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 1:
        return unvisited_nodes[0]

    distances_from_current = distance_matrix[current_node][unvisited_nodes]
    distances_to_destination = distance_matrix[destination_node][unvisited_nodes]

    cost_of_delay = np.zeros(len(unvisited_nodes))
    for i, node in enumerate(unvisited_nodes):
        temp_dists = np.delete(distances_from_current, i)
        if len(temp_dists) > 0:
            cost_of_delay[i] = np.max(temp_dists) - distances_from_current[i]
        else:
            cost_of_delay[i] = 0

    remaining_ratio = len(unvisited_nodes) / (len(distance_matrix) - 1)
    alpha = 0.1 + 0.5 * (1 - remaining_ratio)
    beta = 0.1 + 0.2 * remaining_ratio

    farthest_score = distances_to_destination / (np.max(distances_to_destination) + 1e-10)

    a = distances_from_current
    b = distances_to_destination
    c = distance_matrix[unvisited_nodes][:, destination_node]
    denominator = 2 * a * b
    denominator = np.where(denominator == 0, 1, denominator)
    cosine_angles = (a**2 + b**2 - c**2) / denominator
    angle_penalty = np.abs(cosine_angles)

    scores = (alpha * farthest_score) + (beta * cost_of_delay) - 0.7 * (distances_from_current / (np.max(distances_from_current) + 1e-10)) - 0.5 * angle_penalty

    best_idx = np.argmax(scores)
    return unvisited_nodes[best_idx]
