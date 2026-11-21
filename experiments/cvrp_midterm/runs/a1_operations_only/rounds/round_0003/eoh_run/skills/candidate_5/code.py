def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return int(depot)

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]

    dem = demands[unvisited_nodes]
    cap = rest_capacity if rest_capacity > 0 else 1.0
    fill = np.clip(dem / cap, 0.0, 1.0)

    # Base ordering: near current node, far from depot, high fill.
    base = d_cur - 0.6 * d_dep + 0.05 * fill * (float(np.max(d_cur)) + 1.0)

    lo = float(np.min(base))
    hi = float(np.max(base))
    span = hi - lo
    if span <= 0.0:
        return int(unvisited_nodes[int(np.argmin(d_cur))])

    # Scale-free relative near-tie gate.
    band = 1e-3 * span
    mask = base <= lo + band

    if not np.any(mask):
        return int(unvisited_nodes[int(np.argmin(base))])

    idxs = np.nonzero(mask)[0]
    if idxs.size == 1:
        return int(unvisited_nodes[int(idxs[0])])

    # Refinement: capacity fit + proximity + return-to-depot efficiency.
    d_max = float(np.max(d_cur)) + 1.0
    fit = fill * (1.0 + 0.5 * (1.0 - d_dep / (float(np.max(d_dep)) + 1.0)))
    ref = (d_cur / d_max) - 0.35 * fit
    best_local = idxs[int(np.argmin(ref[idxs]))]
    return int(unvisited_nodes[int(best_local)])