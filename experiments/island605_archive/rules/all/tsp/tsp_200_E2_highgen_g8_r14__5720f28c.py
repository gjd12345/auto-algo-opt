def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) <= 4:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    distances = distance_matrix[current_node][unvisited_nodes]
    dest_distances = distance_matrix[destination_node][unvisited_nodes]

    # farthest-insertion score: prefer nodes far from destination (normalized)
    far_score = dest_distances / (np.max(dest_distances) + 1e-10)

    # 2-opt-awareness penalty: penalize edges where current->u + u->dest is much larger than current->dest
    base_edge = distance_matrix[current_node][destination_node]
    crossing_penalty = np.abs(distances + dest_distances - base_edge) / (base_edge + 1e-10)

    # combined with adjusted weight: favor far nodes more, penalize crossings less
    combined = 0.7 * far_score - 0.3 * crossing_penalty
    best_idx = np.argmax(combined)
    return unvisited_nodes[best_idx]
