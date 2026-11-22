def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot
    # Score: distance from depot to node minus distance from current node to node
    depot_dists = distance_matrix[depot][unvisited_nodes]
    curr_dists = distance_matrix[current_node][unvisited_nodes]
    scores = depot_dists - curr_dists
    best_idx = np.argmax(scores)
    return unvisited_nodes[best_idx]
