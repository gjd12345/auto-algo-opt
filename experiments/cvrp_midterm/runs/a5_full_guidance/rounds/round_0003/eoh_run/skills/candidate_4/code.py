def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return depot
    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    d_cur_dep = distance_matrix[current_node][depot]
    # Clarke-Wright savings, scale-free normalised by the round-trip length.
    savings = d_cur_dep + d_dep - d_cur
    trip = d_cur + d_dep
    trip = np.where(trip <= 0, 1.0, trip)
    score = -(savings / trip)  # smaller is better
    # Secondary: among near-ties, prefer filling remaining capacity efficiently.
    order = np.argsort(score)
    best = order[0]
    best_score = score[best]
    spread = score[order[-1]] - best_score
    if spread <= 0:
        spread = 1.0
    window = 0.10 * spread
    cap = rest_capacity if rest_capacity > 0 else 1.0
    chosen = best
    best_util = demands[unvisited_nodes[best]] / cap
    for idx in order[1:]:
        if score[idx] - best_score > window:
            break
        util = demands[unvisited_nodes[idx]] / cap
        if util > best_util:
            best_util = util
            chosen = idx
    return unvisited_nodes[chosen]