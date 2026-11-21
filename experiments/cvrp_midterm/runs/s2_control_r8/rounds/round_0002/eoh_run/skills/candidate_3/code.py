def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return depot

    nodes = np.asarray(unvisited_nodes)
    n = nodes.size

    d_cur = distance_matrix[current_node][nodes].astype(np.float64)
    d_dep = distance_matrix[depot][nodes].astype(np.float64)
    dem = demands[nodes].astype(np.float64)
    cap = float(rest_capacity) if rest_capacity > 0 else 1.0

    # Rank 1: proximity to current node (lower is better -> smaller rank)
    order_prox = np.argsort(np.argsort(d_cur)).astype(np.float64)
    rank_prox = order_prox / max(n - 1, 1)

    # Rank 2: capacity slack fit -- prefer demands that fit nicely
    # small when demand well matches remaining capacity relative to depot distance
    scale = np.maximum(d_dep, 1e-9)
    fit = np.abs(cap - dem) / scale
    order_fit = np.argsort(np.argsort(fit)).astype(np.float64)
    rank_fit = order_fit / max(n - 1, 1)

    # Rank fusion: product of ranks (both in [0,1]); lower is better
    fused = (0.65 + rank_prox) * (0.35 + rank_fit)

    # Angular sector tie-break based on heading from depot through current node
    if current_node != depot:
        p_cur = distance_matrix[depot][current_node]
        # approximate current radial direction using depot distances is not enough;
        # fall back to distance-based tie break
        fused = fused + 1e-6 * dem - 1e-9 * d_cur
    else:
        # At depot: prefer farther customers first (far-first seeding)
        dmax = float(np.max(d_dep)) if d_dep.size > 0 else 1.0
        if dmax <= 0:
            dmax = 1.0
        fused = fused - 0.15 * (d_dep / dmax)

    idx = int(np.argmin(fused))
    return int(nodes[idx])