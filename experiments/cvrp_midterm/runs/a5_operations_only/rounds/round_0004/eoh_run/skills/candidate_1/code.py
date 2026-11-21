def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    cap = rest_capacity if rest_capacity > 0 else 1.0

    savings = distance_matrix[current_node][depot] + d_dep - d_cur
    dem = demands[unvisited_nodes]
    fill = dem / cap

    primary = 1.2 * (d_cur ** 2) / (cap + 1e-6) - 0.7 * savings - 0.4 * fill

    best_val = primary.min()
    tol = 1e-6 * (abs(best_val) + 1.0)
    close = np.where(primary <= best_val + tol)[0]

    if close.size > 1:
        candidates = unvisited_nodes[close]
        secondary = distance_matrix[current_node][candidates] - 0.5 * demands[candidates] / cap
        return int(candidates[np.argmin(secondary)])

    return int(unvisited_nodes[int(np.argmin(primary))])