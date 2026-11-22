def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    best_node = None
    best_score = -float('inf')

    for node in unvisited_nodes:
        dist_current = distance_matrix[current_node][node]
        dist_dest = distance_matrix[node][destination_node]

        # Combined score: prefer nodes that are close to current but also not too far from destination
        score = -dist_current + 0.3 * dist_dest

        # 2-opt awareness: penalize if edge is very long relative to direct distance to destination
        dist_to_dest = distance_matrix[current_node][destination_node]
        if dist_to_dest > 0:
            ratio = dist_current / dist_to_dest
            if ratio > 2.0:
                score -= ratio * 5
            elif ratio > 1.2:
                score -= ratio * 2

        if score > best_score:
            best_score = score
            best_node = node

    return best_node
