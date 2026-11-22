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

    # When rest_capacity is below average demand, switch to nearest neighbor
    avg_demand = demands[1:].mean()
    if rest_capacity < avg_demand:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    # Regret-based selection: for each candidate, compute estimated cost if postponed
    best_node = unvisited_nodes[0]
    best_score = float('-inf')
    for u in unvisited_nodes:
        # Immediate cost of visiting u now
        immediate_cost = distance_matrix[current_node][u]
        # Estimated cost if u is served later in a new route (from depot)
        future_cost_estimate = distance_matrix[depot][u]
        # Score: high regret = large difference between future and immediate cost
        regret = future_cost_estimate - immediate_cost
        # Also consider distance from depot to bias toward far customers early
        score = regret + 0.3 * distance_matrix[depot][u]
        if score > best_score:
            best_score = score
            best_node = u
    return best_node
