def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return depot
    cur = distance_matrix[current_node][unvisited_nodes]
    dep = distance_matrix[depot][unvisited_nodes]
    max_dep = float(np.max(dep)) if dep.size > 0 else 1.0
    if max_dep <= 0:
        max_dep = 1.0
    # Primary: closest current distance penalized by normalized linear depot distance
    scores = cur - 0.8 * (dep / max_dep)
    order = np.argsort(scores)
    best_score = scores[order[0]]
    tol = 1e-9 + 1e-4 * (abs(best_score) + 1.0)
    tied = order[scores[order] <= best_score + tol]
    if tied.size == 1:
        return int(unvisited_nodes[tied[0]])
    tie_nodes = unvisited_nodes[tied]
    combined = distance_matrix[current_node][tie_nodes] + distance_matrix[depot][tie_nodes]
    best_combined = float(np.min(combined))
    finalists = tie_nodes[combined <= best_combined + 1e-9]
    if finalists.size == 1:
        return int(finalists[0])
    cap = max(rest_capacity, 1e-9)
    ratio = demands[finalists] / cap
    return int(finalists[int(np.argmax(ratio))])