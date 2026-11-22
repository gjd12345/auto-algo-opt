def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot:
        dist_from_depot = distance_matrix[depot][unvisited_nodes]
        demands_subset = demands[unvisited_nodes]
        # Prefer large demand among far customers
        score = dist_from_depot + 0.5 * demands_subset
        return unvisited_nodes[np.argmax(score)]
    else:
        dist_current = distance_matrix[current_node][unvisited_nodes]
        dist_depot = distance_matrix[depot][unvisited_nodes]
        # Score: favor nodes far from depot but close to current node
        score = dist_depot - dist_current
        return unvisited_nodes[np.argmax(score)]
