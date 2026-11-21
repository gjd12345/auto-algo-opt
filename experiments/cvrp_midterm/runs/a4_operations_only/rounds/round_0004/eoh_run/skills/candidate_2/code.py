def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return depot
    cur = distance_matrix[current_node][unvisited_nodes]
    dep = distance_matrix[depot][unvisited_nodes]
    cur_dep = distance_matrix[current_node][depot]
    safe_cur = np.where(cur <= 1e-12, 1e-12, cur)
    # Savings-style score: how much the candidate pulls us back toward the depot
    # relative to its distance from the current node (multiplicative, not additive).
    scores = (dep - cur_dep) / safe_cur
    # Prefer larger scores (more "on the way home")
    order = np.argsort(-scores)
    best_score = scores[order[0]]
    tol = 1e-9 + 1e-6 * (abs(best_score) + 1.0)
    tied = order[scores[order] >= best_score - tol]
    if tied.size == 1:
        return int(unvisited_nodes[tied[0]])
    tie_nodes = unvisited_nodes[tied]
    # Secondary: smaller detour cost (insertion-ish cost of going through the node)
    detour = (distance_matrix[current_node][tie_nodes]
              + distance_matrix[depot][tie_nodes]
              - cur_dep)
    best = detour.min()
    cands = tie_nodes[detour <= best + 1e-12]
    # Final tie-break: shorter distance to current node
    return int(cands[np.argmin(distance_matrix[current_node][cands])])