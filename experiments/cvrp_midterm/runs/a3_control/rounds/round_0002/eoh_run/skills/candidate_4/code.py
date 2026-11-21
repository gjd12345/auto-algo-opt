def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes]
    cap = max(rest_capacity, 1e-9)
    load_ratio = dem / cap
    # stronger capacity pressure: encourages consolidation when nearing full
    fill = min(rest_capacity / (cap + 1e-9), 1.0)
    depot_w = 1.0 + 2.0 * (1.0 - fill)
    # weight demand contribution more heavily; emphasize proximity to depot as load grows
    score = d_cur + 0.35 * depot_w * d_dep + 0.7 * load_ratio * d_cur - 0.1 * dem
    return int(unvisited_nodes[np.argmin(score)])