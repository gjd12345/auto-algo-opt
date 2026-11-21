def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if len(unvisited_nodes) == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    d_home = distance_matrix[current_node][depot]

    # Clarke-Wright saving: serving node now vs returning to depot then visiting it
    savings = d_dep + d_home - d_cur

    # Span-invariant scale (no absolute lengths): only span-proportional terms
    span = float(np.max(d_dep)) + float(np.max(d_cur))
    if span <= 0.0:
        span = 1.0
    savings_n = savings / span

    # Marginal depot-return saving: arriving near depot late in a route is cheap
    depot_pull = (d_home - d_cur) / span  # how much closer node is than depot

    dem = demands[unvisited_nodes].astype(float)
    cap = float(rest_capacity) if rest_capacity > 0 else 1.0
    total_dem = float(np.sum(dem)) if np.sum(dem) > 0 else 1.0

    # Capacity-fill incentive: reward filling the vehicle when load would be wasted
    util = np.clip(dem / cap, 0.0, 1.0)
    frac = dem / total_dem
    # Wastage weight grows as remaining demand mass shrinks relative to capacity
    fill = util * (0.5 + 0.5 * frac)

    # Score: maximize savings and depot pull, add fill bonus (minimize negative)
    score = -savings_n - 0.35 * depot_pull - 0.30 * fill

    idx = np.argmin(score)
    return int(unvisited_nodes[idx])