def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return depot
    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    # Scale-invariant primary score: relative proximity to current node.
    denom = d_cur + d_dep
    denom = np.where(denom <= 0, 1.0, denom)
    score = d_cur / denom
    order = np.argsort(score)
    best = order[0]
    best_score = score[best]
    spread = score[order[-1]] - best_score
    if spread <= 0:
        spread = 1.0
    # Widened near-tie window: 20% of local spread (relative, scale-free).
    window = 0.20 * spread
    chosen = best
    # Secondary tie-break: demand per unit distance (higher is better).
    best_ratio = -np.inf
    for idx in order:
        if score[idx] - best_score > window:
            break
        n = unvisited_nodes[idx]
        d = d_cur[idx]
        ratio = demands[n] / d if d > 0 else demands[n] / 1e-12
        if ratio > best_ratio:
            best_ratio = ratio
            chosen = idx
    return unvisited_nodes[chosen]