def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot:
        return unvisited_nodes[np.argmax(distance_matrix[depot][unvisited_nodes])]
    if len(unvisited_nodes) == 1:
        return unvisited_nodes[0]
    dist_curr = distance_matrix[current_node][unvisited_nodes]
    avg_dist = np.array([
        np.mean(distance_matrix[u][unvisited_nodes])
        for u in unvisited_nodes
    ])
    regret = dist_curr - avg_dist
    return unvisited_nodes[np.argmin(regret)]
