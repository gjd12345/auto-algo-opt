def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes]

    total_demand = float(np.sum(demands))
    if total_demand <= 0:
        total_demand = 1.0

    # Normalize distances by the maximum pair distance for scale robustness
    dmax = float(np.max(distance_matrix))
    if dmax <= 0:
        dmax = 1.0

    # Prefer nodes that are close to current, close to depot, and small demand
    # (small demand leaves room for more customers on the route)
    score = (d_cur / dmax) + 0.3 * (d_dep / dmax) + 0.5 * (dem / total_demand) * 10.0

    return int(unvisited_nodes[np.argmin(score)])