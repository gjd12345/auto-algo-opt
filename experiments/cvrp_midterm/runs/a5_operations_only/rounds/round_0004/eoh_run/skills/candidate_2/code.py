def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    d_back = distance_matrix[current_node][depot]
    cap = rest_capacity if rest_capacity > 0 else 1.0

    savings = d_back + d_dep - d_cur
    dem = demands[unvisited_nodes]
    fill = dem / cap

    # Multiplicative "promise" score: strong when close, high savings, small demand.
    eps = 1e-6
    progress = (d_cur ** 2) / (savings + eps + 1.0)
    risk = (d_dep + eps) / (cap * (dem + eps) + 1.0)
    primary = progress * (1.0 + 0.6 * fill) * (risk ** 0.5)

    best_val = primary.min()
    tol = 1e-6 * (abs(best_val) + 1.0)
    close = np.where(primary <= best_val + tol)[0]

    if close.size > 1:
        candidates = unvisited_nodes[close]
        secondary = (distance_matrix[current_node][candidates]
                     - 0.5 * savings[close]
                     + 0.3 * demands[candidates] / cap)
        return int(candidates[int(np.argmin(secondary))])

    return int(unvisited_nodes[int(np.argmin(primary))])