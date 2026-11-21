def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    idx = np.asarray(unvisited_nodes, dtype=int)
    d_cur = distance_matrix[current_node][idx].astype(float)
    d_dep = distance_matrix[depot][idx].astype(float)
    dem = demands[idx].astype(float)
    cap = float(rest_capacity) if rest_capacity > 0 else 1.0

    max_d_cur = np.max(d_cur) if d_cur.size > 0 else 1.0
    max_d_dep = np.max(d_dep) if d_dep.size > 0 else 1.0
    max_d = max(max_d_cur, max_d_dep, 1e-9)

    fill = dem / cap
    norm_cur = d_cur / max_d
    norm_dep = d_dep / max_d

    score = 0.60 * norm_cur + 0.25 * norm_dep - 0.15 * fill
    return int(idx[np.argmin(score)])