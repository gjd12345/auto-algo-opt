def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot
    if current_node == depot:
        far_idx = np.argmax(distance_matrix[depot][unvisited_nodes])
        return unvisited_nodes[far_idx]

    best_node = None
    best_score = -float('inf')
    for u in unvisited_nodes:
        travel_cost = distance_matrix[current_node][u]
        # Compute sum of distances from u to all other unvisited nodes (excluding u itself)
        others = unvisited_nodes[unvisited_nodes != u]
        if len(others) > 0:
            sum_dist_to_others = np.sum(distance_matrix[u][others])
        else:
            sum_dist_to_others = 1e-6  # avoid division by zero
        # Regret-like score: high when travel_cost is small relative to isolation (large sum_dist)
        score = sum_dist_to_others / (travel_cost + 1e-6)
        if score > best_score:
            best_score = score
            best_node = u
    return best_node if best_node is not None else unvisited_nodes[0]
