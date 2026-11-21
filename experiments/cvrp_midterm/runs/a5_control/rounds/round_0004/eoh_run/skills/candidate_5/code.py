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

    max_depot = float(np.max(d_depot)) if d_depot.size > 0 else 1.0
    if max_depot <= 0.0:
        max_depot = 1.0
    far_norm = d_depot / max_depot

    # Clarke-Wright style savings from extending current -> customer.
    savings = d_depot_cur + d_depot - d_cur
    savings_norm = savings / max_depot

    # Reward far-from-depot customers modestly, but only when the extension
    # yields real savings; penalize going back inward toward the depot.
    inward = np.maximum(d_depot_cur - d_depot, 0.0) / max_depot

    # Load-balance term: prefer customers that fill the vehicle well.
    load_bonus = fill * (0.5 + 0.5 * far_norm)

    score = (
        -1.0 * savings_norm
        + 0.45 * d_cur / max_depot
        - 0.30 * far_norm * (1.0 - fill)
        + 0.20 * inward * d_cur / max_depot
        - 0.55 * load_bonus
    )

    return int(unvisited_nodes[np.argmin(score)])