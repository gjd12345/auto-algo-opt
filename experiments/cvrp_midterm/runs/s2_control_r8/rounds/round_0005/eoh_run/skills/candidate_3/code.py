def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return 0

    nodes = np.asarray(unvisited_nodes)
    d_cur = distance_matrix[current_node][nodes].astype(float)
    d_dep = distance_matrix[depot][nodes].astype(float)
    dem = demands[nodes].astype(float)

    cap = float(rest_capacity) if rest_capacity > 0 else 1.0
    total_dem = float(np.sum(dem)) + 1e-9
    fill = 1.0 - min(1.0, cap / (cap + total_dem))

    w_dep = 0.15 + 0.70 * fill
    w_dem = 0.08 / (cap + 1e-9)

    score = d_cur - w_dep * d_dep + w_dem * dem * d_dep
    return int(nodes[int(np.argmin(score))])