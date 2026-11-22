def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot
    if len(unvisited_nodes) == 1:
        return unvisited_nodes[0]

    current_dists = distance_matrix[current_node][unvisited_nodes]
    depot_dists = distance_matrix[depot][unvisited_nodes]

    # Score: how much farther from depot than from current node
    scores = depot_dists - current_dists

    return unvisited_nodes[np.argmax(scores)]
