def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    d_back = distance_matrix[current_node][depot]
    cap = rest_capacity if rest_capacity > 0 else 1.0

    savings = d_back + d_dep - d_cur
    dem = demands[unvisited_nodes]

    # Ordinal (rank) combination: robust to scale, structurally different
    # from additive or multiplicative scoring.
    r_close = np.argsort(np.argsort(d_cur))
    r_save = np.argsort(np.argsort(-savings))
    r_small = np.argsort(np.argsort(dem))

    rank_score = 1.0 * r_close + 0.8 * r_save + 0.5 * r_small

    best_val = rank_score.min()
    close = np.where(rank_score == best_val)[0]

    if close.size > 1:
        candidates = unvisited_nodes[close]
        secondary = (-savings[close]
                     + 1e-6 * distance_matrix[current_node][candidates])
        return int(candidates[int(np.argmin(secondary))])

    return int(unvisited_nodes[int(np.argmin(rank_score))])