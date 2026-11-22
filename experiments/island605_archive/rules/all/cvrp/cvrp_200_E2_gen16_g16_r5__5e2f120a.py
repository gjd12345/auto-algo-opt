def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot
    dists_current = distance_matrix[current_node][unvisited_nodes]
    dists_depot = distance_matrix[depot][unvisited_nodes]
    epsilon = 1e-10
    ratios = (dists_depot ** 2) / (dists_current + epsilon)
    best_idx = np.argmax(ratios)
    return unvisited_nodes[best_idx]
