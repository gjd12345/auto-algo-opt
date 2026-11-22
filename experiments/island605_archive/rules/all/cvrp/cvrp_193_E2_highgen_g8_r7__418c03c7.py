def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    current_dists = distance_matrix[current_node, unvisited_nodes]
    depot_dists = distance_matrix[depot, unvisited_nodes]

    # Score = depot_distance - current_distance (prefer large positive differences)
    scores = depot_dists - current_dists

    # Select customer with maximum score (ties broken by nearest current distance)
    best_idx = np.argmax(scores)
    return unvisited_nodes[best_idx]
