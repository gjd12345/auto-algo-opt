def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    current_node = int(current_node)
    depot = int(depot)
    unvisited_nodes = np.asarray(unvisited_nodes, dtype=int)
    if unvisited_nodes.size == 0:
        return depot

    demand = demands[unvisited_nodes].astype(float)
    d_cur = distance_matrix[current_node][unvisited_nodes].astype(float)
    d_depot = distance_matrix[depot][unvisited_nodes].astype(float)
    d_depot_cur = float(distance_matrix[depot][current_node])

    cap = float(rest_capacity)
    fill = demand / cap if cap > 0.0 else np.zeros_like(demand)

    # Normalize distances to make combination scale-free.
    max_depot = float(np.max(d_depot)) if d_depot.size > 0 else 1.0
    if max_depot <= 0.0:
        max_depot = 1.0
    far_norm = d_depot / max_depot  # in [0, 1]

    # Multiplicative interaction: nearby AND far-from-depot is rewarded.
    proximity = d_cur / (1.0 + 0.8 * far_norm)

    # Strongly discourage moves that head back inward toward the depot while
    # capacity is still available.
    inward = np.maximum(d_depot_cur - d_depot, 0.0)
    inward_norm = inward / max_depot

    # Quadratic penalty for tiny fills (wasteful stops) plus a mild reward
    # for substantial fills.
    low_fill_penalty = (1.0 - fill) * d_cur if cap > 0.0 else np.zeros_like(d_cur)

    score = (
        proximity
        + 0.9 * inward_norm * d_cur
        - 0.25 * d_cur * far_norm
        + 0.15 * low_fill_penalty
    )

    return int(unvisited_nodes[np.argmin(score)])