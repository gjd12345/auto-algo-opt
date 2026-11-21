def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if len(unvisited_nodes) == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]

    # Scale-invariant reference length: max depot distance among customers.
    scale = float(np.max(distance_matrix[depot][1:])) if distance_matrix.shape[0] > 1 else 1.0
    if scale <= 0:
        scale = 1.0

    d_cur_n = d_cur / scale
    d_dep_n = d_dep / scale

    dem = demands[unvisited_nodes].astype(float)
    cap = float(rest_capacity) if rest_capacity > 0 else 1.0
    # Utilization after serving this node (higher = tighter fit).
    util_after = (cap - dem) / cap
    util_after = np.clip(util_after, 0.0, 1.0)

    # Different parameter setting: emphasize nearness and depot proximity,
    # reward nodes that fit the remaining capacity tightly (small util_after),
    # and mildly penalize depot distance to encourage compact clusters.
    score = 1.2 * d_cur_n + 0.4 * d_dep_n + 0.25 * util_after

    idx = int(np.argmin(score))
    return int(unvisited_nodes[idx])