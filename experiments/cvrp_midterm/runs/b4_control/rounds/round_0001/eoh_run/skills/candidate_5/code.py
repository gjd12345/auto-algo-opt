def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes]
    # Normalize components
    max_d_cur = np.max(d_cur) if len(d_cur) > 0 else 1.0
    max_d_dep = np.max(d_dep) if len(d_dep) > 0 else 1.0
    max_dem = np.max(dem) if len(dem) > 0 else 1.0
    if max_d_cur == 0: max_d_cur = 1.0
    if max_d_dep == 0: max_d_dep = 1.0
    if max_dem == 0: max_dem = 1.0
    # Score: prefer close to current, far from depot (to avoid returning), and high demand utilization
    score = (d_cur / max_d_cur) * 0.6 + (d_dep / max_d_dep) * 0.2 - (dem / max_dem) * 0.2
    return unvisited_nodes[np.argmin(score)]