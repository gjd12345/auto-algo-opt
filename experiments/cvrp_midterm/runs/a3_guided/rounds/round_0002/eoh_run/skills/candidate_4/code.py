def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return depot
    cur = distance_matrix[current_node][unvisited_nodes]
    to_depot = distance_matrix[unvisited_nodes, depot]
    stem = distance_matrix[current_node, depot]
    # Pure Clarke-Wright style savings, no span normalisation.
    score = stem + to_depot - cur
    # Cheap second-order stage: among near ties, prefer the node that
    # leaves the largest capacity headroom (i.e. smallest demand).
    order = np.argsort(-score)
    best_score = score[order[0]]
    tol = 1e-9 * (abs(best_score) + 1.0)
    tied = order[score[order] >= best_score - tol]
    if tied.size > 1:
        dem = demands[unvisited_nodes[tied]]
        best = tied[int(np.argmin(dem))]
    else:
        best = order[0]
    return int(unvisited_nodes[best])