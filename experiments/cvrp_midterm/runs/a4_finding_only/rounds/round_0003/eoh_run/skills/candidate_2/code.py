def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if len(unvisited_nodes) == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]

    # Clarke-Wright style savings: serving this node from current instead of depot
    savings = d_dep + distance_matrix[current_node][depot] - d_cur

    # Span-invariant normalization: scale by max pairwise distance involving these nodes
    dm = distance_matrix
    span = float(np.max(d_dep)) + float(np.max(d_cur))
    if span <= 0.0:
        span = 1.0

    savings_n = savings / span

    dem = demands[unvisited_nodes].astype(float)
    cap = float(rest_capacity) if rest_capacity > 0 else 1.0
    total_dem = float(np.sum(dem)) if np.sum(dem) > 0 else 1.0

    # Fraction of remaining demand mass this node represents
    frac = dem / total_dem
    # Utilization relative to remaining capacity (clipped to avoid extreme ratios)
    util = np.clip(dem / cap, 0.0, 1.0)

    # Rank customers by savings first, with mild utilization bonus to pack loads
    score = -savings_n - 0.25 * util - 0.15 * frac

    idx = np.argmin(score)
    return int(unvisited_nodes[idx])