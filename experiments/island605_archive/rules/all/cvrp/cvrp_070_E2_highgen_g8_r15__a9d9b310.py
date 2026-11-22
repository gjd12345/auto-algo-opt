def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    if current_node == depot:
        dists_from_depot = distance_matrix[depot][unvisited_nodes]
        return unvisited_nodes[np.argmax(dists_from_depot)]

    best_node = None
    best_score = float('inf')
    avg_demand = np.mean(demands[unvisited_nodes]) if len(unvisited_nodes) > 0 else 1.0
    scaling = rest_capacity / (avg_demand + 1e-10)
    for u in unvisited_nodes:
        d_current = distance_matrix[current_node][u]
        d_depot = distance_matrix[depot][u]
        regret = max(0, d_depot - d_current)
        score = d_current - 0.3 * regret * scaling
        if score < best_score:
            best_score = score
            best_node = u

    best_dist = distance_matrix[current_node][best_node]
    dist_to_depot = distance_matrix[current_node][depot]
    if dist_to_depot < best_dist and rest_capacity < avg_demand:
        return depot

    return best_node
