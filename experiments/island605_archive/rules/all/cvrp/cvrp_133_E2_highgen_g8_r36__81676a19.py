def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if current_node == depot:
        # When at depot, pick the customer with highest distance from depot
        return unvisited_nodes[np.argmax(distance_matrix[depot][unvisited_nodes])]

    # Compute a score: minimize distance from current node, maximize distance from depot
    current_dists = distance_matrix[current_node][unvisited_nodes]
    depot_dists = distance_matrix[depot][unvisited_nodes]

    # Weighted combination: 0.7 * closeness to current, 0.3 * farness from depot
    scores = 0.7 * current_dists - 0.3 * depot_dists
    return unvisited_nodes[np.argmin(scores)]
