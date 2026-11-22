def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot:
        dists_depot = distance_matrix[depot][unvisited_nodes]
        demand_ratios = demands[unvisited_nodes] / (rest_capacity + 1e-9)
        scores = dists_depot * (1 + 0.5 * demand_ratios)
        return unvisited_nodes[np.argmax(scores)]

    dists_current = distance_matrix[current_node][unvisited_nodes]
    dists_depot = distance_matrix[depot][unvisited_nodes]
    savings = dists_depot - dists_current
    demand_ratios = demands[unvisited_nodes] / (rest_capacity + 1e-9)
    opportunity_cost = 1.0 - demand_ratios
    weighted_savings = savings * (1 + 0.3 * demand_ratios)
    weighted_dist = dists_current * (1 + 0.2 * opportunity_cost)
    scores = weighted_dist - 0.5 * weighted_savings

    best_idx = np.argmin(scores)
    best_node = unvisited_nodes[best_idx]
    dist_to_best = dists_current[best_idx]
    dist_to_depot_from_here = distance_matrix[current_node][depot]

    if dist_to_best > dist_to_depot_from_here and scores[best_idx] > dist_to_depot_from_here:
        return depot

    return best_node
