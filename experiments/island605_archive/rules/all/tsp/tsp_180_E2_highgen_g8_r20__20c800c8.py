def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    best_score = -float('inf')
    best_node = unvisited_nodes[0]

    for candidate in unvisited_nodes:
        dist_current = distance_matrix[current_node][candidate]
        dist_to_dest = distance_matrix[candidate][destination_node]
        other_nodes = [n for n in unvisited_nodes if n != candidate]
        if len(other_nodes) > 1:
            distances_to_others = [distance_matrix[candidate][n] for n in other_nodes]
            mean_dist = sum(distances_to_others) / len(distances_to_others)
            variance = sum((d - mean_dist) ** 2 for d in distances_to_others) / len(distances_to_others)
        else:
            variance = 0.0

        if dist_current == 0:
            score = -float('inf')
        else:
            score = (dist_to_dest / dist_current) * (1 + variance / (dist_current + 1e-10))

        if score > best_score:
            best_score = score
            best_node = candidate

    return best_node
