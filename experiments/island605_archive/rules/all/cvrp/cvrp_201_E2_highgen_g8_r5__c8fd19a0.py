def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    dist_current = distance_matrix[current_node][unvisited_nodes]
    dist_depot = distance_matrix[depot][unvisited_nodes]

    # Score: high when depot distance is large and current distance is small
    # Add small epsilon to avoid division by zero
    scores = dist_depot / (dist_current + 1e-10)
    best_idx = np.argmax(scores)
    return unvisited_nodes[best_idx]
