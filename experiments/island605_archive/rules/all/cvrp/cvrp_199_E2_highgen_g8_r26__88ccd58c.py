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
    if len(unvisited_nodes) == 0:
        return depot

    # Compute savings: (distance from current to depot + distance from depot to customer)
    #                  - distance from current to customer
    distances_to_depot = distance_matrix[current_node][depot]
    depot_to_customer = distance_matrix[depot][unvisited_nodes]
    current_to_customer = distance_matrix[current_node][unvisited_nodes]
    savings = distances_to_depot + depot_to_customer - current_to_customer

    # Select customer with maximum savings (prefer customers that are much closer than depot return)
    best_idx = unvisited_nodes[np.argmax(savings)]
    return best_idx
