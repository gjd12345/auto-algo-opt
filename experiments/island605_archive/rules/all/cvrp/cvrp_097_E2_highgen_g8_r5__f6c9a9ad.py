def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot:
        # Seed route with farthest node to reach distant clusters
        dist_to_depot = distance_matrix[depot][unvisited_nodes]
        return unvisited_nodes[np.argmax(dist_to_depot)]
    else:
        # Weighted combination: 0.6 * distance from current + 0.4 * negative distance from depot
        weights = 0.6 * distance_matrix[current_node][unvisited_nodes] - 0.4 * distance_matrix[depot][unvisited_nodes]
        return unvisited_nodes[np.argmin(weights)]
