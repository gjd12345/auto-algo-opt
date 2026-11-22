def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot
    # Compute savings: (distance from depot to customer) - (distance from current node to customer)
    depot_dist = distance_matrix[depot][unvisited_nodes]
    current_dist = distance_matrix[current_node][unvisited_nodes]
    savings = depot_dist - current_dist
    # Select customer with maximum savings (if tie, prefer closer to current node)
    best_idx = np.argmax(savings)
    return unvisited_nodes[best_idx]
