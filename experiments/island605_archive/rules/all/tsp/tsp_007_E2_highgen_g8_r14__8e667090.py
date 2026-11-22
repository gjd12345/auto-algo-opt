def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    # Weighted score: favor nodes farther from destination but penalize long edges from current node
    distances_from_current = distance_matrix[current_node][unvisited_nodes]
    distances_from_dest = distance_matrix[destination_node][unvisited_nodes]
    # Score = distance_from_dest - 0.5 * distance_from_current (higher is better for farthest, but we minimize)
    # To prioritize far-from-dest nodes with a locally reasonable edge, we minimize (distance_from_current - 0.5 * distance_from_dest)
    scores = distances_from_current - 0.5 * distances_from_dest
    best_idx = np.argmin(scores)
    return int(unvisited_nodes[best_idx])
