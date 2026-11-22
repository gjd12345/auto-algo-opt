def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) <= 3:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    dist_from_current = distance_matrix[current_node][unvisited_nodes]
    dist_from_dest = distance_matrix[destination_node][unvisited_nodes]

    # Compute relative direction penalty: prefer nodes that maintain progress toward destination
    # Score = (dist_from_dest - dist_from_current) / (dist_from_current + 1e-8)
    score = (dist_from_dest - dist_from_current) / (dist_from_current + 1e-8)
    return unvisited_nodes[np.argmax(score)]
