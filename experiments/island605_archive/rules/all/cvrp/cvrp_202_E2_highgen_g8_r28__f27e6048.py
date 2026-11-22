def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    # Distance from depot to each candidate
    depot_dists = distance_matrix[depot, unvisited_nodes]
    # Distance from current node to each candidate
    current_dists = distance_matrix[current_node, unvisited_nodes]

    # Score: prefer far from depot and close to current, with a small epsilon to avoid division by zero
    scores = depot_dists / (current_dists + 1e-10)

    # Return the candidate with highest score; if tie, choose the one with smaller current distance
    max_score = np.max(scores)
    candidates = unvisited_nodes[scores == max_score]
    if len(candidates) == 1:
        return candidates[0]
    else:
        return candidates[np.argmin(distance_matrix[current_node, candidates])]
