def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes].astype(float)
    d_dep = distance_matrix[depot][unvisited_nodes].astype(float)
    dem = demands[unvisited_nodes].astype(float)

    total = 0.0
    for v in unvisited_nodes:
        total += distance_matrix[depot][v]
    total = total if total > 0 else 1.0

    # Savings: how much return distance is avoided by visiting this customer now.
    denom = d_cur + d_dep
    denom = np.where(denom <= 0.0, 1e-12, denom)
    savings = (d_dep) / denom  # in [0,1], larger when customer is close but far from depot
    # Actually use classic savings-like ratio: (d_dep) / (d_cur + d_dep)
    score = savings

    # Load-aware bonus: prefer customers that fill the truck (reduces number of routes).
    cap = float(rest_capacity) if rest_capacity > 0 else 1.0
    dem_frac = dem / cap
    score = score + 0.35 * dem_frac

    # Prefer customers closer to depot (route-cluster cohesion) at small weight.
    dep_norm = d_dep / (float(np.max(d_dep)) + 1e-12)
    score = score - 0.25 * dep_norm

    # Deterministic tie-break: nearer customer.
    score = score - 1e-9 * (d_cur / (float(np.max(d_cur)) + 1e-12))

    idx = int(np.argmax(score))
    return int(unvisited_nodes[idx])