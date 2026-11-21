def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes].astype(float)
    d_dep = distance_matrix[depot][unvisited_nodes].astype(float)
    dem = demands[unvisited_nodes].astype(float)
    slack = rest_capacity - dem
    slack = np.where(slack < 0.0, 0.0, slack)

    # Normalise each criterion to [0,1] within the candidate set
    def _norm(x):
        lo = float(np.min(x))
        hi = float(np.max(x))
        rng = hi - lo
        if rng <= 1e-12:
            return np.zeros_like(x)
        return (x - lo) / rng

    n_cur = _norm(d_cur)
    n_dep = _norm(d_dep)
    n_slack = _norm(slack)

    # Fleet fill fraction: how full the vehicle currently is
    cap = float(rest_capacity) + float(np.sum(dem))
    fill = 1.0 - (float(rest_capacity) / cap) if cap > 1e-12 else 0.0
    fill = min(max(fill, 0.0), 1.0)

    # Adaptive weights: early in a route favor packing well (slack),
    # late in a route favor returning toward depot cheaply.
    w_slack = 0.55 - 0.35 * fill
    w_dep = 0.20 + 0.45 * fill
    w_cur = 1.0 - w_slack - w_dep

    score = w_cur * n_cur + w_dep * n_dep + w_slack * n_slack

    # Softmin-style sharpening: emphasize the best few candidates
    temperature = 0.10 + 0.25 * fill
    expo = np.exp(-score / temperature)
    total = float(np.sum(expo))
    if total <= 1e-12 or not np.isfinite(total):
        return int(unvisited_nodes[int(np.argmin(score))])

    probs = expo / total
    # Deterministic argmax of the sharpened distribution (equivalent to argmin score)
    pick = int(np.argmax(probs))
    return int(unvisited_nodes[pick])