def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    n_remaining = len(unvisited_nodes)
    if n_remaining == 1:
        return unvisited_nodes[0]

    best_score = np.inf
    best_node = unvisited_nodes[0]

    for u in unvisited_nodes:
        direct_dist = distance_matrix[current_node][u]
        dest_dist = distance_matrix[u][destination_node]
        # Penalize nodes far from destination, weighted by remaining count
        score = direct_dist + (dest_dist / n_remaining)
        if score < best_score:
            best_score = score
            best_node = u

    return best_node
