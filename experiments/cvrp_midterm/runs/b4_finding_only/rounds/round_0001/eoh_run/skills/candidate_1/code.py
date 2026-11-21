def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    d_cur = distance_matrix[current_node]
    d_dep = distance_matrix[depot]
    dists = d_cur[unvisited_nodes]
    depot_dists = d_dep[unvisited_nodes]
    dem = demands[unvisited_nodes]
    scale = float(np.mean(depot_dists) + 1e-9)
    # Relative terms: distance to customer vs. depot distance, plus a mild
    # load penalty that is dimensionless (demand / remaining capacity).
    load_pen = dem / (rest_capacity + 1e-9)
    scores = dists / scale + 0.3 * (depot_dists / scale) + 0.2 * load_pen
    return int(unvisited_nodes[np.argmin(scores)])