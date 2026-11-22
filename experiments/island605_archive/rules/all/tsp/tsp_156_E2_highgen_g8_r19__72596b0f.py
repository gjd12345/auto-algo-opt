def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    best_score = float('inf')
    best_node = unvisited_nodes[0]

    for candidate in unvisited_nodes:
        d_current = distance_matrix[current_node][candidate]
        d_to_dest = distance_matrix[candidate][destination_node]
        other_dists = [distance_matrix[candidate][other] for other in unvisited_nodes if other != candidate]
        total_other_dist = sum(other_dists) if other_dists else 0.0
        denominator = d_to_dest + total_other_dist
        if denominator == 0.0:
            denominator = 1.0
        score = d_current / denominator

        if score < best_score:
            best_score = score
            best_node = candidate

    return int(best_node)
