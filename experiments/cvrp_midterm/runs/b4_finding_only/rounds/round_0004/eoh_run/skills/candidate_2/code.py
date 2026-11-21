def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes].astype(float)

    scale = float(np.max(distance_matrix[depot])) if distance_matrix.size else 1.0
    if scale <= 0.0:
        scale = 1.0

    cap = float(rest_capacity) if rest_capacity > 0.0 else 1.0
    load_frac = np.clip(dem / cap, 0.0, 1.0)

    # Two normalized, opposing objectives.
    prox = d_cur / scale                                 # smaller = nearer
    backhaul = (d_cur + d_dep - distance_matrix[current_node][depot]) / scale

    # Pareto front: candidates not dominated on (prox, backhaul).
    n = prox.size
    keep = np.ones(n, dtype=bool)
    for i in range(n):
        if not keep[i]:
            continue
        dominated = (prox <= prox[i]) & (backhaul <= backhaul[i])
        strictly = (prox < prox[i]) | (backhaul < backhaul[i])
        if np.any(dominated & strictly):
            keep[i] = False
    front = np.nonzero(keep)[0]
    if front.size == 0:
        front = np.arange(n)

    # Geometric conflict resolution: prefer front points whose direction from
    # the current node trends toward the depot (keeps the return leg short),
    # with a mild reward for high remaining load being picked up.
    cx = distance_matrix[current_node][depot] + 1e-9
    alignment = d_dep[front] / cx            # smaller = more inward
    score = prox[front] + 0.15 * alignment - 0.25 * load_frac[front]

    best_local = int(np.argmin(score))
    return int(unvisited_nodes[front[best_local]])