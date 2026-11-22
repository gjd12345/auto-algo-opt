def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot:
        distances_from_depot = distance_matrix[depot][unvisited_nodes]
        return unvisited_nodes[np.argmax(distances_from_depot)]
    else:
        distances_from_current = distance_matrix[current_node][unvisited_nodes]
        distances_from_depot = distance_matrix[depot][unvisited_nodes]
        savings = distances_from_depot - distances_from_current

        capacity_usage = demands[unvisited_nodes] / (rest_capacity + 1e-6)

        savings_norm = savings / (np.max(np.abs(savings)) + 1e-6)
        capacity_norm = capacity_usage / (np.max(capacity_usage) + 1e-6)

        scores = 0.9 * savings_norm + 0.1 * capacity_norm

        return unvisited_nodes[np.argmax(scores)]
