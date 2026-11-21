def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes]

    # Load ratio: 1.0 = empty, ~0.0 = nearly full
    max_dem = float(np.max(dem)) + 1e-9
    load_frac = rest_capacity / (rest_capacity + float(np.sum(dem)) + 1e-9)

    # Priority: closer to current node is better (lower score),
    # but when capacity is tight prefer nodes near the depot and with larger demand.
    score = d_cur + (1.0 - load_frac) * (0.3 * d_dep - 0.5 * dem)

    return int(unvisited_nodes[int(np.argmin(score))])