def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    # If current node is depot or route just started, prefer farthest customer
    if current_node == depot:
        return unvisited_nodes[np.argmax(distance_matrix[current_node][unvisited_nodes])]

    # Voluntary return if all remaining customers are farther than returning to depot
    nearest_dist = np.min(distance_matrix[current_node][unvisited_nodes])
    return_dist = distance_matrix[current_node][depot]
    if return_dist < nearest_dist:
        return depot

    # Once away from depot, switch to nearest feasible customer
    return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]
