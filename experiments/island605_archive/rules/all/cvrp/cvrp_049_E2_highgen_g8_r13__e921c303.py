def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    if current_node == depot:
        # Start with farthest customer from depot to spread routes
        distances_from_depot = distance_matrix[depot][unvisited_nodes]
        return unvisited_nodes[np.argmax(distances_from_depot)]

    best_node = None
    best_score = -float('inf')

    for u in unvisited_nodes:
        dist_to_current = distance_matrix[current_node][u]
        # Compute average distance to all other unvisited nodes
        other_nodes = unvisited_nodes[unvisited_nodes != u]
        if len(other_nodes) == 0:
            avg_dist_to_others = 0.0
        else:
            avg_dist_to_others = np.mean(distance_matrix[u][other_nodes])
        # Regret: difference between distance to current and average to others
        regret = avg_dist_to_others - dist_to_current
        if regret > best_score:
            best_score = regret
            best_node = u

    if best_node is None:
        return depot
    return best_node
