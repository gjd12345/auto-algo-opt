def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return depot
    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    # Primary: relative proximity that also rewards being far from depot
    # (i.e., customers that would be expensive to leave behind). Scale-free.
    denom = d_cur + d_dep
    denom = np.where(denom <= 0, 1.0, denom)
    score = d_cur / denom
    # Secondary: among near-ties (relative to local spread), prefer larger demand.
    order = np.argsort(score)
    best = order[0]
    best_score = score[best]
    spread = score[order[-1]] - best_score
    if spread <= 0:
        spread = 1.0
    window = 0.10 * spread
    chosen = best
    best_demand = demands[unvisited_nodes[best]]
    for idx in order[1:]:
        if score[idx] - best_score > window:
            break
        dem = demands[unvisited_nodes[idx]]
        if dem > best_demand:
            best_demand = dem
            chosen = idx
    return unvisited_nodes[chosen]