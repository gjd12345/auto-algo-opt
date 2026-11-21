def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return depot
    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes]

    # Scale-free normalisers over the candidate set.
    dc_sum = np.sum(d_cur)
    if dc_sum <= 0:
        dc_sum = 1.0
    dd_sum = np.sum(d_dep)
    if dd_sum <= 0:
        dd_sum = 1.0

    prox = d_cur / dc_sum                 # prefer near candidates
    dep = d_dep / dd_sum                  # prefer customers far from depot (hard to leave)
    cap = rest_capacity if rest_capacity > 0 else 1.0
    fill = dem / cap                      # prefer filling the vehicle
    fill = np.clip(fill, 0.0, 1.0)

    # Single composite score: proximity dominates, depot-return and fill act as
    # continuous modifiers instead of a discrete near-tie window.
    score = prox - 0.35 * dep - 0.25 * fill
    return unvisited_nodes[np.argmin(score)]