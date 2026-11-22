def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    dist_from_current = distance_matrix[current_node][unvisited_nodes]
    dist_to_dest = distance_matrix[destination_node][unvisited_nodes]
    if len(unvisited_nodes) == 1:
        return unvisited_nodes[0]
    # Dynamic alpha: start high (favor farthest) when many nodes left, shift to nearest when few left
    n = len(unvisited_nodes)
    alpha = min(0.9, 0.5 + 0.4 * (n / 10))  # decreases from 0.9 to ~0.5 as n shrinks
    # Penalize nodes that create long jumps from current (2-opt awareness) while still favoring distant from dest
    scores = alpha * dist_to_dest - (2 - alpha) * dist_from_current
    best_idx = np.argmax(scores)
    return unvisited_nodes[best_idx]
