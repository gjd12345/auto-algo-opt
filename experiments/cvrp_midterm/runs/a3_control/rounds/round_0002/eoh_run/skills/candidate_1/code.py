def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes]
    cap = max(rest_capacity, 1e-9)
    # load pressure: how full relative to demands
    load_ratio = dem / cap
    # weight depot pull up as capacity shrinks
    depot_w = 1.0 + (1.0 - min(rest_capacity / (cap + 1e-9), 1.0))
    score = d_cur + 0.15 * depot_w * d_dep + 0.3 * load_ratio * d_cur
    return int(unvisited_nodes[np.argmin(score)])