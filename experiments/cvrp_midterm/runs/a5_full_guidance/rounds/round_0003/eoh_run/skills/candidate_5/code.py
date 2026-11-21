def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return depot
    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    d_cur_dep = distance_matrix[current_node][depot]
    # Clarke-Wright savings normalised by the depot round-trip from the current node.
    savings = d_cur_dep + d_dep - d_cur
    trip = d_cur + d_dep
    trip = np.where(trip <= 0, 1.0, trip)
    score = -(savings / trip)
    order = np.argsort(score)
    best = order[0]
    best_score = score[best]
    # Scale-invariant relative near-tie gate: window is a fraction of the best magnitude.
    mag = max(abs(best_score), 1e-9)
    window = 0.05 * mag
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