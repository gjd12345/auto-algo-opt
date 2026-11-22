def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot:
        # Seed: choose customer with largest savings (dist(depot,u) + dist(depot,v) - dist(u,v)) relative to closest other unvisited
        best_seed = None
        best_savings = -1.0
        for u in unvisited_nodes:
            # Savings = dist(depot,u) + dist(depot,closest_other) - dist(u,closest_other)
            others = [v for v in unvisited_nodes if v != u]
            if len(others) == 0:
                savings = 0
            else:
                closest_dist = np.min(distance_matrix[u][others])
                savings = distance_matrix[depot][u] + distance_matrix[depot][others[np.argmin(distance_matrix[u][others])]] - closest_dist
            if savings > best_savings:
                best_savings = savings
                best_seed = u
        return best_seed if best_seed is not None else unvisited_nodes[0]

    # For subsequent nodes: choose customer that maximizes distance reduction vs returning to depot
    best_node = None
    best_saving = -float('inf')
    for u in unvisited_nodes:
        # Saving = dist(current_node, depot) + dist(depot, u) - dist(current_node, u)
        saving = distance_matrix[current_node][depot] + distance_matrix[depot][u] - distance_matrix[current_node][u]
        if saving > best_saving:
            best_saving = saving
            best_node = u
    return best_node if best_node is not None else depot
