def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    if current_node == depot:
        depot_distances = distance_matrix[depot][unvisited_nodes]
        return unvisited_nodes[np.argmax(depot_distances)]

    # Compute savings: distance(current, customer) + distance(depot, customer)
    # vs. just distance(depot, customer) if served later from a new route
    dist_current = distance_matrix[current_node][unvisited_nodes]
    dist_depot = distance_matrix[depot][unvisited_nodes]

    # Savings regret = (cost to serve now) - (cost to serve later from depot)
    # Serve now cost: dist_current + return_to_depot if no capacity left
    # Serve later cost: dist_depot (from depot on next route)
    # Use maximum demand as proxy for capacity pressure
    max_demand = np.max(demands[unvisited_nodes])
    capacity_pressure = rest_capacity / (max_demand + 1e-6)
    serve_now_cost = dist_current + distance_matrix[current_node][depot] * (1.0 / (capacity_pressure + 1e-6))
    serve_later_cost = dist_depot
    regret = serve_later_cost - serve_now_cost

    best_idx = np.argmax(regret)
    if regret[best_idx] <= 0:
        best_idx = np.argmin(dist_current)
    return unvisited_nodes[best_idx]
