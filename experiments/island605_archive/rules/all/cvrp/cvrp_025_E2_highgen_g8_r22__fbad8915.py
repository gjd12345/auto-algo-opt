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
        # Regret-based seed: choose customer with largest cost difference
        # between best and second-best insertion into any existing route
        # (For first route, use farthest as proxy)
        if np.all(distance_matrix[depot, unvisited_nodes] == 0):
            return unvisited_nodes[0]
        # Compute a simple regret: for each customer, cost to go from depot directly
        # minus average cost to all other unvisited customers
        depot_dists = distance_matrix[depot, unvisited_nodes]
        mean_dists = np.mean(distance_matrix[unvisited_nodes][:, unvisited_nodes], axis=1)
        regret = depot_dists - mean_dists
        return unvisited_nodes[np.argmax(regret)]

    # When away from depot, compute regret for each candidate:
    # cost to insert after current_node minus cost to insert after the best alternative node
    best_regret = -1
    best_node = None
    for u in unvisited_nodes:
        # Cost to go from current_node to u (then to depot or next best)
        direct_cost = distance_matrix[current_node, u]
        # Alternative: cost from current_node to depot, then to u
        alt_cost = distance_matrix[current_node, depot] + distance_matrix[depot, u]
        regret = alt_cost - direct_cost
        if regret > best_regret:
            best_regret = regret
            best_node = u

    # Voluntary return: if no customer improves over depot return
    return_to_depot = distance_matrix[current_node, depot]
    if best_node is not None and return_to_depot < distance_matrix[current_node, best_node]:
        return depot

    return best_node if best_node is not None else depot
