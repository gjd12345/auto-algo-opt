def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if current_node == depot:
        dist_depot = distance_matrix[depot, unvisited_nodes]
        return unvisited_nodes[np.argmax(dist_depot)]
    else:
        dist_current = distance_matrix[current_node, unvisited_nodes]
        dist_depot = distance_matrix[depot, unvisited_nodes]
        weight = 1.0 - (rest_capacity / demands.sum())  # dynamic weight
        score = weight * dist_current + (1 - weight) * (1.0 / (dist_depot + 1e-8))
        best_idx = np.argmin(score)
        best_customer = unvisited_nodes[best_idx]
        if distance_matrix[current_node, depot] < dist_current[best_idx]:
            return depot
        return best_customer
