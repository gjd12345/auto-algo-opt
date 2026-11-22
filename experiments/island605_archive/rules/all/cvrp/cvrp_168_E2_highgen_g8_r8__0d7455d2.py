def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot:
        # When starting a new route, choose the farthest unvisited customer
        dists_from_depot = distance_matrix[depot][unvisited_nodes]
        return unvisited_nodes[np.argmax(dists_from_depot)]

    # Compute distance from current node to each unvisited customer
    current_dists = distance_matrix[current_node][unvisited_nodes]
    # Compute distance from depot to each unvisited customer
    depot_dists = distance_matrix[depot][unvisited_nodes]
    # Score: prioritize customers that are close to current but far from depot (savings-like)
    score = depot_dists - current_dists

    # Apply demand penalty when remaining capacity is below average demand
    if rest_capacity < np.mean(demands[unvisited_nodes]):
        demand_ratios = demands[unvisited_nodes] / rest_capacity
        score -= 10.0 * demand_ratios

    # Return the customer with the highest score
    return unvisited_nodes[np.argmax(score)]
