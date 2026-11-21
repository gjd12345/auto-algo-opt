def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes]
    residual = rest_capacity - dem
    # Prefer: close to current (low d_cur), far from depot (high d_dep),
    # and leaving low residual capacity (good packing).
    score = d_cur - 0.3 * d_dep + 0.1 * residual
    return int(unvisited_nodes[np.argmin(score)])