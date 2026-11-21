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
    # Primary: closest current distance penalized slightly by depot distance
    scores = cur - 0.5 * (dep / max_dep)
    order = np.argsort(scores)
    # Cheap secondary ordering among near-tied candidates
    best_score = scores[order[0]]
    tol = 1e-9 + 1e-6 * (abs(best_score) + 1.0)
    tied = order[scores[order] <= best_score + tol]
    if tied.size == 1:
        return int(unvisited_nodes[tied[0]])
    # Secondary: prefer larger demand relative to remaining capacity (fuller loads)
    cap = max(rest_capacity, 1e-9)
    tie_nodes = unvisited_nodes[tied]
    ratio = demands[tie_nodes] / cap
    best_ratio_idx = int(np.argmax(ratio))
    # Final tie-break: shorter distance to current node
    candidates = tie_nodes[ratio >= ratio[best_ratio_idx] - 1e-12]
    dists = distance_matrix[current_node][candidates]
    return int(candidates[np.argmin(dists)])