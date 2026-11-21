def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return depot

    nodes = np.asarray(unvisited_nodes)
    d_cur = distance_matrix[current_node][nodes].astype(np.float64)
    d_dep = distance_matrix[depot][nodes].astype(np.float64)
    dem = demands[nodes].astype(np.float64)

    d_0cur = float(distance_matrix[depot][current_node])
    cap = float(rest_capacity) if rest_capacity > 0 else 1.0

    eps = 1e-9

    # Detour cost: extra distance vs returning straight home from current node.
    detour = d_cur + d_dep - d_0cur
    # Penalize detours that are large relative to the leg already traveled.
    detour_ratio = detour / (d_cur + d_dep + eps)

    # Return pressure: how much capacity each candidate would leave.
    # slack in [0,1]; high when candidate is small relative to remaining cap.
    slack = np.clip(1.0 - dem / (cap + eps), 0.0, 1.0)

    # Rank-blend: turn each raw term into a normalized rank so scales match.
    n = nodes.size
    if n == 1:
        return int(nodes[0])

    order_detour = np.argsort(np.argsort(detour_ratio)).astype(np.float64) / (n - 1)
    order_slack = np.argsort(np.argsort(-slack)).astype(np.float64) / (n - 1)
    order_dep = np.argsort(np.argsort(-d_dep)).astype(np.float64) / (n - 1)

    # Combine: prefer small detour, prefer balanced slack, mild far-first nudge.
    score = 0.55 * order_detour + 0.30 * order_slack + 0.15 * order_dep

    idx = int(np.argmin(score))
    return int(nodes[idx])