def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    best_node = None
    best_score = -float('inf')
    dist_to_depot = distance_matrix[depot][unvisited_nodes]
    dist_from_current = distance_matrix[current_node][unvisited_nodes]

    for i, node in enumerate(unvisited_nodes):
        # Regret score: difference between best cost if served later (from depot) vs now (from current)
        # plus a small bonus for larger demand to avoid leftover capacity waste
        cost_now = dist_from_current[i]
        cost_later = dist_to_depot[i]
        regret = cost_later - cost_now
        demand_ratio = demands[node] / rest_capacity if rest_capacity > 0 else 0
        score = regret + 0.5 * demand_ratio * dist_to_depot[i]
        if score > best_score:
            best_score = score
            best_node = node

    if best_node is None:
        return depot
    return best_node
