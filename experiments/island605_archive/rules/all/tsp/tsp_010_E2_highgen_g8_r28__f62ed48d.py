def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) <= 3:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    best_node = None
    best_score = -float('inf')

    for u in unvisited_nodes:
        direct_dist = distance_matrix[current_node][u]
        dest_dist = distance_matrix[destination_node][u]
        # Penalize long direct edges, reward closeness to destination
        score = -direct_dist + 0.5 * dest_dist
        if score > best_score:
            best_score = score
            best_node = u

    return best_node
