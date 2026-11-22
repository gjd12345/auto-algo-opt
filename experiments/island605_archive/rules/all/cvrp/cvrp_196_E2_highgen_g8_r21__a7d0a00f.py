def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    # Compute savings: (distance from current node to depot + distance from depot to customer)
    # minus distance from current node to customer.
    # Customers with higher savings are preferred.
    savings = (distance_matrix[current_node, depot] + distance_matrix[depot, unvisited_nodes]) \
              - distance_matrix[current_node, unvisited_nodes]
    best_idx = np.argmax(savings)
    return unvisited_nodes[best_idx]
