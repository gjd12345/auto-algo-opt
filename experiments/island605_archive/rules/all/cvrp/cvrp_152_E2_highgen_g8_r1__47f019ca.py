def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    if current_node == depot:
        # Start of route: prioritize customer with highest distance*demand product
        scores = distance_matrix[depot, unvisited_nodes] * demands[unvisited_nodes]
        return unvisited_nodes[np.argmax(scores)]
    else:
        # En route: use savings = distance[current][u] - distance[depot][u]
        # Prefer small savings (close to current, far from depot)
        savings = distance_matrix[current_node, unvisited_nodes] - distance_matrix[depot, unvisited_nodes]
        return unvisited_nodes[np.argmin(savings)]
