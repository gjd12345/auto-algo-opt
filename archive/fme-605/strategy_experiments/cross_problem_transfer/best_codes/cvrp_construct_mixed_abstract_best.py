# 正式证据来源: cross_problem_transfer/cvrp_construct/mixed_abstract/3102
# Core/primary held-out score: 16.5538643973
def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    if current_node == depot:
        return unvisited_nodes[np.argmax(distance_matrix[depot][unvisited_nodes])]

    best_customer = None
    best_score = -float('inf')
    current_dists = distance_matrix[current_node][unvisited_nodes]
    depot_dists = distance_matrix[depot][unvisited_nodes]

    for i, u in enumerate(unvisited_nodes):
        # Nearest-neighbor distance (negative, minimize)
        nearest_dist = current_dists[i]
        # Savings component
        savings = distance_matrix[current_node][depot] + depot_dists[i] - nearest_dist
        # Regret component (penalty for postponing)
        regret = depot_dists[i] - nearest_dist
        # Normalized capacity pressure
        capacity_pressure = (demands[u] / rest_capacity) if rest_capacity > 0 else 0

        # Combined score with adjusted weights
        score = -0.3 * nearest_dist + 0.4 * savings + 0.2 * regret + 0.1 * capacity_pressure

        if score > best_score:
            best_score = score
            best_customer = u

    # Early depot return heuristic (more conservative)
    serving_cost = distance_matrix[current_node][best_customer] + distance_matrix[best_customer][depot]
    return_cost = distance_matrix[current_node][depot]
    if serving_cost > 1.5 * return_cost and rest_capacity < demands[unvisited_nodes].max() * 1.2:
        return depot

    return best_customer
