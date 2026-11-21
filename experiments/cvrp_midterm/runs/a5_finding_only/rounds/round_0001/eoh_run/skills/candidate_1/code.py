def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes].astype(float)

    # Capacity term: prefer customers that fill the remaining capacity well.
    # Normalize by rest_capacity (relative, scale-invariant w.r.t. distances).
    if rest_capacity > 0:
        fill_ratio = dem / rest_capacity
    else:
        fill_ratio = np.zeros_like(dem)

    # Scale-free combination: distances are relative to the max distance
    # among candidates, avoiding absolute-length contamination.
    max_d = max(float(np.max(d_cur)), float(np.max(d_dep)), 1e-12)
    score = (d_cur / max_d) + 0.5 * (d_dep / max_d) - 0.3 * fill_ratio

    return int(unvisited_nodes[np.argmin(score)])