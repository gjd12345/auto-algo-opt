def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return depot
    if unvisited_nodes.size == 1:
        return int(unvisited_nodes[0])

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    base = d_cur - 0.6 * d_dep

    order = np.argsort(base)
    best_idx = order[0]
    best_score = float(base[best_idx])

    span = float(d_cur.max() - d_cur.min()) if d_cur.size > 1 else 0.0
    band = 1e-2 * span + 1e-12

    second_score = float(base[order[1]])
    if second_score - best_score > band:
        return int(unvisited_nodes[best_idx])

    # Near-tie: refine with capacity-fit term among candidates within band.
    cap = float(rest_capacity)
    best_val = None
    best_node = int(unvisited_nodes[best_idx])
    for i in range(unvisited_nodes.size):
        b = float(base[i])
        if b - best_score > band:
            continue
        dem = float(demands[unvisited_nodes[i]])
        # Prefer candidates that fit snugly: smaller leftover capacity is better.
        fit = dem / cap if cap > 0 else 0.0
        val = b - 0.5 * fit * (span if span > 0 else 1.0)
        if best_val is None or val < best_val:
            best_val = val
            best_node = int(unvisited_nodes[i])
    return best_node