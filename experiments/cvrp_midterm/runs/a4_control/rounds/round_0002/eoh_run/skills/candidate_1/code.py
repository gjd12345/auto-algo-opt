def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes].astype(float)

    # Insertion cost: marginal detour of visiting this node before returning to depot,
    # normalized by the direct depot round-trip length.
    insertion = (d_cur + d_dep) / np.maximum(d_cur + d_dep + 1e-9, 1e-9)
    insertion_cost = (d_cur + d_dep) - distance_matrix[current_node][depot]
    round_trip = 2.0 * d_dep + 1e-9

    # Fill ratio favors customers that consume more of the remaining capacity.
    fill = dem / max(rest_capacity, 1e-9)

    # Angular coherence: prefer customers roughly aligned with the direction
    # already traveled from depot to current node (behavioral sweep).
    if current_node != depot:
        vx = 0.0
        # Use the cosine similarity via the distance matrix (law of cosines).
        a = distance_matrix[depot][current_node]
        b = d_dep
        c = d_cur
        cos_ang = (a * a + b * b - c * c) / np.maximum(2.0 * a * b, 1e-9)
        aligned = -cos_ang  # prefer forward continuation
    else:
        aligned = np.zeros_like(d_cur)

    score = (
        0.55 * (insertion_cost / round_trip)
        + 0.30 * aligned
        - 0.25 * fill
    )

    return int(unvisited_nodes[np.argmin(score)])