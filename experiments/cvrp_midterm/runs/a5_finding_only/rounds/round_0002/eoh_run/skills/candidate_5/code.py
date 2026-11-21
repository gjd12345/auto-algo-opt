def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes].astype(float)
    mean_dep = float(np.mean(d_dep)) if len(d_dep) > 0 else 1.0
    if mean_dep <= 0:
        mean_dep = 1.0
    rel_dep = d_dep / mean_dep
    load_frac = dem / (float(rest_capacity) + 1e-9)
    score = d_cur - 0.25 * d_dep + 0.6 * mean_dep * load_frac * rel_dep
    return int(unvisited_nodes[np.argmin(score)])