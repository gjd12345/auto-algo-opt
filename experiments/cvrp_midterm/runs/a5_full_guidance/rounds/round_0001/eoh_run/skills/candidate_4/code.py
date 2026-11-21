def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes]

    # Relative detour term (scale-invariant): extra distance relative to leg length.
    base = distance_matrix[current_node][depot]
    denom = d_cur + d_dep
    denom = np.where(denom <= 0, 1.0, denom)
    rel_extra = (d_cur + d_dep - base) / denom

    # Depot-distance term (kept, but made relative to current->depot leg).
    base_safe = base if base > 0 else 1.0
    rel_depot = d_dep / base_safe

    # Capacity term (kept): prefer larger demand utilization, scaled to capacity.
    cap = rest_capacity if rest_capacity > 0 else 1.0
    cap_term = dem / cap

    score = rel_extra + 0.5 * rel_depot - 0.2 * cap_term

    order = np.argsort(score)
    best = order[0]

    # Cheap second ordering stage: among near-ties on relative score, break by absolute distance.
    best_score = score[best]
    tol = 0.05 * (abs(best_score) + 1e-9)
    near_mask = np.abs(score - best_score) <= tol
    candidates = np.where(near_mask)[0]
    if candidates.size > 1:
        sub = distance_matrix[current_node][unvisited_nodes[candidates]]
        best = candidates[np.argmin(sub)]

    return int(unvisited_nodes[best])