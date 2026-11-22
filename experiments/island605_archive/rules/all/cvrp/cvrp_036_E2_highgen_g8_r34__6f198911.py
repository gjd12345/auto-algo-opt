def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot:
        return unvisited_nodes[np.argmax(distance_matrix[depot][unvisited_nodes])]

    d_current = distance_matrix[current_node][unvisited_nodes]
    d_depot = distance_matrix[depot][unvisited_nodes]
    savings = d_depot - d_current
    score = 0.3 * savings + 0.7 * (1.0 / (d_current + 1e-10))
    best_idx = np.argmax(score)
    candidate = unvisited_nodes[best_idx]

    current_to_candidate = distance_matrix[current_node][candidate]
    candidate_to_depot = distance_matrix[candidate][depot]
    current_to_depot = distance_matrix[current_node][depot]
    if current_to_candidate + candidate_to_depot > 1.8 * current_to_depot and len(unvisited_nodes) > 1:
        return depot
    return candidate
