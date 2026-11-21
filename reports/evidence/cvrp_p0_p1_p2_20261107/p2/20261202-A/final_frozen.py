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
    if unvisited_nodes.size == 0:
        return 0

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    d_base = distance_matrix[depot][current_node]

    # Clarke-Wright style saving: serving candidate directly from current node
    # instead of a separate current->depot plus depot->candidate trip.
    saving = d_base + d_dep - d_cur

    # Capacity utilization of the vehicle *after* serving the candidate.
    dem = demands[unvisited_nodes]
    util = (dem + 1e-9) / (rest_capacity + 1e-9)
    util = np.clip(util, 0.0, 1.0)

    # Bonus for customers that nearly fill the remaining capacity, scaled by
    # how far the customer is from the depot (avoid stranding far customers).
    bonus = util * util * d_dep

    score = saving + bonus
    return int(unvisited_nodes[np.argmax(score)])