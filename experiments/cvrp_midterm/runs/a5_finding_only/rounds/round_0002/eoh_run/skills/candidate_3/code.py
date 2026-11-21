def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if len(unvisited_nodes) == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes].astype(float)
    d_dep = distance_matrix[depot][unvisited_nodes].astype(float)
    d_cur_dep = float(distance_matrix[current_node][depot])

    # Route-elongation view: extra cost of inserting the candidate on the
    # current arc (depot -> ... -> current -> cand) rather than closing the
    # tour directly back to the depot.
    detour = d_cur + d_dep - d_cur_dep

    # Regret / future-accessibility: customers far from the depot would be
    # expensive to serve on a later route; give them mild priority now.
    mean_dep = float(np.mean(d_dep)) if len(d_dep) > 0 else 1.0
    if mean_dep <= 0:
        mean_dep = 1.0
    far_pull = d_dep / mean_dep

    # Load packing: favour larger demands while capacity remains, so routes
    # fill rather than leaving fragments for extra trips.
    dem = demands[unvisited_nodes].astype(float)
    cap = float(rest_capacity) + 1e-9
    load_frac = dem / cap

    # Normalise detour by its own mean so the score is scale-free.
    mean_det = float(np.mean(detour)) if len(detour) > 0 else 1.0
    if mean_det <= 0:
        mean_det = 1.0
    elong = detour / mean_det

    score = elong - 0.30 * far_pull - 0.40 * load_frac
    return int(unvisited_nodes[np.argmin(score)])