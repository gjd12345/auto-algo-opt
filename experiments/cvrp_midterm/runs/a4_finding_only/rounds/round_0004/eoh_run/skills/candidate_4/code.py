def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if len(unvisited_nodes) == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]

    dem = demands[unvisited_nodes].astype(float)
    cap = float(rest_capacity) if rest_capacity > 0 else 1.0
    util = dem / cap

    scale = np.max(d_dep) if np.max(d_dep) > 0 else 1.0
    d_cur_n = d_cur / scale
    d_dep_n = d_dep / scale

    # Polar/angular ordering around depot using centroid geometry is unavailable,
    # so use a swept-score: proximity to current node, load fill, and a
    # "return-toward-depot" pull weighted by how full the vehicle is.
    load_used = 1.0 - (cap - np.sum(dem)) / cap if cap > 0 else 0.0
    load_used = min(max(load_used, 0.0), 1.0)

    # As the vehicle fills up, weight depot pull more strongly to start closing the tour.
    score = (1.0 - 0.5 * load_used) * d_cur_n \
            - (0.35 + 0.55 * load_used) * (1.0 - d_dep_n) \
            - 0.25 * util

    idx = np.argmin(score)
    return int(unvisited_nodes[idx])