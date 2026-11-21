def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes].astype(float)

    cap = max(rest_capacity, 1e-9)
    fill = dem / cap

    # Depot round-trip baseline for the current node.
    base = d_cur + d_dep
    # Savings-style insertion cost: extra distance vs. returning to depot now.
    detour = d_cur + d_dep - distance_matrix[current_node][depot]
    detour_scale = max(float(np.max(detour)), 1e-9)

    # Normalized detour penalty in [0, 1].
    detour_norm = detour / detour_scale

    # Packing term: encourage filling remaining capacity.
    pack_term = fill

    # Directional alignment: prefer customers roughly in line with current
    # radial direction from depot (sweep-like) discounted by detour.
    d_cur_safe = d_cur + 1e-9
    radial = d_dep / d_cur_safe
    radial_scale = max(float(np.max(radial)), 1e-9)
    radial_norm = radial / radial_scale

    # Composite score to minimize: detour penalty minus packing and radial pull.
    scores = detour_norm - 0.55 * pack_term - 0.30 * radial_norm

    return int(unvisited_nodes[np.argmin(scores)])