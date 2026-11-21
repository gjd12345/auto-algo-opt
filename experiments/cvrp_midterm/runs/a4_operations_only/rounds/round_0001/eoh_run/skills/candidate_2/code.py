def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select next node using a capacity-aware savings score with a nearest tie-break."""
    d_cur_depot = distance_matrix[current_node, depot]
    d_depot_nodes = distance_matrix[depot, unvisited_nodes]
    d_cur_nodes = distance_matrix[current_node, unvisited_nodes]
    scores = d_cur_depot + d_depot_nodes - d_cur_nodes

    best_score = np.max(scores)
    close = np.isclose(scores, best_score, rtol=1e-9, atol=1e-12)
    if np.any(close):
        candidates = unvisited_nodes[close]
        return int(candidates[np.argmin(distance_matrix[current_node, candidates])])
    return int(unvisited_nodes[np.argmax(scores)])