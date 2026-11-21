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
    # Primary: closest current distance penalized by exponential normalized depot distance
    scores = cur + 0.3 * max_dep * (1.0 - np.exp(-dep / max_dep))
    order = np.argsort(scores)
    best_score = scores[order[0]]
    tol = 1e-9 + 5e-3 * (abs(best_score) + 1.0)
    tied = order[scores[order] <= best_score + tol]
    if tied.size == 1:
        return int(unvisited_nodes[tied[0]])
    # Secondary: among near-tied, minimize combined current+depot minus normalized demand bonus
    tie_nodes = unvisited_nodes[tied]
    combined = distance_matrix[current_node][tie_nodes] + distance_matrix[depot][tie_nodes]
    cap = max(rest_capacity, 1e-9)
    bonus = 0.2 * (demands[tie_nodes] / cap)
    adj = combined - bonus
    best_adj = float(np.min(adj))
    finalists = tie_nodes[adj <= best_adj + 1e-9]
    if finalists.size == 1:
        return int(finalists[0])
    # Final tie-break: prefer larger demand relative to remaining capacity
    ratio = demands[finalists] / cap
    return int(finalists[int(np.argmax(ratio))])