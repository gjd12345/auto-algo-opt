def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot:
        # At depot: use weighted score favoring far from depot and near to depot
        # alpha near 1: strongly favor far from depot; beta near 0: ignore current distance
        alpha = 0.8
        beta = 0.2
        dist_from_depot = distance_matrix[depot][unvisited_nodes]
        # Normalize distances to [0,1] for combination
        max_dist = np.max(distance_matrix)
        scores = alpha * (dist_from_depot / max_dist) - beta * (dist_from_depot / max_dist)  # simplified: just far-first
        # Actually, at depot, far-first is effective: use farthest
        farthest_idx = np.argmax(dist_from_depot)
        return unvisited_nodes[farthest_idx]
    else:
        # Away from depot: prefer nearest neighbor but allow early return
        # Weighted combination favoring near current node and far from depot (to stay on route)
        dist_current = distance_matrix[current_node][unvisited_nodes]
        dist_depot = distance_matrix[depot][unvisited_nodes]
        max_dist = np.max(distance_matrix)
        # gamma controls trade-off: higher gamma => more weight on staying near current node
        gamma = 0.7
        # Score: lower is better; combine normalized distances
        scores = gamma * (dist_current / max_dist) - (1 - gamma) * (dist_depot / max_dist)
        best_idx = np.argmin(scores)
        best_candidate = unvisited_nodes[best_idx]
        # Early return if best candidate is not closer than returning to depot
        if distance_matrix[current_node][best_candidate] >= distance_matrix[current_node][depot]:
            return depot
        return best_candidate
