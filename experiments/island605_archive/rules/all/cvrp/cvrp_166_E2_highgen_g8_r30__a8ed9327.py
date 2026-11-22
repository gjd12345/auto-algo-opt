def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot
    if current_node == depot:
        return unvisited_nodes[np.argmax(distance_matrix[depot][unvisited_nodes])]
    else:
        total_demand = demands[unvisited_nodes].sum() + rest_capacity
        if rest_capacity > 0.7 * total_demand:
            return unvisited_nodes[np.argmax(distance_matrix[depot][unvisited_nodes])]
        else:
            savings = distance_matrix[depot][unvisited_nodes] - distance_matrix[current_node][unvisited_nodes]
            angles = np.arctan2(
                distance_matrix[unvisited_nodes, 1] - distance_matrix[depot, 1],
                distance_matrix[unvisited_nodes, 0] - distance_matrix[depot, 0]
            )
            angle_current = np.arctan2(
                distance_matrix[current_node, 1] - distance_matrix[depot, 1],
                distance_matrix[current_node, 0] - distance_matrix[depot, 0]
            )
            angle_diff = np.abs(angles - angle_current)
            angle_penalty = 0.3 * (1 - np.cos(angle_diff))
            return unvisited_nodes[np.argmax(savings - angle_penalty)]
