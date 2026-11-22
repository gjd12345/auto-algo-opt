def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    # At depot, seed routes toward farthest customers
    if current_node == depot:
        dists_depot = distance_matrix[depot][unvisited_nodes]
        return unvisited_nodes[np.argmax(dists_depot)]

    # Weighted combination: savings vs. immediate distance (alpha in [0,1])
    alpha = 0.7  # weight for savings; 1 - alpha for distance penalty
    current_to_depot = distance_matrix[current_node][depot]
    depot_to_candidates = distance_matrix[depot][unvisited_nodes]
    current_to_candidates = distance_matrix[current_node][unvisited_nodes]
    savings = current_to_depot + depot_to_candidates - current_to_candidates

    # Score = alpha * savings - (1 - alpha) * current_to_candidates
    scores = alpha * savings - (1 - alpha) * current_to_candidates
    return unvisited_nodes[np.argmax(scores)]
