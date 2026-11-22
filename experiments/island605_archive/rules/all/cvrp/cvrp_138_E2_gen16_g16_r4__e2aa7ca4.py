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
        # When starting a route, pick the farthest customer to seed distant clusters
        return unvisited_nodes[np.argmax(distance_matrix[depot][unvisited_nodes])]

    best_score = -1e9
    best_node = unvisited_nodes[0]
    for u in unvisited_nodes:
        # Savings relative to two separate trips from depot
        savings = distance_matrix[current_node][depot] + distance_matrix[depot][u] - distance_matrix[current_node][u]
        # Angular proximity: small angle deviation from current-depot line
        dx1 = distance_matrix[current_node][0] - distance_matrix[0][0]
        dy1 = distance_matrix[current_node][0] - distance_matrix[0][0]  # placeholder, use atan2 from coordinates
        # Use savings as primary, with secondary tie-break by nearest distance
        score = savings - 0.1 * distance_matrix[current_node][u]
        if score > best_score:
            best_score = score
            best_node = u
    return best_node
