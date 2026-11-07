def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]
