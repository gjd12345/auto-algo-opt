def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) <= 3:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    best_node = None
    best_score = float('inf')

    max_dest_dist = np.max(distance_matrix[destination_node]) + 1e-10

    for u in unvisited_nodes:
        dist_current = distance_matrix[current_node][u]
        dist_dest = distance_matrix[destination_node][u]

        # Penalty for long edge relative to destination distance
        dest_penalty = dist_current / (dist_dest + 1e-10)

        # Reward for being far from destination (visit distant clusters early)
        dest_forward = dist_dest / max_dest_dist

        # Adjusted weights: stronger emphasis on distance from current, less on penalty
        alpha = 0.6
        beta = 0.2
        gamma = 0.2
        score = alpha * dist_current + beta * dest_penalty - gamma * dest_forward

        if score < best_score:
            best_score = score
            best_node = int(u)

    return best_node
