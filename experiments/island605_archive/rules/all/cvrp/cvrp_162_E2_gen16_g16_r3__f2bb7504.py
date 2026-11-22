def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    alpha = 0.7  # weight for distance from depot
    beta = 1.3   # weight for distance from current
    if current_node == depot:
        distances_from_depot = distance_matrix[depot][unvisited_nodes]
        return unvisited_nodes[np.argmax(distances_from_depot)]
    dist_from_depot = distance_matrix[depot][unvisited_nodes] + 1e-10
    dist_from_current = distance_matrix[current_node][unvisited_nodes]
    scores = (dist_from_depot ** alpha) / (dist_from_current ** beta)
    return unvisited_nodes[np.argmax(scores)]
