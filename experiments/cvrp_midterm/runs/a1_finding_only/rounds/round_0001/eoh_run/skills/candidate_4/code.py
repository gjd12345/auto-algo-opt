def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return depot
    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    # span of distances among candidates and depot, scale-free normalization
    all_d = np.concatenate((d_cur, d_dep, distance_matrix[current_node][[depot]]))
    span = float(all_d.max() - all_d.min())
    if span <= 0.0:
        span = 1.0
    # normalized terms
    cur_n = d_cur / span
    dep_n = d_dep / span
    dem = demands[unvisited_nodes]
    cap = max(rest_capacity, 1e-12)
    # load pressure: high when remaining capacity after this customer is small relative to its demand
    load_n = dem / cap  # in [0,1]
    # Score: prefer close to current, close to depot (cheap return), and filling capacity
    score = -1.0 * cur_n - 0.45 * dep_n + 0.35 * load_n
    return int(unvisited_nodes[np.argmax(score)])