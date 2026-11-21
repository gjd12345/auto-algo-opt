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
    load_frac = dem / cap

    d_cur_dep = distance_matrix[current_node][depot]

    # Primary: Clarke-Wright savings of inserting node between current and depot.
    savings = (d_cur + d_dep - d_cur_dep) / scale
    # Prefer large savings (long shared edges), mildly weighted by how much of
    # the remaining capacity the node consumes so the van fills efficiently.
    primary = savings * (1.0 + 0.20 * load_frac)

    best = float(np.max(primary))
    band = max(abs(best), 1e-9) * 0.10 + 1e-9
    in_band = primary >= best - band

    # Secondary: among near-best savings, pick the node whose geometric
    # position best balances "close to current" and "heading toward depot",
    # rewarding high load to close out the route efficiently.
    outward = d_cur / (d_cur + d_dep + 1e-9)
    balance = outward - 0.35 * load_frac - 0.25 * (d_dep / scale)
    secondary = np.where(in_band, balance, np.inf)

    return int(unvisited_nodes[np.argmin(secondary)])