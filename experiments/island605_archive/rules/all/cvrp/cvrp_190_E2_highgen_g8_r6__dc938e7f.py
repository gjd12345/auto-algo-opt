def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    # Compute savings: distance from depot to customer - distance from current_node to customer
    savings = distance_matrix[depot][unvisited_nodes] - distance_matrix[current_node][unvisited_nodes]

    # Select customer with maximum savings (furthest from depot relative to current position)
    best_idx = np.argmax(savings)
    return unvisited_nodes[best_idx]
