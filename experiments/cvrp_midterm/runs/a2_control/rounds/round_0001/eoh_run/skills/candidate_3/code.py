def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes].astype(float)
    cap = max(float(rest_capacity), 1e-9)
    score = d_cur + 0.3 * d_dep - 0.5 * (dem / cap) * d_cur.mean()
    return int(unvisited_nodes[np.argmin(score)])