def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) <= 2:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    best_node = None
    best_score = np.inf
    avg_dest_dist = np.mean([distance_matrix[destination_node][u] for u in unvisited_nodes])

    for candidate in unvisited_nodes:
        direct_dist = distance_matrix[current_node][candidate]
        dest_dist = distance_matrix[destination_node][candidate]
        # Penalize if edge is long relative to average destination distance
        edge_ratio = direct_dist / (dest_dist + 1e-10)
        score = direct_dist + edge_ratio * avg_dest_dist * len(unvisited_nodes)

        if score < best_score:
            best_score = score
            best_node = candidate

    if best_node is None:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]
    return best_node
