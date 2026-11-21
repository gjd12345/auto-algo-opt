def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return depot
    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    # Clarke-Wright savings relative to the extra detour incurred by visiting
    # this node from the current position instead of returning to the depot.
    saving = d_cur + d_dep - d_cur  # == d_dep; kept explicit for clarity
    detour = d_cur + d_dep
    detour = np.where(detour <= 0, 1.0, detour)
    score = saving / detour  # scale-free, in (0, 1]
    order = np.argsort(score)[::-1]  # higher savings ratio preferred
    best = order[0]
    best_score = score[best]
    spread = best_score - score[order[-1]]
    if spread <= 0:
        spread = 1.0
    window = 0.20 * spread
    chosen = best
    cap_target = rest_capacity
    best_fill = -np.inf
    for idx in order:
        if best_score - score[idx] > window:
            break
        dem = demands[unvisited_nodes[idx]]
        fill = -abs(cap_target - dem * 2.0) if cap_target > 0 else -dem
        if fill > best_fill:
            best_fill = fill
            chosen = idx
    return unvisited_nodes[chosen]