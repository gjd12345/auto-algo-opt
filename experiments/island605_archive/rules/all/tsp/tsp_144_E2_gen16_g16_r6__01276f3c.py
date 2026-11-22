def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return destination_node
    if len(unvisited_nodes) == 1:
        return unvisited_nodes[0]

    best_node = None
    best_score = -float('inf')

    for node in unvisited_nodes:
        dist_to_current = distance_matrix[current_node][node]
        dist_to_dest = distance_matrix[node][destination_node]
        # Avoid division by zero
        if dist_to_current == 0:
            score = float('inf') if dist_to_dest > 0 else 0
        else:
            score = dist_to_dest / dist_to_current

        if score > best_score:
            best_score = score
            best_node = node

    return int(best_node)
