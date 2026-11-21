def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes].astype(np.float64)
    d_dep = distance_matrix[depot][unvisited_nodes].astype(np.float64)
    dem = demands[unvisited_nodes].astype(np.float64)

    scale = float(np.mean(d_dep)) if d_dep.size > 0 else 1.0
    if not np.isfinite(scale) or scale <= 0.0:
        scale = 1.0

    cap = float(rest_capacity)
    if cap <= 0.0:
        cap = 1.0

    s_cur = d_cur / scale
    s_dep = d_dep / scale
    fill = np.clip(dem / cap, 0.0, 1.0)
    s_cap = 1.0 - fill

    # Different weights: less emphasis on current distance, more on depot
    # proximity and capacity filling to diversify the construction.
    score = 0.70 * s_cur + 0.55 * s_dep + 0.40 * s_cap

    return int(unvisited_nodes[int(np.argmin(score))])