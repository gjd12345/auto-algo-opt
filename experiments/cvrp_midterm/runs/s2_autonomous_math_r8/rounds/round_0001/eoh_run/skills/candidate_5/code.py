def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return 0

    nodes = np.asarray(unvisited_nodes)
    dem = demands[nodes].astype(float)

    d_cur = distance_matrix[current_node][nodes].astype(float)
    d_dep = distance_matrix[depot][nodes].astype(float)
    d_cur_dep = float(distance_matrix[current_node][depot])

    all_d = distance_matrix[nodes][:, nodes].astype(float)
    scale = float(np.max(all_d)) if all_d.size > 0 else 1.0
    if scale <= 0.0:
        scale = 1.0

    rest = float(rest_capacity)
    if rest <= 0.0:
        rest = 1.0

    if current_node == depot:
        # Depot-start: farthest-first radial seed with stronger load weighting.
        rel_dem = dem / rest
        rel_dist = d_dep / scale
        score = -(1.0 * rel_dist + 0.8 * rel_dem)
        return int(nodes[int(np.argmin(score))])

    # Mid-route: stronger depot pull + convex capacity-fill reward.
    alpha_mid = 0.75
    rel_cur = d_cur / scale
    rel_dep = d_dep / scale

    fill = dem / rest
    fill_clipped = np.minimum(fill, 1.0)
    fill_term = -0.4 * (2.0 * fill_clipped - fill_clipped * fill_clipped)

    local = d_cur / (d_cur_dep + scale)

    score = rel_cur - alpha_mid * rel_dep + fill_term + 5e-4 * local

    return int(nodes[int(np.argmin(score))])