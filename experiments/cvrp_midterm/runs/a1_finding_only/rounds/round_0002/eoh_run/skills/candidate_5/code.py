def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes].astype(float)
    d_dep = distance_matrix[depot][unvisited_nodes].astype(float)
    dem = demands[unvisited_nodes].astype(float)

    denom = d_cur + d_dep
    denom = np.where(denom <= 0.0, 1e-12, denom)
    near_ratio = d_cur / denom
    score = -near_ratio

    cap = float(rest_capacity) if rest_capacity > 0 else 1.0
    dem_frac = dem / cap
    score = score + 0.55 * dem_frac

    max_dep = float(np.max(d_dep)) + 1e-12
    dep_norm = d_dep / max_dep
    score = score - 0.15 * dep_norm

    max_cur = float(np.max(d_cur)) + 1e-12
    score = score - 1e-9 * (d_cur / max_cur)

    idx = int(np.argmax(score))
    return int(unvisited_nodes[idx])