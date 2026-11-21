def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]

    base = d_cur - 0.6 * d_dep

    order = np.argsort(base)
    best_idx = int(order[0])

    if order.size == 1:
        return int(unvisited_nodes[best_idx])

    # Soft near-tie weighting based on base score gap.
    span = float(np.max(base) - np.min(base))
    if span <= 0.0:
        span = 1.0

    gaps = base - float(base[best_idx])
    scale = 1e-2 * span
    if scale <= 0.0:
        scale = 1.0

    # Exponential kernel: near base scores get comparable weights.
    weights = np.exp(-np.abs(gaps) / scale)

    # Capacity-fit utility: prefer demands that fill up more of remaining capacity
    # but never exceed it (all nodes already feasible).
    cap = float(rest_capacity) if rest_capacity > 0 else 1.0
    dem = demands[unvisited_nodes].astype(float)
    fill = dem / cap if cap > 0 else dem
    fill = np.clip(fill, 0.0, 1.0)

    # Combined score: weight * fill; distances break ties softly.
    inv_dist = 1.0 / (1.0 + d_cur)
    combined = weights * (0.7 * fill + 0.3 * inv_dist)

    return int(unvisited_nodes[int(np.argmax(combined))])