def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot:
        return unvisited_nodes[np.argmax(distance_matrix[depot][unvisited_nodes])]

    max_demand = np.max(demands[unvisited_nodes]) if len(unvisited_nodes) > 0 else 0
    if rest_capacity < 1.2 * max_demand:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    savings = (0.8 * distance_matrix[depot][unvisited_nodes] +
               0.2 * distance_matrix[depot][current_node] -
               distance_matrix[current_node][unvisited_nodes])
    return unvisited_nodes[np.argmax(savings)]
