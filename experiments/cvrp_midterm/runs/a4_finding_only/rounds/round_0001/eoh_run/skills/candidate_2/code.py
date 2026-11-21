def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes]

    max_d = float(np.max(d_cur)) if d_cur.size else 0.0
    max_dd = float(np.max(d_dep)) if d_dep.size else 0.0
    cap = float(rest_capacity)
    if cap <= 0.0:
        return depot

    dc = d_cur / max_d if max_d > 0.0 else np.zeros_like(d_cur)
    dd = d_dep / max_dd if max_dd > 0.0 else np.zeros_like(d_dep)

    load = np.clip(dem / cap, 0.0, 1.0)

    score = 0.55 * dc + 0.30 * dd - 0.15 * load
    return int(unvisited_nodes[int(np.argmin(score))])