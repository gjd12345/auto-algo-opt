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

    # For each unvisited customer, compute insertion costs at the end of the current route
    # and at the depot (as if returning to depot and starting a new route from there).
    best_costs = np.full(len(unvisited_nodes), np.inf)
    second_best_costs = np.full(len(unvisited_nodes), np.inf)

    # Current route end cost: distance from current_node to customer
    route_end_costs = distance_matrix[current_node][unvisited_nodes]

    # Alternative: return to depot then go to customer
    depot_start_costs = distance_matrix[current_node][depot] + distance_matrix[depot][unvisited_nodes]

    for i, cust in enumerate(unvisited_nodes):
        costs = np.array([route_end_costs[i], depot_start_costs[i]])
        costs.sort()
        best_costs[i] = costs[0]
        second_best_costs[i] = costs[1] if len(costs) > 1 else costs[0]

    regret = second_best_costs - best_costs
    # In case of ties, prefer shorter route_end_cost
    best_idx = np.argmax(regret)
    return unvisited_nodes[best_idx]
