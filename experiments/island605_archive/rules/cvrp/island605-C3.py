def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot:
        return unvisited_nodes[np.argmax(distance_matrix[depot][unvisited_nodes])]
    else:
        alpha = rest_capacity / demands.max()  # dynamic weight
        dist_current = distance_matrix[current_node][unvisited_nodes]
        dist_depot = distance_matrix[depot][unvisited_nodes]
        score = alpha * dist_current + (1 - alpha) * dist_depot
        best_node = unvisited_nodes[np.argmin(score)]
        if distance_matrix[current_node][best_node] >= distance_matrix[current_node][depot]:
            return depot
        return best_node