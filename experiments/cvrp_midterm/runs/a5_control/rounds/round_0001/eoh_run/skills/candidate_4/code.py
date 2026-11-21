def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes]

    # Normalize roughly to avoid domination by large distances.
    dc_max = np.max(d_cur)
    dd_max = np.max(d_dep)
    cap = rest_capacity
    if cap <= 0:
        return 0

    # Reward filling the vehicle: higher demand is slightly preferred when it fits.
    fill = dem / cap

    # Score: nearest neighbor dominant, slight depot closeness effect,
    # and load-fill preference. Lower is better.
    score = d_cur + 0.15 * d_dep - 0.25 * (dc_max + 1.0) * fill

    # Early return if nearest remaining customer is disproportionately far future work.
    idx = int(np.argmin(score))
    return int(unvisited_nodes[idx])