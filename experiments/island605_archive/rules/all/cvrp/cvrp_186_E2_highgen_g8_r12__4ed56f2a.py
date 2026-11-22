def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    # Precompute distances from current_node and from depot to each unvisited node
    dist_from_curr = distance_matrix[current_node][unvisited_nodes]
    dist_from_depot = distance_matrix[depot][unvisited_nodes]

    # Compute savings: d(current, depot) + d(node, depot) - d(current, node)
    savings = distance_matrix[current_node][depot] + dist_from_depot - dist_from_curr

    # Compute regret: for each node, the second-best savings from depot minus best savings from depot
    # Here we approximate by looking at the gap between the node's depot distance and the next best depot distance among all unvisited
    depot_dists = dist_from_depot
    if len(depot_dists) > 1:
        sorted_depot = np.sort(depot_dists)
        best = sorted_depot[0]
        second_best = sorted_depot[1] if len(sorted_depot) > 1 else best
        # For each node, regret = (second_best - depot_dists[i]) clipped to non-negative
        regrets = np.maximum(second_best - depot_dists, 0)
    else:
        regrets = np.zeros_like(depot_dists)

    # Score = savings - alpha * regret, where alpha is a parameter (e.g., 0.5)
    alpha = 0.5
    scores = savings - alpha * regrets

    best_idx = np.argmax(scores)
    return unvisited_nodes[best_idx]
