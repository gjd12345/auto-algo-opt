def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) <= 3:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    from_current = distance_matrix[current_node][unvisited_nodes]
    from_dest = distance_matrix[destination_node][unvisited_nodes]

    max_from_dest = np.max(from_dest)
    norm_from_dest = from_dest / max_from_dest if max_from_dest > 0 else from_dest

    max_from_curr = np.max(from_current)
    norm_from_curr = from_current / max_from_curr if max_from_curr > 0 else from_current

    candidate_to_dest = distance_matrix[unvisited_nodes][:, destination_node]
    ratio_penalty = np.where(candidate_to_dest > 0, from_current / candidate_to_dest, 1.0)
    ratio_penalty = np.clip(ratio_penalty, 0.5, 3.0)

    score = 0.3 * norm_from_dest - 0.5 * norm_from_curr - 0.3 * ratio_penalty

    best_idx = np.argmax(score)
    return int(unvisited_nodes[best_idx])
