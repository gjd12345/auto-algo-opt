def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    best_score = float('inf')
    best_node = unvisited_nodes[0]

    for node in unvisited_nodes:
        dist_current = distance_matrix[current_node][node]
        dists_to_others = distance_matrix[node][unvisited_nodes]
        mean_dist = np.mean(dists_to_others)
        if mean_dist == 0:
            score = dist_current
        else:
            score = dist_current / mean_dist

        if score < best_score:
            best_score = score
            best_node = node

    return best_node
