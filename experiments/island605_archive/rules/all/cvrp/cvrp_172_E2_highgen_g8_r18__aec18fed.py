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
        return unvisited_nodes[np.argmax(distance_matrix[depot][unvisited_nodes])]
    else:
        # savings = distance from depot to customer - distance from current to customer
        d_depot = distance_matrix[depot][unvisited_nodes]
        d_current = distance_matrix[current_node][unvisited_nodes]
        savings = d_depot - d_current
        # Prefer larger savings (benefit of combining with current route)
        return unvisited_nodes[np.argmax(savings)]
