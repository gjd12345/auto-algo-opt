def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return depot
    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    # Scale-free relative proximity: distance to current node normalised by
    # the sum of distances to current node and depot. Ranges in [0, 1].
    denom = d_cur + d_dep
    denom = np.where(denom <= 0, 1.0, denom)
    score = d_cur / denom
    # Secondary cheap ordering among near-ties: prefer larger demand served
    # (fills the vehicle efficiently) when primary scores are close.
    order = np.argsort(score)
    best = order[0]
    best_score = score[best]
    # Near-tie window relative to best score (scale-free)
    window = 0.05
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