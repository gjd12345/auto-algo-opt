def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot
    if len(unvisited_nodes) == 1:
        return unvisited_nodes[0]

    current_dists = distance_matrix[current_node][unvisited_nodes]
    depot_dists = distance_matrix[depot][unvisited_nodes]
    best_scores = np.full(len(unvisited_nodes), np.inf)

    for i, node in enumerate(unvisited_nodes):
        other_nodes = unvisited_nodes[np.arange(len(unvisited_nodes)) != i]
        if len(other_nodes) > 0:
            dist_to_others = distance_matrix[node][other_nodes]
            min_to_other = np.min(dist_to_others)
        else:
            min_to_other = depot_dists[i]
        # Score: how much cheaper it is to visit now vs. later (later = go depot then to other)
        now_cost = current_dists[i]
        later_cost = depot_dists[i] + min_to_other
        best_scores[i] = later_cost - now_cost

    best_idx = np.argmax(best_scores)
    if best_scores[best_idx] < 1e-6:
        return unvisited_nodes[np.argmin(current_dists)]
    return unvisited_nodes[best_idx]
