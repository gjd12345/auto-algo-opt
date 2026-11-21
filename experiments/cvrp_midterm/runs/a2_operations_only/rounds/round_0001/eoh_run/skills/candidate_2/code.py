def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes]

    # Primary score: balance travel from current node with return cost,
    # and slightly reward filling the remaining capacity.
    cap = rest_capacity if rest_capacity > 0 else 1.0
    fill = dem / cap  # fraction of remaining capacity used
    score = 1.0 * d_cur + 0.5 * d_dep - 0.35 * fill * (d_cur.mean() + 1e-9)

    # Secondary ordering among near-tied candidates: pick the nearest one
    # to the current node to keep routes compact.
    order = np.argsort(score)
    best = order[0]
    tol = 1e-6 + 0.05 * (score[order[-1]] - score[order[0]] + 1e-9)
    tied = order[score[order] <= score[best] + tol]
    if tied.size > 1:
        # cheap nearest-neighbour tie-break
        local = np.argmin(d_cur[tied])
        best = tied[local]

    return int(unvisited_nodes[best])