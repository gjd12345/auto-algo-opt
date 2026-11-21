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

    # Replaced term: squared distance-to-current -> round-trip estimate per unit capacity
    trip = (d_cur + d_dep) / (cap + 1e-6)

    primary = 1.1 * trip - 0.8 * savings - 0.5 * fill

    best_val = primary.min()
    tol = 1e-6 * (abs(best_val) + 1.0)
    close = np.where(primary <= best_val + tol)[0]

    if close.size > 1:
        candidates = unvisited_nodes[close]
        secondary = -0.6 * demands[candidates] / cap + distance_matrix[current_node][candidates] / (cap + 1e-6)
        return int(candidates[np.argmin(secondary)])

    return int(unvisited_nodes[int(np.argmin(primary))])