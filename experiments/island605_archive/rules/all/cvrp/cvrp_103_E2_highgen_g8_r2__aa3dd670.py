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
        # Seed route with farthest feasible customer from depot
        dists_from_depot = distance_matrix[depot][unvisited_nodes]
        return unvisited_nodes[np.argmax(dists_from_depot)]

    # Compute savings: s(i,j) = d(depot,i) + d(depot,j) - d(i,j)
    # For each unvisited customer j, savings = d(depot, current) + d(depot, j) - d(current, j)
    d_from_depot_cur = distance_matrix[depot][current_node]
    d_cur_to_cust = distance_matrix[current_node][unvisited_nodes]
    d_depot_to_cust = distance_matrix[depot][unvisited_nodes]
    savings = d_from_depot_cur + d_depot_to_cust - d_cur_to_cust

    # Prefer customer with maximum savings
    best_idx = np.argmax(savings)
    best_customer = unvisited_nodes[best_idx]
    best_dist = d_cur_to_cust[best_idx]

    # If returning to depot is cheaper than going to best customer, close route
    if distance_matrix[current_node][depot] < best_dist:
        return depot

    return best_customer
