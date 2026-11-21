def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes]

    # Normalize demand pressure relative to remaining capacity (scale-invariant in distance).
    cap = rest_capacity if rest_capacity > 0 else 1.0
    load_ratio = dem / cap

    denom = d_cur + d_dep
    denom = np.where(denom <= 0.0, 1.0, denom)

    # Scale-invariant score: distance-to-current weighted by depot proximity,
    # plus a load term that promotes filling the vehicle before returning.
    score = (d_cur / denom) * (1.0 + 0.5 * load_ratio) + 0.25 * d_dep / denom * (1.0 - load_ratio)

    return int(unvisited_nodes[np.argmin(score)])