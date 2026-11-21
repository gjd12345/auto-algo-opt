def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]

    # span-normalised depot term: proportional, not additive in absolute length
    span = float(np.max(d_dep))
    if span <= 0.0:
        span = 1.0
    dep_norm = d_dep / span

    score = d_cur + dep_norm

    # cheap secondary stage: among near-ties, prefer smaller demand
    best = float(np.min(score))
    tol = 1e-9 * (abs(best) + 1.0)
    tied = np.nonzero(score <= best + tol)[0]
    if tied.size > 1:
        cand = unvisited_nodes[tied]
        dd = demands[cand]
        return int(cand[int(np.argmin(dd))])

    return int(unvisited_nodes[int(np.argmin(score))])