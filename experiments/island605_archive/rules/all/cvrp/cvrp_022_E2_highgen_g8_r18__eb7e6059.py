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

    if current_node == depot:
        # Start route: choose customer with largest saving relative to serving it alone
        savings = []
        for u in unvisited_nodes:
            # Saving = (depot->u + u->depot) - (depot->u) = u->depot
            # But we want to seed toward distant clusters: use distance from depot
            savings.append(distance_matrix[depot][u])
        return unvisited_nodes[np.argmax(savings)]

    # Compute combined score for each candidate:
    # score = savings(s_i, s_j) - capacity_weight * (distance from current node)
    # where savings(s_i, s_j) = d(current, depot) + d(depot, u) - d(current, u)
    # This penalizes nodes far from current location but rewards those with high depot savings.
    best_score = -np.inf
    best_node = depot
    for u in unvisited_nodes:
        saving = distance_matrix[current_node][depot] + distance_matrix[depot][u] - distance_matrix[current_node][u]
        # Capacity penalty: proportion of rest_capacity consumed
        capacity_penalty = demands[u] / rest_capacity if rest_capacity > 0 else 0
        score = saving - 1.5 * capacity_penalty * distance_matrix[current_node][u]
        if score > best_score:
            best_score = score
            best_node = u

    # If no positive score, return to depot
    if best_score <= 0 or best_node == depot:
        return depot
    return best_node
