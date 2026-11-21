def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return depot

    cap = float(rest_capacity)
    if cap <= 0.0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes].astype(float)
    d_dep = distance_matrix[depot][unvisited_nodes].astype(float)
    dem = demands[unvisited_nodes].astype(float)

    # Fit ratio: how much of remaining capacity this customer fills (0..1]
    fit = dem / cap

    # Prefer customers that fill capacity well (close to 1 fit), without
    # over-committing: penalize both underfill and extreme fill.
    fit_score = -np.abs(fit - 0.85)

    # Normalized proximity: closer to current node is better, but we cap the
    # influence using a scale based on route geometry so it does not dominate.
    span = np.maximum(np.max(d_cur) if d_cur.size else 1.0, 1e-9)
    prox = -d_cur / span

    # Depot-reach term: mild preference for customers moderately far from depot
    # (avoids picking tiny near-depot hops that fragment the route).
    dspan = np.maximum(np.max(d_dep) if d_dep.size else 1.0, 1e-9)
    dep_term = d_dep / dspan

    # Composite: capacity fit dominates, proximity refines, depot term regularizes.
    score = 2.0 * fit_score + 1.0 * prox + 0.25 * dep_term

    return int(unvisited_nodes[int(np.argmax(score))])