def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot:
        # Seed route with farthest customer from depot
        depot_dists = distance_matrix[depot][unvisited_nodes]
        return unvisited_nodes[np.argmax(depot_dists)]

    # Score: low distance to current node + high distance to depot (weighted)
    alpha = 0.6  # weight for current node distance
    beta = 0.4   # weight for depot distance (negative, because we want far from depot)
    scores = alpha * distance_matrix[current_node][unvisited_nodes] - beta * distance_matrix[depot][unvisited_nodes]
    return unvisited_nodes[np.argmin(scores)]
