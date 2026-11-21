def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return 0

    nodes = np.asarray(unvisited_nodes)
    d_cur = distance_matrix[current_node][nodes].astype(float)
    d_dep = distance_matrix[depot][nodes].astype(float)
    dem = demands[nodes].astype(float)

    def _norm(v):
        lo = float(np.min(v))
        hi = float(np.max(v))
        rng = hi - lo
        if rng < 1e-12:
            return np.zeros_like(v)
        return (v - lo) / rng

    n_cur = _norm(d_cur)
    n_dep = _norm(d_dep)
    n_dem = _norm(dem)

    cap = max(float(rest_capacity), 1e-12)
    fill = np.clip(dem / cap, 0.0, 1.0)

    score = 1.0 * n_cur - 0.55 * n_dep + 0.35 * n_dem - 0.25 * fill

    best = int(np.argmin(score))
    return int(nodes[best])