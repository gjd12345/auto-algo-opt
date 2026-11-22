def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction.

    Args:
        current_node:    index of the current node (0 = depot)
        depot:           index of the depot (always 0)
        unvisited_nodes: array of feasible unvisited customer indices
                         (already filtered to satisfy remaining capacity)
        rest_capacity:   remaining vehicle capacity
        demands:         demand of every node (index 0 = depot demand = 0)
        distance_matrix: pairwise Euclidean distance matrix
    Returns:
        Index of the next node to visit, or 0 to return to the depot early.
    """
    if current_node == depot:
        # First node from depot: choose the farthest customer to seed route
        dists_from_depot = distance_matrix[depot][unvisited_nodes]
        return unvisited_nodes[np.argmax(dists_from_depot)]

    best_node = None
    best_savings = -float('inf')
    for u in unvisited_nodes:
        # Modified savings: give higher weight to distance from current node
        savings = 2 * distance_matrix[current_node][depot] + distance_matrix[depot][u] - 1.5 * distance_matrix[current_node][u]
        if savings > best_savings:
            best_savings = savings
            best_node = u
    return best_node
