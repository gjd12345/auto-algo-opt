def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes]

    # Term 1: distance to current node (unchanged functional form)
    # Term 2: depot distance replaced by capacity-urgency ratio
    urgency = dem / (rest_capacity + 1e-9)
    # Term 3: remaining capacity term replaced by a depot-proximity pull (kept cheap)
    score = d_cur + 0.5 * urgency * d_dep - 0.1 * d_dep

    # Cheap second ordering stage: among near-tied candidates, prefer larger demand
    k = min(3, len(unvisited_nodes))
    order = np.argsort(score)
    best_idx = order[0]
    best_score = score[best_idx]
    tol = 1e-6 + 0.05 * abs(best_score)
    candidate_set = order[:k]
    # secondary: pick larger demand among near-tied
    for idx in candidate_set:
        if abs(score[idx] - best_score) <= tol:
            if dem[idx] > dem[best_idx]:
                best_idx = idx
    return int(unvisited_nodes[best_idx])